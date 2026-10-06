"""Verified, bounded, disposable site caches; never a learning-data backup."""

import importlib.metadata
import json
import os
import re
import shutil
import stat
import sys
import time
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import yaml

from .builder import BuildResult
from .session import _OwnerLock
from .sources import (
    _is_directory_link,
    is_evidence_path,
    iter_supported_visible_source_files,
)
from .watcher import _git_state_stamp

_FORMAT = 1
_OWNER = b'jlpt-reader-cache-v1\n'
_MARKER = '.jlpt-reader-owned'
_KEY = re.compile(r'[0-9a-f]{64}\Z')
_GENERATION = re.compile(r'(?:generation|candidate)-[0-9a-f]{32}\Z')
_SOURCE_SUFFIXES = frozenset({'.md', '.jsonl', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.txt', '.json'})


def _linked(path: Path) -> bool:
    """Reject Windows junctions/reparse points as well as dangling symlinks."""
    return path.is_symlink() or (path.exists() and _is_directory_link(path))


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def configuration_paths(config_path: Path) -> tuple[Path, ...]:
    """Config, inherited configs, templates, presentation files and plugin code."""
    pending = [Path(config_path).resolve(strict=True)]
    found: set[Path] = set()
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        found.add(path)
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict):
            raise TypeError('Reader configuration must be a mapping')
        parent = data.get('INHERIT')
        if parent:
            pending.append((path.parent / parent).resolve(strict=True))
        found.update((path.parent / 'assets', path.parent / 'overrides'))
        theme = data.get('theme', {})
        if isinstance(theme, dict) and theme.get('custom_dir'):
            found.add(path.parent / theme['custom_dir'])
        for item in data.get('plugins', ()) or ():
            if isinstance(item, dict):
                options = item.get('jlpt_reader')
                if isinstance(options, dict) and options.get('assets_dir'):
                    found.add(path.parent / options['assets_dir'])
        for name in ('extra_css', 'extra_javascript', 'hooks'):
            for item in data.get(name, ()) or ():
                if isinstance(item, dict):
                    item = item.get('path')
                if isinstance(item, str) and not re.match(r'(?:[a-z]+:)?//', item):
                    found.add(path.parent / item)
    package = Path(__file__).resolve().parents[1]
    found.add(package)
    for name in ('pyproject.toml', 'uv.lock'):
        found.add(package.parents[1] / name)
    return tuple(sorted(found, key=str))


def configuration_fingerprint(config_path: Path) -> str:
    """Include implementation/dependency versions so stale sanitizers never reuse HTML."""
    digest = sha256(str(Path(config_path).resolve()).encode())
    package = Path(__file__).resolve().parents[1]
    for resource in configuration_paths(config_path):
        digest.update(str(resource).encode('utf-8'))
        if _linked(resource):
            raise ValueError('Cache does not reuse linked presentation resources')
        if resource.is_dir():
            paths = sorted(resource.rglob('*'))
            for path in paths:
                if '__pycache__' in path.parts or any(part.startswith('.') for part in path.relative_to(resource).parts):
                    continue
                if _linked(path):
                    raise ValueError('Cache does not reuse linked presentation resources')
                if path.is_file() and (resource != package or path.suffix == '.py'):
                    digest.update(path.relative_to(resource).as_posix().encode('utf-8'))
                    digest.update(_digest_file(path).encode())
        elif resource.is_file():
            digest.update(_digest_file(resource).encode())
        else:
            digest.update(b'(missing)')
    versions = {'python': sys.version}
    for name in ('jlpt-notes', 'mkdocs', 'mkdocs-material', 'bleach', 'watchdog', 'Markdown', 'Jinja2', 'pymdown-extensions', 'PyYAML'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = '(missing)'
    digest.update(json.dumps(versions, sort_keys=True).encode())
    return digest.hexdigest()


def input_fingerprint(source_root: Path, config_path: Path, *, compatibility: str | None = None) -> str:
    """Strong content fingerprint independent of file size and modification time."""
    root = Path(source_root).resolve(strict=True)
    digest = sha256(str(root).encode('utf-8'))
    digest.update((compatibility or configuration_fingerprint(config_path)).encode())
    for path in iter_supported_visible_source_files(root, suffixes=_SOURCE_SUFFIXES):
        relative = path.relative_to(root)
        if path.suffix.lower() in {'.txt', '.json'} and not is_evidence_path(relative):
            continue
        digest.update(relative.as_posix().encode('utf-8') + b'\0')
        digest.update(_digest_file(path).encode())
    git = _git_state_stamp(root)
    if git is None and any((parent / '.git').exists() for parent in (root, *root.parents)):
        raise ValueError('Git state unavailable; cache cannot be trusted')
    digest.update(repr(git).encode('utf-8'))
    return digest.hexdigest()


def _inventory(root: Path) -> dict[str, list]:
    files = {}
    if _linked(root) or not root.is_dir():
        raise ValueError('Cache site must be a real directory')
    for path in sorted(root.rglob('*')):
        if _linked(path):
            raise ValueError('Cache refuses site symlinks')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = [path.stat().st_size, _digest_file(path)]
        elif not path.is_dir():
            raise ValueError('Cache refuses special files')
    version = json.loads((root / 'reader-version.json').read_text(encoding='utf-8'))
    search = json.loads((root / 'search/search_index.json').read_text(encoding='utf-8'))
    if not isinstance(version.get('version'), str) or not version['version'] or not isinstance(version.get('pages'), dict):
        raise ValueError('Cache generation manifest is incomplete')
    if 'index.html' not in files or not isinstance(search.get('docs'), list):
        raise ValueError('Cache site is incomplete')
    return files


class ReaderCache:
    """Serialize cache access; lease copies before releasing the global lock."""

    def __init__(self, source_root: Path, config_path: Path, *, directory: Path | None = None,
                 max_bytes: int = 3 * 1024**3, max_versions: int = 2):
        if max_bytes <= 0 or max_versions < 1:
            raise ValueError('Cache capacity and version count must be positive')
        xdg = os.environ.get('XDG_CACHE_HOME', '')
        default = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / '.cache'
        self.directory = Path(directory) if directory is not None else default / 'jlpt-reader'
        self.source = Path(source_root).resolve()
        self.config = Path(config_path).resolve()
        self.key = sha256((str(self.source) + '\0' + str(self.config)).encode('utf-8')).hexdigest()
        self.project = self.directory / self.key
        self.max_bytes = max_bytes
        self.max_versions = max_versions
        self.last_result: BuildResult | None = None
        self.last_signature: str | None = None

    def _owned(self, path: Path) -> bool:
        marker = path / _MARKER
        try:
            return (not _linked(path) and path.is_dir() and not _linked(marker)
                    and marker.is_file() and marker.stat().st_size == len(_OWNER)
                    and marker.read_bytes() == _OWNER)
        except OSError:
            return False

    @contextmanager
    def _locked(self):
        resolved = self.directory.resolve(strict=False)
        if resolved == self.source or self.source in resolved.parents:
            raise ValueError('Cache directory must be outside learning data')
        if _linked(self.directory):
            raise ValueError('Cache root must not be a symlink')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.directory / _MARKER
        if not marker.exists():
            if any(self.directory.iterdir()):
                raise ValueError('Refusing an unowned cache directory')
            marker.write_bytes(_OWNER)
        if not self._owned(self.directory):
            raise ValueError('Cache ownership marker is invalid')
        lock_path = self.directory / '.cache.lock'
        if _linked(lock_path):
            raise ValueError('Cache lock must not be a symlink')
        lock = _OwnerLock(lock_path)
        if not lock.try_acquire():
            lock.close()
            raise BlockingIOError('Reader cache is in use')
        try:
            yield
        finally:
            lock.close()

    def _ensure_project(self):
        if self.project.exists() and not self._owned(self.project):
            raise ValueError('Refusing an unowned cache project')
        self.project.mkdir(mode=0o700, exist_ok=True)
        (self.project / _MARKER).write_bytes(_OWNER)

    def _current(self, project: Path) -> Path | None:
        try:
            pointer = project / 'current.json'
            if _linked(pointer):
                return None
            data = json.loads(pointer.read_text(encoding='utf-8'))
            name = data.get('generation', '')
            if not isinstance(name, str) or not _GENERATION.fullmatch(name) or not name.startswith('generation-'):
                return None
            candidate = project / name
            return candidate if self._owned(candidate) else None
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def _projects(self):
        return [path for path in self.directory.iterdir() if _KEY.fullmatch(path.name) and self._owned(path)]

    def _generations(self, project: Path):
        return sorted((path for path in project.iterdir() if path.name.startswith('generation-')
                       and _GENERATION.fullmatch(path.name) and self._owned(path)),
                      key=lambda path: path.stat().st_mtime_ns, reverse=True)

    def _usage(self) -> int:
        """Count unique regular-file bytes, including candidates and foreign files."""
        total = 0
        seen = set()
        for directory, names, files in os.walk(self.directory, followlinks=False):
            current = Path(directory)
            names[:] = [name for name in names if not _linked(current / name)]
            for name in files:
                path = current / name
                if not _linked(path):
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    identity = (info.st_dev, info.st_ino) if info.st_ino else path
                    if identity not in seen:
                        seen.add(identity)
                        total += info.st_size
        return total

    def _remove(self, path: Path):
        if self._owned(path) and path.parent.parent == self.directory and _KEY.fullmatch(path.parent.name):
            shutil.rmtree(path)

    def _cleanup_locked(self):
        for project in self._projects():
            current = self._current(project)
            for candidate in project.iterdir():
                if candidate.name.startswith('candidate-') and _GENERATION.fullmatch(candidate.name):
                    self._remove(candidate)
                elif candidate.name.startswith('.pointer-') and candidate.is_file() and not _linked(candidate):
                    candidate.unlink()
            retained = 1 if current is not None else 0
            for generation in self._generations(project):
                if generation == current:
                    continue
                if retained < self.max_versions:
                    retained += 1
                else:
                    self._remove(generation)
        self._make_room(0)

    def _make_room(self, needed: int) -> bool:
        if self._usage() + needed <= self.max_bytes:
            return True
        obsolete = [generation for project in self._projects() for generation in self._generations(project)
                    if generation != self._current(project)]
        for generation in sorted(obsolete, key=lambda path: path.stat().st_mtime_ns):
            self._remove(generation)
            if self._usage() + needed <= self.max_bytes:
                return True
        return self._usage() + needed <= self.max_bytes

    def cleanup(self) -> None:
        with self._locked():
            self._cleanup_locked()

    def clear(self) -> int:
        """Remove this project's owned generations under the same restore/write lock."""
        if not self.directory.exists():
            return 0
        with self._locked():
            if not self._owned(self.project):
                return 0
            removed = 0
            for path in self.project.iterdir():
                if _GENERATION.fullmatch(path.name) and self._owned(path):
                    self._remove(path)
                    removed += 1
            pointer = self.project / 'current.json'
            if pointer.is_file() and not _linked(pointer):
                pointer.unlink()
            return removed

    def _restore(self, destination: Path, *, signature: str | None, compatibility: str | None) -> bool:
        destination = Path(destination)
        resolved = destination.resolve(strict=False)
        if resolved == self.source or self.source in resolved.parents:
            raise ValueError('Cache cannot restore inside learning data')
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        self.last_result = None
        self.last_signature = None
        if not self.directory.exists():
            return False
        created = False
        try:
            with self._locked():
                current = self._current(self.project) if self._owned(self.project) else None
                if current is None:
                    return False
                meta_path = current / 'cache.json'
                if _linked(meta_path):
                    return False
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
                if meta.get('format') != _FORMAT or meta.get('key') != self.key:
                    return False
                if signature is not None and meta.get('signature') != signature:
                    return False
                if compatibility is not None and meta.get('compatibility') != compatibility:
                    return False
                site = current / 'site'
                if _inventory(site) != meta.get('files'):
                    return False
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Claim our output before copying; a losing restore must never
                # remove a directory created by another caller.
                destination.mkdir(mode=0o700)
                created = True
                shutil.copytree(site, destination, copy_function=shutil.copy2, dirs_exist_ok=True)
                if _inventory(destination) != meta['files']:
                    raise ValueError('Restored cache bytes differ')
                version = json.loads((destination / 'reader-version.json').read_text(encoding='utf-8'))['version']
                warnings = tuple(meta.get('warnings', ()))
                warning_log = None
                if warnings:
                    warning_log = destination.parent / f'{destination.name}.warnings.log'
                    while True:
                        try:
                            with warning_log.open('x', encoding='utf-8') as stream:
                                stream.write('\n'.join(warnings) + '\n')
                            break
                        except FileExistsError:
                            warning_log = destination.parent / f'{destination.name}.{uuid4().hex}.warnings.log'
                self.last_result = BuildResult(True, version=version, reused_pages=int(meta.get('page_count', len(meta.get('pages', ())))),
                                               warnings=warnings, log_path=warning_log)
                self.last_signature = meta['signature']
                return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            if created:
                shutil.rmtree(destination, ignore_errors=True)
            return False

    def restore(self, destination: Path, signature: str) -> bool:
        return self._restore(destination, signature=signature, compatibility=None)

    def restore_previous(self, destination: Path, compatibility: str) -> bool:
        """Restore compatible old inputs only as a private incremental build seed."""
        return self._restore(destination, signature=None, compatibility=compatibility)

    def save(self, site: Path, signature: str, *, compatibility: str | None = None,
             warnings: tuple[str, ...] = (), page_count: int | None = None) -> bool:
        candidate = None
        pointer_temp = None
        try:
            files = _inventory(Path(site))
            version = json.loads((Path(site) / 'reader-version.json').read_text(encoding='utf-8'))
            meta = {'format': _FORMAT, 'key': self.key, 'signature': signature,
                    'compatibility': compatibility or configuration_fingerprint(self.config),
                    'created_ns': time.time_ns(), 'files': files, 'pages': version['pages'],
                    'page_count': len(version['pages']) if page_count is None else page_count,
                    'warnings': list(warnings)}
            metadata = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode('utf-8')
            with self._locked():
                self._ensure_project()
                self._cleanup_locked()
                # Only the protected current generation of this project can
                # supply immutable bytes. Its actual inventory, never its saved
                # metadata, establishes which new-site files can share storage.
                current = self._current(self.project)
                previous_files = {}
                if current is not None:
                    try:
                        previous_files = _inventory(current / 'site')
                    except (OSError, ValueError, TypeError, KeyError, AttributeError):
                        pass
                shared = {name for name, record in files.items()
                          if previous_files.get(name) == record and (current / 'site' / name).lstat().st_ino}
                # Without stable inode identities accounting uses paths, so
                # copies must reserve their full size even for equal content.
                # Reserve all new bytes plus metadata, marker and pointer space
                # before copying; existing shared inodes cost no extra bytes.
                needed = sum(record[0] for name, record in files.items() if name not in shared) + len(metadata) + 512
                if not self._make_room(needed):
                    return False
                candidate = self.project / f'candidate-{uuid4().hex}'
                candidate.mkdir(mode=0o700)
                (candidate / _MARKER).write_bytes(_OWNER)
                remaining = needed - len(_OWNER)

                def copy_generated(source, target):
                    nonlocal remaining
                    name = Path(source).relative_to(site).as_posix()
                    size = files[name][0]
                    if name in shared:
                        try:
                            os.link(current / 'site' / name, target, follow_symlinks=False)
                            return target
                        except (OSError, NotImplementedError):
                            # Platforms without hardlinks may copy only after
                            # reserving additional bytes, while retaining the
                            # old current generation throughout the attempt.
                            if not self._make_room(remaining + size):
                                raise ValueError('Cache hardlink fallback exceeds capacity') from None
                            remaining += size
                    result = shutil.copy2(source, target)
                    remaining -= size
                    return result

                shutil.copytree(site, candidate / 'site', copy_function=copy_generated)
                if _inventory(candidate / 'site') != files:
                    raise ValueError('Site changed while caching')
                (candidate / 'cache.json').write_bytes(metadata)
                if self._usage() + 128 > self.max_bytes:
                    raise ValueError('Cache capacity exceeded')
                generation = self.project / f'generation-{uuid4().hex}'
                os.replace(candidate, generation)
                candidate = generation
                pointer_temp = self.project / f'.pointer-{uuid4().hex}'
                pointer_temp.write_text(json.dumps({'generation': generation.name}), encoding='utf-8')
                os.replace(pointer_temp, self.project / 'current.json')
                candidate = None
                pointer_temp = None
                self._cleanup_locked()
                return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            if candidate is not None:
                self._remove(candidate)
            if pointer_temp is not None:
                pointer_temp.unlink(missing_ok=True)
            return False
