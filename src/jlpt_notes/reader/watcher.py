"""Native events with periodic strong reconciliation and polling fallback."""

from __future__ import annotations

import math
import stat
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Condition, Event, Lock, Thread, current_thread

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .links import EVIDENCE_SUFFIXES, is_evidence_path
from .sources import _is_directory_link, iter_supported_visible_source_files

_DOCUMENT_SUFFIXES = frozenset({'.md', '.jsonl'})
_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.webp'})
_MAX_PENDING_PATHS = 4096


@dataclass(frozen=True, order=True)
class FileStamp:
    """The minimal, deterministic state used to identify one source file."""

    path: str
    size: int
    modified_ns: int
    digest: str = ''


def snapshot_sources(
    root: Path, *, extra_paths: tuple[Path, ...] = (), content_hashes: bool = False,
) -> tuple[FileStamp, ...]:
    """Return stable stamps for visible sources and their Git submission state.

    The function reads file metadata, optional content hashes and Git state. It does not follow
    symlinks or create any files, so observing a learner's source directory is
    safe.  Files that disappear during an editor's save operation are skipped
    and are picked up on the following poll.
    """
    resolved = root.resolve(strict=True)
    stamps: list[FileStamp] = []
    suffixes = _DOCUMENT_SUFFIXES | _IMAGE_SUFFIXES | EVIDENCE_SUFFIXES
    for path in iter_supported_visible_source_files(resolved, suffixes=suffixes):
        relative = path.relative_to(resolved)
        if path.suffix.lower() in EVIDENCE_SUFFIXES and not is_evidence_path(relative):
            continue
        try:
            stat = path.stat()
            digest = sha256(path.read_bytes()).hexdigest() if content_hashes else ''
        except OSError:
            # A rename/atomic editor-save can legitimately win this race.
            continue
        stamps.append(
            FileStamp(
                path.relative_to(resolved).as_posix(),
                stat.st_size,
                stat.st_mtime_ns,
                digest,
            )
        )
    for extra in _normalize_paths(extra_paths):
        if _has_directory_link(extra):
            continue
        candidates = (
            iter_supported_visible_source_files(extra, suffixes=_extra_suffixes(extra))
            if extra.is_dir() else (extra,)
        )
        for path in candidates:
            if '__pycache__' in path.parts:
                continue
            try:
                if _has_directory_link(path) or not path.is_file():
                    continue
                stat = path.stat()
                digest = sha256(path.read_bytes()).hexdigest() if content_hashes else ''
            except OSError:
                continue
            stamps.append(FileStamp(f'<extra:{path}>', stat.st_size, stat.st_mtime_ns, digest))
    git_stamp = _git_state_stamp(resolved)
    if git_stamp is not None:
        stamps.append(git_stamp)
    return _sorted_stamps({stamp.path: stamp for stamp in stamps})


def _sorted_stamps(inventory: dict[str, FileStamp]) -> tuple[FileStamp, ...]:
    return tuple(sorted(inventory.values(), key=lambda stamp: _name_sort_key(stamp.path)))


def _normalize_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(sorted({path.absolute() for path in paths}, key=str))


def _has_directory_link(path: Path) -> bool:
    """Reject links/reparse points without treating deleted paths as links."""
    return any(_is_directory_link(candidate) for candidate in (path, *path.parents)
               if candidate.exists() or candidate.is_symlink())


def _same_content(left: tuple[FileStamp, ...] | None, right: tuple[FileStamp, ...]) -> bool:
    if left is None or len(left) != len(right):
        return False
    return all(
        (a.path, a.size, a.digest) == (b.path, b.size, b.digest)
        if a.digest and b.digest else a == b
        for a, b in zip(left, right, strict=True)
    )


def _extra_suffixes(root: Path) -> frozenset[str]:
    # Configuration directories can contain templates, scripts, and extensionless files.
    # Discover in the same visibility-safe traversal, without assuming their extensions.
    import os
    if _has_directory_link(root):
        return frozenset()
    suffixes = {''}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not name.startswith('.') and name != '__pycache__'
                   and not _is_directory_link(Path(directory) / name)]
        suffixes.update(Path(name).suffix.lower() for name in files if not name.startswith('.'))
    return frozenset(suffixes)


def _git_state_stamp(root: Path) -> FileStamp | None:
    """Represent HEAD and scoped worktree state without watching ``.git`` files."""
    try:
        top_level = Path(
            _run_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        ).resolve()
        scope = root.relative_to(top_level).as_posix() or "."
        try:
            head = _run_git(top_level, "rev-parse", "--verify", "HEAD").strip()
        except subprocess.CalledProcessError:
            head = b"(unborn)"
        worktree = _run_git(
            top_level,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            scope,
        )
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError):
        return None

    digest = sha256(head + b"\0" + worktree).digest()
    return FileStamp(
        path="<git-submission-state>",
        size=int.from_bytes(digest[:8], "big"),
        modified_ns=int.from_bytes(digest[8:16], "big"),
    )


def _run_git(repository: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def _name_sort_key(value: str) -> tuple[str, str]:
    return (value.casefold(), value)


class ChangeDetector:
    """Convert changing snapshots into one callback after a settle period."""

    def __init__(self, debounce_seconds: float) -> None:
        if not math.isfinite(debounce_seconds) or debounce_seconds < 0:
            raise ValueError("debounce_seconds must be a non-negative finite number")
        self._debounce_seconds = debounce_seconds
        self._latest: tuple[FileStamp, ...] | None = None
        self._changed_at: float | None = None

    def observe(self, snapshot: tuple[FileStamp, ...], now: float) -> bool:
        """Observe one snapshot and report whether its change has settled."""
        if self._latest is None:
            self._latest = snapshot
            return False
        if snapshot != self._latest:
            self._latest = snapshot
            self._changed_at = now
            return False
        if self._changed_at is None or now - self._changed_at < self._debounce_seconds:
            return False
        self._changed_at = None
        return True


class _EventHandler(FileSystemEventHandler):
    def __init__(self, watcher: SourceWatcher) -> None:
        self.watcher = watcher

    def on_any_event(self, event) -> None:
        if event.event_type in {'opened', 'closed_no_write'}:
            return
        if event.event_type not in {'created', 'modified', 'deleted', 'moved', 'closed'}:
            self.watcher._notice_event()
            return
        if event.is_directory and event.event_type in {'modified', 'closed'}:
            return
        paths = []
        refresh = False
        for value in (event.src_path, getattr(event, 'dest_path', '')):
            if value and self.watcher._relevant(Path(value), event.is_directory):
                path = Path(value).absolute()
                refresh |= event.is_directory and any(
                    extra == path or extra.is_relative_to(path)
                    for extra in self.watcher._extra_paths)
                paths.append(path)
        if paths:
            self.watcher._notice_event(tuple(paths), refresh=refresh, full_resync=event.is_directory)


class SourceWatcher:
    """Debounce native notifications; reconcile content/Git/config every minute.

    ``prepare`` listens before the initial build, while ``start`` enables the
    scheduler and serialized callback worker. Explicit snapshotters retain the
    historical deterministic polling interface.
    """

    def __init__(
        self,
        root: Path,
        on_change: Callable[[], object],
        interval_seconds: float = 0.5,
        debounce_seconds: float = 0.5,
        *,
        on_error: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        snapshotter: Callable[[Path], tuple[FileStamp, ...]] | None = None,
        initial_snapshot: tuple[FileStamp, ...] | None = None,
        extra_paths: tuple[Path, ...] = (),
        reconcile_seconds: float = 60,
        observer_factory: Callable[[], object] = Observer,
    ) -> None:
        for name, value in (('interval_seconds', interval_seconds),
                            ('reconcile_seconds', reconcile_seconds)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be a positive finite number')
        self._root = root.absolute()
        self._on_change = on_change
        self._on_error = on_error
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._snapshotter = snapshotter or snapshot_sources
        self._legacy = snapshotter is not None
        self._detector = ChangeDetector(debounce_seconds)
        self._debounce_seconds = debounce_seconds
        if initial_snapshot is not None:
            self._detector.observe(initial_snapshot, 0.0)
        self._latest = initial_snapshot
        self._extra_paths = _normalize_paths(extra_paths)
        self._reconcile_seconds = reconcile_seconds
        self._observer_factory = observer_factory
        self._observer = None
        self._observer_lock = Lock()
        self._git_dirs: tuple[Path, ...] = ()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._worker: Thread | None = None
        self._lock = Lock()
        self._condition = Condition()
        self._prepared = False
        self._event_at: float | None = None
        self._event_serial = 0
        self._pending_paths: set[Path] = set()
        self._full_resync = False
        self._refresh_watches = False
        self._queued = 0
        self._completed = 0
        self._retry_at = 0.0
        self._poll_retry_at: float | None = None
        self._next_reconcile = 0.0
        self._next_poll = 0.0
        self._next_observer_retry = 0.0
        self._snapshot_retry_at = 0.0

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def change_token(self) -> int:
        """Return the event generation, including transient edits during a build."""
        with self._condition:
            return self._event_serial

    def ensure_rebuild_after(self, token: int) -> bool:
        """Queue a retry if events occurred while a controller build was in flight."""
        with self._condition:
            if token == self._event_serial:
                return True
            self._queued += 1
            if self._event_at is not None:
                self._retry_at = max(self._retry_at, self._event_at + self._debounce_seconds)
            self._condition.notify_all()
            return False

    def prepare(self) -> None:
        """Start listening and seed a strong baseline, without invoking callbacks."""
        if self._prepared or self._legacy:
            return
        self._root = self._root.resolve(strict=True)
        self._stop_event.clear()
        self._start_observer()
        baseline = self._strong_snapshot()
        now = self._clock()
        with self._condition:
            if self._latest is not None and not _same_content(self._latest, baseline):
                self._queued += 1
                self._retry_at = max(self._retry_at, now + self._debounce_seconds)
            self._latest = baseline
        self._next_reconcile = now + self._reconcile_seconds
        self._next_poll = now + 1.0
        self._prepared = True

    def update_extra_paths(self, paths: tuple[Path, ...]) -> None:
        """Refresh native configuration watches when a config discovers new resources."""
        normalized = _normalize_paths(paths)
        with self._condition:
            if normalized == self._extra_paths:
                return
            self._extra_paths = normalized
            self._notice_event(refresh=True, full_resync=True)

    def start(self) -> None:
        """Enable watching; repeated calls leave the existing workers unchanged."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self.prepare()
            self._stop_event.clear()
            if not self._legacy:
                self._worker = Thread(target=self._run_callbacks,
                                      name='jlpt-reader-callback', daemon=True)
                self._worker.start()
            self._thread = Thread(target=self._run, name='jlpt-reader-watcher', daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop listening promptly; an already-running callback may finish separately."""
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        self._stop_observer()
        with self._lock:
            threads = (self._thread, self._worker)
        for thread in threads:
            if thread is not None and thread is not current_thread():
                thread.join(timeout=0.1)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = None
        self._prepared = False

    def poll_once(self, now: float | None = None) -> bool:
        """Historical synchronous poll seam, including retry of a failed callback."""
        now = self._clock() if now is None else now
        try:
            snapshot = self._snapshotter(self._root)
            changed = self._detector.observe(snapshot, now)
        except Exception as error:  # noqa: BLE001 - injected snapshotters must not stop watching
            self._report_error('source snapshot failed', error)
            return False
        if not changed and (self._poll_retry_at is None or now < self._poll_retry_at):
            return False
        if self._invoke_callback():
            self._poll_retry_at = None
            return True
        self._poll_retry_at = now + 1.0
        return False

    def _strong_snapshot(self) -> tuple[FileStamp, ...]:
        return snapshot_sources(self._root, extra_paths=self._extra_paths, content_hashes=True)

    def _notice_event(
        self, paths: tuple[Path, ...] = (), *, refresh: bool = False, full_resync: bool = False,
    ) -> None:
        with self._condition:
            self._event_at = self._clock()
            self._event_serial += 1
            self._refresh_watches |= refresh
            self._full_resync |= full_resync or not paths
            if not self._full_resync:
                self._pending_paths.update(paths)
                if len(self._pending_paths) > _MAX_PENDING_PATHS:
                    self._full_resync = True
            if self._full_resync:
                self._pending_paths.clear()
            self._condition.notify_all()

    def _path_snapshot(self, paths: set[Path]) -> tuple[FileStamp, ...]:
        """Refresh only changed files in the strong inventory, plus scoped Git state."""
        inventory = {stamp.path: stamp for stamp in self._latest or ()}
        for path in paths:
            labels = set()
            extra_label = f'<extra:{path}>'
            if extra_label in inventory:
                labels.add(extra_label)
            try:
                relative = path.relative_to(self._root)
            except ValueError:
                relative = None
            if (relative is not None and not any(part.startswith('.') for part in relative.parts)
                and (path.suffix.lower() in _DOCUMENT_SUFFIXES | _IMAGE_SUFFIXES
                     or is_evidence_path(relative))):
                labels.add(relative.as_posix())
            for extra in self._extra_paths:
                if path == extra:
                    labels.add(extra_label)
                elif extra.is_dir() and path.is_relative_to(extra):
                    relative_extra = path.relative_to(extra)
                    if ('__pycache__' not in relative_extra.parts
                        and not any(part.startswith('.') for part in relative_extra.parts)):
                        labels.add(extra_label)
            if not labels:
                continue  # Git metadata paths are handled by the Git stamp below.
            exists = self._visible(path, Path())
            try:
                info = path.lstat() if exists else None
                if info is not None and stat.S_ISREG(info.st_mode):
                    digest = sha256(path.read_bytes()).hexdigest()
                else:
                    exists = False
            except (FileNotFoundError, NotADirectoryError):
                exists = False
            for label in labels:
                if exists:
                    inventory[label] = FileStamp(label, info.st_size, info.st_mtime_ns, digest)
                else:
                    inventory.pop(label, None)
        git_stamp = _git_state_stamp(self._root)
        if git_stamp is None:
            inventory.pop('<git-submission-state>', None)
        else:
            inventory[git_stamp.path] = git_stamp
        return _sorted_stamps(inventory)

    def _relevant(self, path: Path, directory: bool) -> bool:
        path = path.absolute()
        for git_dir in self._git_dirs:
            try:
                relative = path.relative_to(git_dir)
            except ValueError:
                continue
            return relative.as_posix() in {'HEAD', 'index', 'packed-refs', 'refs'} or (
                relative.parts and relative.parts[0] == 'refs'
                and not relative.name.endswith('.lock'))
        for extra in self._extra_paths:
            if path == extra:
                return not _has_directory_link(path)
            if directory and extra.is_relative_to(path):
                return not _has_directory_link(path)
            if extra.is_dir():
                try:
                    relative = path.relative_to(extra)
                except ValueError:
                    continue
                return '__pycache__' not in relative.parts and self._visible(path, relative)
        try:
            relative = path.relative_to(self._root)
        except ValueError:
            return False
        return self._visible(path, relative) and (
            directory or path.suffix.lower() in _DOCUMENT_SUFFIXES | _IMAGE_SUFFIXES
            or is_evidence_path(relative))

    @staticmethod
    def _visible(path: Path, relative: Path) -> bool:
        if any(part.startswith('.') for part in relative.parts):
            return False
        # Do not follow linked files or directories, including internal links.
        return not _has_directory_link(path)

    def _discover_git_dirs(self) -> tuple[Path, ...]:
        try:
            result = []
            for argument in ('--absolute-git-dir', '--git-common-dir'):
                value = Path(_run_git(self._root, 'rev-parse', argument).decode().strip())
                result.append((self._root / value).resolve())
            return tuple(dict.fromkeys(result))
        except (OSError, UnicodeError, subprocess.CalledProcessError):
            return ()

    def _start_observer(self) -> None:
        with self._observer_lock:
            if not self._stop_event.is_set():
                self._launch_observer()

    def _launch_observer(self) -> None:
        observer = None
        try:
            observer = self._observer_factory()
            handler = _EventHandler(self)
            self._git_dirs = self._discover_git_dirs()
            watches = {(self._root, True)}
            for extra in self._extra_paths:
                if _has_directory_link(extra):
                    continue
                parent = extra if extra.is_dir() else extra.parent
                while not parent.is_dir() and parent != parent.parent:
                    parent = parent.parent
                watches.add((parent, extra.is_dir()))
            for git_dir in self._git_dirs:
                watches.add((git_dir, False))
                refs = git_dir / 'refs'
                if refs.is_dir():
                    watches.add((refs, True))
            for path, recursive in watches:
                observer.schedule(handler, str(path), recursive=recursive)
            observer.start()
            self._observer = observer
            if self._prepared:
                self._notice_event()  # Recovery may have missed notifications.
        except Exception as error:  # noqa: BLE001 - notification failures require polling fallback
            if observer is not None:
                try:
                    observer.stop()
                    if observer.is_alive():
                        observer.join(timeout=0.1)
                except Exception as cleanup_error:  # noqa: BLE001 - best-effort partial startup cleanup
                    self._report_error('partial native observer shutdown failed', cleanup_error)
            self._observer = None
            self._report_error('native observer failed; using one-second polling', error)
        self._next_observer_retry = self._clock() + 1.0

    def _stop_observer(self) -> None:
        with self._observer_lock:
            self._close_observer()

    def _close_observer(self) -> None:
        observer, self._observer = self._observer, None
        if observer is not None:
            try:
                observer.stop()
                if observer is not current_thread() and observer.is_alive():
                    observer.join(timeout=0.1)
            except Exception as error:  # noqa: BLE001 - backend shutdown must remain best-effort
                self._report_error('native observer shutdown failed', error)

    def _observer_healthy(self) -> bool:
        observer = self._observer
        return (observer is not None and observer.is_alive()
                and bool(observer.emitters)
                and all(emitter.is_alive() for emitter in observer.emitters))

    def _service_once(self, now: float) -> None:
        with self._condition:
            refresh = self._refresh_watches
            self._refresh_watches = False
        if refresh and self._observer is not None:
            self._stop_observer()
            self._notice_event()
            self._start_observer()
        if self._observer is not None and not self._observer_healthy():
            self._report_error('native observer stopped; using one-second polling',
                               RuntimeError('observer or emitter is no longer alive'))
            self._stop_observer()
            self._next_poll = min(self._next_poll, now + 1.0)
        fallback = self._observer is None
        if fallback and now >= self._next_observer_retry:
            self._start_observer()
        with self._condition:
            serial = self._event_serial
            paths = self._pending_paths.copy()
            full_resync = self._full_resync
            event_ready = (self._event_at is not None
                           and now - self._event_at >= self._debounce_seconds)
            settling = self._event_at is not None and not event_ready
        reconcile = now >= self._next_reconcile
        poll = fallback and now >= self._next_poll
        if settling or now < self._snapshot_retry_at or not (event_ready or reconcile or poll):
            return
        try:
            snapshot = (self._strong_snapshot() if reconcile or poll or full_resync
                        else self._path_snapshot(paths))
        except Exception as error:  # noqa: BLE001 - snapshots must retain dirty state on any failure
            self._report_error('source snapshot failed', error)
            self._snapshot_retry_at = now + 1.0
            return
        self._snapshot_retry_at = 0.0
        if reconcile:
            self._next_reconcile = now + self._reconcile_seconds
        if poll:
            self._next_poll = now + 1.0
        with self._condition:
            if self._event_serial == serial:
                self._event_at = None
                self._pending_paths.clear()
                self._full_resync = False
            changed = not _same_content(self._latest, snapshot)
            self._latest = snapshot
            if changed:
                self._queued += 1
                self._condition.notify_all()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._legacy:
                self.poll_once()
                self._stop_event.wait(self._interval_seconds)
            else:
                try:
                    self._service_once(self._clock())
                except Exception as error:  # noqa: BLE001 - service errors must not end monitoring
                    self._report_error('watcher service failed', error)
                    self._stop_observer()
                with self._condition:
                    if not self._stop_event.is_set():
                        self._condition.wait(timeout=0.05)

    def _run_callbacks(self) -> None:
        while not self._stop_event.is_set():
            with self._condition:
                while not self._stop_event.is_set() and (
                    self._queued <= self._completed or self._clock() < self._retry_at
                    or self._event_at is not None
                ):
                    self._condition.wait(timeout=0.1)
                if self._stop_event.is_set():
                    return
                generation = self._queued
            succeeded = self._invoke_callback()
            with self._condition:
                if succeeded:
                    self._completed = generation
                    self._retry_at = 0.0
                else:
                    self._retry_at = self._clock() + 1.0
                self._condition.notify_all()

    def _invoke_callback(self) -> bool:
        try:
            return self._on_change() is not False
        except Exception as error:  # noqa: BLE001 - arbitrary build callbacks are outside watcher control
            self._report_error('on_change callback failed', error)
            return False

    def _report_error(self, context: str, error: Exception) -> None:
        if self._on_error is None:
            return
        try:
            self._on_error(f'{context}: {type(error).__name__}: {error}')
        except Exception:  # noqa: BLE001, S110 - diagnostics must not stop watcher or retry callbacks
            pass
