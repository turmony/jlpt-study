import os
import subprocess
import time
from threading import Event
from unittest.mock import patch

from watchdog.events import (
    DirMovedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemMovedEvent,
)

from jlpt_notes.reader.watcher import SourceWatcher, snapshot_sources


def wait_until(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def git(root, *args):
    subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)


def test_strong_snapshot_detects_same_metadata_edit_and_extra_config(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    card = root / '文法.md'
    card.write_text('old')
    config = tmp_path / 'mkdocs.yml'
    config.write_text('one')
    original_stat = card.stat()
    before = snapshot_sources(root, extra_paths=(config,), content_hashes=True)
    card.write_text('new')
    os.utime(card, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    after = snapshot_sources(root, extra_paths=(config,), content_hashes=True)
    assert after != before
    config.write_text('two')
    assert snapshot_sources(root, extra_paths=(config,), content_hashes=True) != after


def test_one_snapshot_traversal_covers_docs_images_and_evidence(tmp_path):
    (tmp_path / 'quizzes' / 'sources').mkdir(parents=True)
    for name in ('card.md', 'events.jsonl', 'picture.png', 'quizzes/sources/proof.json'):
        (tmp_path / name).write_text('data')
    (tmp_path / 'other.json').write_text('ignored')
    from jlpt_notes.reader import sources
    original = sources.os.walk
    walks = []
    def walk(*args, **kwargs):
        walks.append(args[0])
        return original(*args, **kwargs)
    with patch.object(sources.os, 'walk', walk):
        result = snapshot_sources(tmp_path)
    assert {stamp.path for stamp in result} == {
        'card.md', 'events.jsonl', 'picture.png', 'quizzes/sources/proof.json'}
    assert len(walks) == 1


def test_extra_directory_watches_templates_and_ignores_python_cache(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    resources = tmp_path / 'templates'
    resources.mkdir()
    template = resources / 'page.html'
    template.write_text('old')
    (resources / '__pycache__').mkdir()
    compiled = resources / '__pycache__' / 'module.pyc'
    compiled.write_text('old cache')
    baseline = snapshot_sources(root, extra_paths=(resources,), content_hashes=True)
    compiled.write_text('new cache')
    assert snapshot_sources(root, extra_paths=(resources,), content_hashes=True) == baseline
    calls = []
    watcher = SourceWatcher(root, lambda: calls.append(True), extra_paths=(resources,),
                            debounce_seconds=0.03)
    watcher.start()
    try:
        compiled.write_text('another cache')
        time.sleep(0.15)
        assert calls == []
        template.write_text('new')
        wait_until(lambda: calls == [True])
    finally:
        watcher.stop()


def test_initially_missing_extra_directory_gets_recursive_notifications(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    resources = tmp_path / 'overrides'
    calls = []
    watcher = SourceWatcher(root, lambda: calls.append(True), extra_paths=(resources,),
                            debounce_seconds=0.03)
    watcher.start()
    try:
        (resources / 'nested').mkdir(parents=True)
        template = resources / 'nested' / 'page.html'
        template.write_text('first')
        wait_until(lambda: calls == [True])
        template.write_text('second')
        wait_until(lambda: calls == [True, True])
    finally:
        watcher.stop()


def test_native_unicode_create_rename_directory_move_and_delete(tmp_path):
    calls = []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(time.monotonic()), debounce_seconds=0.03)
    watcher.start()
    try:
        folder = tmp_path / '旧'
        folder.mkdir()
        card = folder / '文法.md'
        card.write_text('created')
        wait_until(lambda: len(calls) == 1)
        card.rename(folder / '新.md')
        wait_until(lambda: len(calls) == 2)
        folder.rename(tmp_path / '新')
        wait_until(lambda: len(calls) == 3)
        (tmp_path / '新' / '新.md').unlink()
        wait_until(lambda: len(calls) == 4)
    finally:
        watcher.stop()


def test_events_during_initial_build_and_callback_are_retained(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('initial')
    entered, release = Event(), Event()
    calls = []
    def callback():
        calls.append(card.read_text())
        if len(calls) == 1:
            entered.set()
            release.wait(3)
    watcher = SourceWatcher(tmp_path, callback, debounce_seconds=0.03)
    watcher.prepare()
    card.write_text('during initial build')
    watcher.start()
    try:
        assert entered.wait(3)
        card.write_text('during callback')
        time.sleep(0.15)
        release.set()
        wait_until(lambda: len(calls) == 2)
        assert calls == ['during initial build', 'during callback']
    finally:
        release.set()
        watcher.stop()


def test_idle_native_mode_does_not_full_scan_and_ignores_reads_hidden_and_other_files(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('initial')
    calls, scans = [], []
    original = snapshot_sources
    def snapshot(*args, **kwargs):
        scans.append(time.monotonic())
        return original(*args, **kwargs)
    with patch('jlpt_notes.reader.watcher.snapshot_sources', snapshot):
        watcher = SourceWatcher(tmp_path, lambda: calls.append(True), reconcile_seconds=60)
        watcher.start()
        try:
            baseline_scans = len(scans)
            card.read_text()
            (tmp_path / '.hidden.md').write_text('hidden')
            (tmp_path / 'unrelated.txt').write_text('unsupported')
            time.sleep(0.7)
            assert len(scans) == baseline_scans
            assert calls == []
        finally:
            watcher.stop()


def test_git_only_commit_and_external_config_trigger_native_changes(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    card = root / 'card.md'
    card.write_text('unchanged')
    config = tmp_path / 'mkdocs.yml'
    config.write_text('first')
    git(tmp_path, 'init')
    git(tmp_path, 'config', 'user.name', 'Reader Test')
    git(tmp_path, 'config', 'user.email', 'reader@example.invalid')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-m', 'initial')
    calls = []
    watcher = SourceWatcher(root, lambda: calls.append(True), extra_paths=(config,), debounce_seconds=0.05)
    watcher.start()
    try:
        git(tmp_path, 'commit', '--allow-empty', '-m', 'submission state only')
        wait_until(lambda: len(calls) == 1)
        config.write_text('second')
        wait_until(lambda: len(calls) == 2)
        time.sleep(0.3)
        assert len(calls) == 2  # Git status must not cause an index-write loop.
    finally:
        watcher.stop()


class SilentObserver:
    """Healthy notification backend which intentionally drops all events."""
    def __init__(self):
        self.alive = False
        self.emitters = [self]

    def schedule(self, handler, path, *, recursive):
        pass

    def start(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def join(self, timeout=None):
        pass

    def is_alive(self):
        return self.alive


def test_reconcile_uses_content_fingerprints_at_60_seconds_without_events(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    stamp = card.stat()
    calls = []
    now = [0.0]
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    card.write_text('new')
    os.utime(card, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    watcher.start()
    try:
        now[0] = 59.9
        watcher._service_once(now[0])
        assert calls == []
        now[0] = 60.0
        watcher._service_once(now[0])
        wait_until(lambda: calls)
        now[0] = 120.0
        watcher._service_once(now[0])
        time.sleep(0.1)
        assert len(calls) == 1
    finally:
        watcher.stop()


def test_dead_native_emitter_is_reported_and_changed_content_recovered(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    calls, errors = [], []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), on_error=errors.append,
                            debounce_seconds=0.01)
    watcher.start()
    try:
        observer = watcher._observer
        for emitter in observer.emitters:
            emitter.stop()
            emitter.join()
        card.write_text('new')
        wait_until(lambda: calls, seconds=3)
        assert errors
        wait_until(lambda: watcher._observer is not None and watcher._observer is not observer)
        card.write_text('new after recovery')
        wait_until(lambda: len(calls) == 2)
    finally:
        watcher.stop()


def test_observer_start_failure_does_not_leave_orphan_listener(tmp_path):
    observer = SilentObserver()
    def failed_start():
        observer.alive = True
        raise OSError('started only some watches')
    observer.start = failed_start
    errors = []
    watcher = SourceWatcher(tmp_path, lambda: None, observer_factory=lambda: observer,
                            on_error=errors.append)
    watcher.prepare()
    try:
        assert errors
        assert not observer.is_alive()
    finally:
        watcher.stop()


def test_reconciliation_does_not_bypass_recent_event_debounce(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    now = [0.0]
    calls = []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    try:
        now[0] = 59.9
        card.write_text('new')
        watcher._notice_event()
        now[0] = 60.0
        watcher._service_once(now[0])
        watcher.start()
        time.sleep(0.1)
        assert calls == []
        now[0] = 60.5
        watcher._service_once(now[0])
        wait_until(lambda: calls == [True])
    finally:
        watcher.stop()


def test_snapshot_failure_keeps_dirty_state_but_backs_off_retries(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    now = [0.0]
    errors = []
    calls = []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), clock=lambda: now[0],
                            observer_factory=SilentObserver, on_error=errors.append)
    watcher.prepare()
    try:
        card.write_text('new')
        watcher._notice_event()
        now[0] = 1.0
        with patch('jlpt_notes.reader.watcher.snapshot_sources', side_effect=OSError('unreadable')):
            watcher._service_once(now[0])
            now[0] = 1.1
            watcher._service_once(now[0])
        assert len(errors) == 1
        now[0] = 2.0
        watcher._service_once(now[0])
        watcher.start()
        wait_until(lambda: calls == [True])
    finally:
        watcher.stop()


def test_native_failure_falls_back_to_polling_and_reports_error(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    calls, errors = [], []
    def unavailable():
        raise OSError('no native observer')
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), observer_factory=unavailable,
                            debounce_seconds=0.01, on_error=errors.append)
    watcher.start()
    try:
        card.write_text('new')
        wait_until(lambda: calls, seconds=3)
        assert errors and 'no native observer' in errors[0]
    finally:
        watcher.stop()


def test_false_and_exception_callbacks_retry_without_new_edit(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    attempts, errors = [], []
    def callback():
        attempts.append(True)
        if len(attempts) == 1:
            return False
        if len(attempts) == 2:
            raise RuntimeError('build failed')
    watcher = SourceWatcher(tmp_path, callback, debounce_seconds=0.01, on_error=errors.append)
    watcher.start()
    try:
        card.write_text('new')
        wait_until(lambda: len(attempts) == 3, seconds=4)
        assert len(errors) == 1
        time.sleep(0.2)
        assert len(attempts) == 3
    finally:
        watcher.stop()


def test_stop_is_prompt_even_with_blocked_callback(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    entered, release = Event(), Event()
    def callback():
        entered.set()
        release.wait(3)
    watcher = SourceWatcher(tmp_path, callback, debounce_seconds=0.01)
    watcher.start()
    try:
        card.write_text('new')
        assert entered.wait(3)
        before = time.monotonic()
        watcher.stop()
        assert time.monotonic() - before < 0.5
        assert not watcher.is_running
    finally:
        release.set()
        watcher.stop()


def test_file_event_hashes_only_changed_file_and_60_seconds_still_full_scans(tmp_path):
    for number in range(100):
        (tmp_path / f'card-{number}.md').write_text('old')
    card = tmp_path / 'card-42.md'
    now = [0.0]
    watcher = SourceWatcher(tmp_path, lambda: None, clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    before = card.stat()
    read_paths = []
    path_type = type(card)
    original_read = path_type.read_bytes
    original_snapshot = snapshot_sources
    scans = []
    def read(path):
        read_paths.append(path)
        return original_read(path)
    def snapshot(*args, **kwargs):
        scans.append(True)
        return original_snapshot(*args, **kwargs)
    from jlpt_notes.reader.watcher import _EventHandler
    try:
        card.write_text('new')
        os.utime(card, ns=(before.st_atime_ns, before.st_mtime_ns))
        _EventHandler(watcher).on_any_event(FileModifiedEvent(str(card)))
        now[0] = 1.0
        with patch('jlpt_notes.reader.watcher.snapshot_sources', snapshot), patch.object(path_type, 'read_bytes', read):
            watcher._service_once(now[0])
            assert scans == []
            assert read_paths == [card]
            updated = next(stamp for stamp in watcher._latest if stamp.path == 'card-42.md')
            from hashlib import sha256
            assert updated.digest == sha256(b'new').hexdigest()
            now[0] = 60.0
            watcher._service_once(now[0])
            assert scans == [True]
            assert len(read_paths) == 101
    finally:
        watcher.stop()


def test_snapshot_deduplicates_overlapping_extra_directory_and_file(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    resources = tmp_path / 'assets'
    resources.mkdir()
    script = resources / 'reader.js'
    script.write_text('asset')
    baseline = snapshot_sources(root, extra_paths=(resources, script, resources, script), content_hashes=True)
    assert len(baseline) == 1


def test_path_batch_rename_delete_and_git_state_match_full_snapshot(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    card = root / 'old.md'
    card.write_text('old')
    config = tmp_path / 'mkdocs.yml'
    config.write_text('old')
    git(tmp_path, 'init')
    git(tmp_path, 'config', 'user.name', 'Reader Test')
    git(tmp_path, 'config', 'user.email', 'reader@example.invalid')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-m', 'initial')
    now = [0.0]
    watcher = SourceWatcher(root, lambda: None, clock=lambda: now[0], extra_paths=(config,),
                            observer_factory=SilentObserver)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    handler = _EventHandler(watcher)
    try:
        renamed = root / 'new.md'
        card.rename(renamed)
        handler.on_any_event(FileSystemMovedEvent(str(card), str(renamed)))
        config.write_text('new')
        handler.on_any_event(FileModifiedEvent(str(config)))
        now[0] = 1.0
        with patch('jlpt_notes.reader.watcher.snapshot_sources', side_effect=AssertionError('ordinary event full-scanned')):
            watcher._service_once(now[0])
        assert watcher._latest == snapshot_sources(root, extra_paths=(config,), content_hashes=True)
        renamed.unlink()
        handler.on_any_event(FileModifiedEvent(str(renamed)))
        git(tmp_path, 'commit', '--allow-empty', '-m', 'git only')
        handler.on_any_event(FileModifiedEvent(str(tmp_path / '.git' / 'refs' / 'heads' / 'master')))
        now[0] = 2.0
        with patch('jlpt_notes.reader.watcher.snapshot_sources', side_effect=AssertionError('ordinary event full-scanned')):
            watcher._service_once(now[0])
        assert watcher._latest == snapshot_sources(root, extra_paths=(config,), content_hashes=True)
    finally:
        watcher.stop()


def test_directory_unknown_and_pending_path_overflow_force_full_resync(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('old')
    now = [0.0]
    watcher = SourceWatcher(tmp_path, lambda: None, clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    handler = _EventHandler(watcher)
    scans = []
    original = snapshot_sources
    def snapshot(*args, **kwargs):
        scans.append(True)
        return original(*args, **kwargs)
    try:
        with patch('jlpt_notes.reader.watcher.snapshot_sources', snapshot):
            handler.on_any_event(DirMovedEvent(str(tmp_path / 'old'), str(tmp_path / 'new')))
            now[0] = 1.0
            watcher._service_once(now[0])
            assert len(scans) == 1
            handler.on_any_event(FileSystemEvent(''))
            now[0] = 2.0
            watcher._service_once(now[0])
            assert len(scans) == 2
            for number in range(5000):
                handler.on_any_event(FileModifiedEvent(str(tmp_path / f'absent-{number}.md')))
            assert len(watcher._pending_paths) <= 4096
            card.write_text('new')
            now[0] = 3.0
            watcher._service_once(now[0])
            assert len(scans) == 3
        assert watcher._latest == snapshot_sources(tmp_path, content_hashes=True)
    finally:
        watcher.stop()


def test_event_arriving_while_path_hash_runs_is_not_consumed(tmp_path):
    first = tmp_path / 'first.md'
    second = tmp_path / 'second.md'
    first.write_text('old')
    second.write_text('old')
    now = [0.0]
    watcher = SourceWatcher(tmp_path, lambda: None, clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    handler = _EventHandler(watcher)
    path_type = type(first)
    original_read = path_type.read_bytes
    changed = [False]
    def read(path):
        if path == first and not changed[0]:
            changed[0] = True
            second.write_text('later')
            handler.on_any_event(FileModifiedEvent(str(second)))
        return original_read(path)
    try:
        first.write_text('new')
        handler.on_any_event(FileModifiedEvent(str(first)))
        now[0] = 1.0
        with patch.object(path_type, 'read_bytes', read):
            watcher._service_once(now[0])
        now[0] = 2.0
        watcher._service_once(now[0])
        assert watcher._latest == snapshot_sources(tmp_path, content_hashes=True)
    finally:
        watcher.stop()


def test_update_extra_paths_moves_native_watches_and_unchanged_paths_do_no_work(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    old = tmp_path / 'old-external'
    new = tmp_path / 'new-external'
    old.mkdir()
    new.mkdir()
    old_file = old / 'template.html'
    new_file = new / 'template.html'
    old_file.write_text('old')
    new_file.write_text('new')
    calls, scans = [], []
    original = snapshot_sources
    def snapshot(*args, **kwargs):
        scans.append(True)
        return original(*args, **kwargs)
    with patch('jlpt_notes.reader.watcher.snapshot_sources', snapshot):
        watcher = SourceWatcher(root, lambda: calls.append(True), extra_paths=(old,),
                                debounce_seconds=0.03)
        watcher.start()
        try:
            watcher.update_extra_paths((new,))
            wait_until(lambda: len(calls) == 1)
            new_file.write_text('edited new resource')
            wait_until(lambda: len(calls) == 2)
            old_file.write_text('removed resource')
            time.sleep(0.15)
            assert len(calls) == 2
            before_scans = len(scans)
            observer = watcher._observer
            watcher.update_extra_paths((new, new))
            time.sleep(0.15)
            assert len(scans) == before_scans
            assert watcher._observer is observer
            assert len(calls) == 2
        finally:
            watcher.stop()


def test_missed_config_edit_is_reconciled_and_callback_discovers_new_resource(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    config = tmp_path / 'mkdocs.yml'
    old = tmp_path / 'old.html'
    new = tmp_path / 'new.html'
    old.write_text('old')
    new.write_text('new')
    config.write_text(str(old))
    now = [0.0]
    calls = []
    errors = []
    def callback():
        calls.append(True)
        watcher.update_extra_paths((config, type(config)(config.read_text())))
    watcher = SourceWatcher(root, callback, extra_paths=(config, old), clock=lambda: now[0],
                            observer_factory=SilentObserver, on_error=errors.append)
    watcher.prepare()
    watcher.start()
    from jlpt_notes.reader.watcher import _EventHandler
    try:
        config.write_text(str(new))  # Backend intentionally loses the event.
        now[0] = 60.0
        watcher._service_once(now[0])
        wait_until(lambda: calls == [True])
        now[0] = 61.0
        watcher._service_once(now[0])
        wait_until(lambda: len(calls) == 2)
        new.write_text('changed new dependency')
        _EventHandler(watcher).on_any_event(FileModifiedEvent(str(new)))
        now[0] = 62.0
        watcher._service_once(now[0])
        wait_until(lambda: len(calls) == 3)
        assert errors == []
        assert f'<extra:{new}>' in {stamp.path for stamp in watcher._latest}
        assert f'<extra:{old}>' not in {stamp.path for stamp in watcher._latest}
    finally:
        watcher.stop()


def test_same_bytes_with_new_mtime_does_not_rebuild_but_next_content_edit_does(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('same')
    now = [0.0]
    calls = []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(True), clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    handler = _EventHandler(watcher)
    watcher.start()
    try:
        original = card.stat()
        card.write_text('same')
        os.utime(card, ns=(original.st_atime_ns, original.st_mtime_ns + 1_000_000))
        handler.on_any_event(FileModifiedEvent(str(card)))
        now[0] = 1.0
        watcher._service_once(now[0])
        time.sleep(0.1)
        assert calls == []
        assert watcher._latest[0].modified_ns == card.stat().st_mtime_ns
        card.write_text('next')
        handler.on_any_event(FileModifiedEvent(str(card)))
        now[0] = 2.0
        watcher._service_once(now[0])
        wait_until(lambda: calls == [True])
    finally:
        watcher.stop()


def test_extra_snapshot_and_suffix_discovery_do_not_cross_directory_junction(tmp_path):
    root = tmp_path / 'notes'
    root.mkdir()
    resource = tmp_path / 'linked-resource'
    resource.mkdir()
    secret = resource / 'secret.external'
    secret.write_text('do not read')
    from jlpt_notes.reader.watcher import _extra_suffixes
    with patch.object(type(resource), 'is_junction', lambda path: path == resource, create=True):
        assert snapshot_sources(root, extra_paths=(resource,), content_hashes=True) == ()
        assert '.external' not in _extra_suffixes(tmp_path)


def test_changed_path_rejects_reparse_parent_but_still_removes_deleted_file(tmp_path):
    folder = tmp_path / 'linked'
    folder.mkdir()
    card = folder / 'card.md'
    card.write_text('old')
    now = [0.0]
    watcher = SourceWatcher(tmp_path, lambda: None, clock=lambda: now[0],
                            observer_factory=SilentObserver)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    try:
        with patch.object(type(folder), 'is_junction', lambda path: path == folder, create=True):
            assert not watcher._relevant(card, False)
            watcher._notice_event((card,))
            now[0] = 1.0
            with patch.object(type(card), 'read_bytes', side_effect=AssertionError('read through junction')):
                watcher._service_once(now[0])
            assert watcher._latest == ()
        watcher._notice_event()
        now[0] = 2.0
        watcher._service_once(now[0])
        card.unlink()
        _EventHandler(watcher).on_any_event(FileModifiedEvent(str(card)))
        now[0] = 3.0
        watcher._service_once(now[0])
        assert watcher._latest == ()
    finally:
        watcher.stop()


def test_build_change_token_forces_retry_after_a_b_a_without_idle_touch_rebuild(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('A')
    calls = []
    watcher = SourceWatcher(tmp_path, lambda: calls.append(card.read_text()),
                            observer_factory=SilentObserver, debounce_seconds=0.03)
    watcher.prepare()
    from jlpt_notes.reader.watcher import _EventHandler
    handler = _EventHandler(watcher)
    try:
        token = watcher.change_token
        assert watcher.ensure_rebuild_after(token)
        card.write_text('B')
        handler.on_any_event(FileModifiedEvent(str(card)))
        card.write_text('A')
        handler.on_any_event(FileModifiedEvent(str(card)))
        assert watcher.change_token > token
        assert not watcher.ensure_rebuild_after(token)
        watcher.start()
        wait_until(lambda: calls == ['A'])
        assert watcher.ensure_rebuild_after(watcher.change_token)
        card.write_text('A')
        handler.on_any_event(FileModifiedEvent(str(card)))
        time.sleep(0.15)
        assert calls == ['A']
    finally:
        watcher.stop()


def _forced_callback_probe(tmp_path, *, later_edit):
    card = tmp_path / 'card.md'
    card.write_text('A')
    calls, edit_times, errors = [], [], []
    ready = Event()
    def callback():
        calls.append((time.monotonic(), card.read_text()))
        if len(calls) == 1:
            token = watcher.change_token
            card.write_text('C')
            edit_times.append(time.monotonic())
            wait_until(lambda: watcher.change_token > token)
            assert not watcher.ensure_rebuild_after(token)
            ready.set()
        return True
    watcher = SourceWatcher(tmp_path, callback, on_error=errors.append)
    watcher.start()
    try:
        card.write_text('B')
        assert ready.wait(3)
        if later_edit:
            time.sleep(0.2)
            card.write_text('D')
            edit_times.append(time.monotonic())
        wait_until(lambda: len(calls) >= 2)
        assert errors == []
        assert calls[1][0] - edit_times[-1] >= 0.48
        assert calls[1][1] == ('D' if later_edit else 'C')
        time.sleep(0.6)
        assert [value for _, value in calls] == ['B', 'D' if later_edit else 'C']
    finally:
        watcher.stop()


def test_successful_callback_preserves_forced_native_event_debounce(tmp_path):
    _forced_callback_probe(tmp_path, later_edit=False)


def test_new_edit_extends_forced_native_callback_debounce(tmp_path):
    _forced_callback_probe(tmp_path, later_edit=True)


def test_forced_native_callback_waits_for_pending_snapshot_and_runs_only_once(tmp_path):
    card = tmp_path / 'card.md'
    card.write_text('A')
    calls, errors = [], []
    ready, scan_entered, release_scan = Event(), Event(), Event()
    def callback():
        calls.append(card.read_text())
        if len(calls) == 1:
            token = watcher.change_token
            card.write_text('C')
            wait_until(lambda: watcher.change_token > token)
            assert not watcher.ensure_rebuild_after(token)
            ready.set()
        return True
    path_type = type(card)
    original_read = path_type.read_bytes
    def read(path):
        if path == card and card.read_text() == 'D':
            scan_entered.set()
            release_scan.wait(3)
        return original_read(path)
    watcher = SourceWatcher(tmp_path, callback, on_error=errors.append)
    with patch.object(path_type, 'read_bytes', read):
        watcher.start()
        try:
            card.write_text('B')
            assert ready.wait(3)
            time.sleep(0.2)
            card.write_text('D')
            assert scan_entered.wait(3)
            time.sleep(0.2)
            assert calls == ['B']  # A settled but unverified batch is still pending.
            release_scan.set()
            wait_until(lambda: calls == ['B', 'D'])
            time.sleep(0.6)
            assert calls == ['B', 'D']
            assert errors == []
        finally:
            release_scan.set()
            watcher.stop()
