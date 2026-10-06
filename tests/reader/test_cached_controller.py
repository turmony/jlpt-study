"""Real builds prove cross-launch reuse and stale-input invalidation."""

import json
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

from jlpt_notes.reader.builder import build_site
from jlpt_notes.reader.controller import ReaderController

from .test_controller import _FakeServer


class _ManualWatcher:
    instances: ClassVar[list] = []

    def __init__(self, root, callback, **kwargs):
        self.callback = callback
        self.prepared = False
        self.started = False
        self.change_token = 0
        self.retry_requested = False
        self.extra_paths = kwargs.get('extra_paths', ())
        self.instances.append(self)

    def prepare(self):
        self.prepared = True

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def update_extra_paths(self, paths):
        self.extra_paths = paths

    def ensure_rebuild_after(self, token):
        self.retry_requested = self.change_token != token
        return not self.retry_requested


class CachedControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.notes = self.base / 'notes'
        self.notes.mkdir()
        self.card = self.notes / 'card.md'
        self.card.write_text('# Card\n\nfirst contents\n', encoding='utf-8')
        project = Path(__file__).resolve().parents[2]
        shutil.copytree(project / 'reader', self.base / 'reader')
        self.config = self.base / 'reader/mkdocs.yml'
        self.cache_dir = self.base / 'cache'
        _ManualWatcher.instances.clear()
        self.server_patch = patch('jlpt_notes.reader.controller.ReadOnlyServer', _FakeServer)
        self.watcher_patch = patch('jlpt_notes.reader.controller.SourceWatcher', _ManualWatcher)
        self.server_patch.start()
        self.watcher_patch.start()
        self.addCleanup(self.server_patch.stop)
        self.addCleanup(self.watcher_patch.stop)

    def controller(self):
        return ReaderController(self.notes, self.config, Path(sys.executable), local_only=True,
                                cache_directory=self.cache_dir)

    def test_second_launch_restores_verified_pages_without_building(self):
        with patch('jlpt_notes.reader.controller.build_site', wraps=build_site) as builds:
            first = self.controller()
            self.addCleanup(first.stop)
            self.assertTrue(first.start())
            original = (first._store.current / 'index.html').read_bytes()
            first.stop()
            second = self.controller()
            self.addCleanup(second.stop)
            self.assertTrue(second.start())
            self.assertEqual(builds.call_count, 1)
            self.assertEqual((second._store.current / 'index.html').read_bytes(), original)
            self.assertTrue(_ManualWatcher.instances[-1].prepared)

    def test_changed_inputs_rebuild_with_old_cache_as_private_seed(self):
        with patch('jlpt_notes.reader.controller.build_site', wraps=build_site) as builds:
            first = self.controller()
            self.assertTrue(first.start())
            first.stop()
            self.card.write_text('# Card\n\nupdated contents\n', encoding='utf-8')
            second = self.controller()
            self.addCleanup(second.stop)
            self.assertTrue(second.start())
            self.assertEqual(builds.call_count, 2)
            self.assertIsNotNone(builds.call_args.kwargs.get('previous_site'))
            pages = '\n'.join(path.read_text(encoding='utf-8') for path in second._store.current.rglob('index.html'))
            self.assertIn('updated contents', pages)

    def test_incompatible_configuration_performs_full_build(self):
        with patch('jlpt_notes.reader.controller.build_site', wraps=build_site) as builds:
            first = self.controller()
            self.assertTrue(first.start())
            first.stop()
            with self.config.open('a', encoding='utf-8') as stream:
                stream.write('\nsite_name: upgraded fixture\n')
            second = self.controller()
            self.addCleanup(second.stop)
            self.assertTrue(second.start())
            self.assertEqual(builds.call_count, 2)
            self.assertIsNone(builds.call_args.kwargs.get('previous_site'))

    def test_cache_unavailable_does_not_prevent_start(self):
        self.cache_dir.mkdir()
        (self.cache_dir / 'unrelated.txt').write_text('keep me')
        controller = self.controller()
        self.addCleanup(controller.stop)
        self.assertTrue(controller.start())
        self.assertEqual((self.cache_dir / 'unrelated.txt').read_text(), 'keep me')

    def test_live_inherited_config_change_rebuilds_before_caching_new_compatibility(self):
        inherited = self.config.parent / 'base.yml'
        inherited.write_text('site_name: FIRST_NAME\n')
        text = self.config.read_text(encoding='utf-8')
        self.config.write_text('INHERIT: base.yml\n' + '\n'.join(
            line for line in text.splitlines() if not line.startswith('site_name:')) + '\n')
        controller = self.controller()
        self.addCleanup(controller.stop)
        with patch('jlpt_notes.reader.controller.build_site', wraps=build_site) as builds:
            self.assertTrue(controller.start())
            inherited.write_text('site_name: SECOND_NAME\n')
            self.assertTrue(controller.rebuild())
            self.assertIsNone(builds.call_args.kwargs.get('previous_site'))
            rendered = '\n'.join(p.read_text() for p in controller._store.current.rglob('index.html'))
            self.assertIn('SECOND_NAME', rendered)
            controller.stop()
            restarted = self.controller()
            self.addCleanup(restarted.stop)
            self.assertTrue(restarted.start())
            self.assertEqual(builds.call_count, 2)
            self.assertIn('SECOND_NAME', (restarted._store.current / 'index.html').read_text())

    def test_failed_update_retains_successful_site_and_cached_version(self):
        controller = self.controller()
        self.addCleanup(controller.stop)
        self.assertTrue(controller.start())
        before = json.loads((controller._store.current / 'reader-version.json').read_text())['version']
        self.card.write_bytes(b'\xff\xfe')
        self.assertFalse(controller.rebuild())
        after = json.loads((controller._store.current / 'reader-version.json').read_text())['version']
        self.assertEqual(after, before)
        cached = next(self.cache_dir.rglob('reader-version.json'))
        self.assertEqual(json.loads(cached.read_text())['version'], before)

    def test_edit_during_initial_build_is_never_saved_as_matching_cache(self):
        def build_with_edit(*args, **kwargs):
            self.assertTrue(_ManualWatcher.instances[-1].prepared)
            result = build_site(*args, **kwargs)
            self.card.write_text('# Card\n\nedited during build\n', encoding='utf-8')
            return result
        controller = self.controller()
        self.addCleanup(controller.stop)
        with patch('jlpt_notes.reader.controller.build_site', side_effect=build_with_edit):
            self.assertTrue(controller.start())
        self.assertEqual(list(self.cache_dir.rglob('reader-version.json')), [])
        self.assertTrue(controller.rebuild())
        self.assertEqual(len(list(self.cache_dir.rglob('reader-version.json'))), 1)

    def test_hourly_cleanup_runs_after_timeout_and_collects_abandoned_candidate(self):
        controller = self.controller()
        self.addCleanup(controller.stop)
        self.assertTrue(controller.start())
        controller.stop()
        generation = next(path.parent for path in self.cache_dir.rglob('cache.json'))
        abandoned = generation.parent / ('candidate-' + 'f' * 32)
        shutil.copytree(generation, abandoned)
        # A stop before the first hourly timeout must leave cleanup untouched.
        controller._cache_maintenance()
        self.assertTrue(abandoned.exists())
        with patch.object(controller._maintenance_stop, 'wait', side_effect=[False, True]):
            controller._cache_maintenance()
        self.assertFalse(abandoned.exists())
        self.assertTrue(generation.exists())

    def test_transient_edit_during_build_never_poisons_exact_cache(self):
        original = self.card.read_bytes()
        def transient_build(*args, **kwargs):
            self.card.write_text('# Card\n\nTRANSIENT_CONTENT\n')
            watcher = _ManualWatcher.instances[-1]
            watcher.change_token += 1
            result = build_site(*args, **kwargs)
            self.card.write_bytes(original)
            watcher.change_token += 1
            return result
        controller = self.controller()
        self.addCleanup(controller.stop)
        with patch('jlpt_notes.reader.controller.build_site', side_effect=transient_build):
            self.assertTrue(controller.start())
        self.assertEqual(list(self.cache_dir.rglob('reader-version.json')), [])
        self.assertTrue(_ManualWatcher.instances[-1].retry_requested)
        self.assertTrue(controller.rebuild())
        controller.stop()
        restarted = self.controller()
        self.addCleanup(restarted.stop)
        with patch('jlpt_notes.reader.controller.build_site', wraps=build_site) as builds:
            self.assertTrue(restarted.start())
            self.assertEqual(builds.call_count, 0)
        pages = '\n'.join(p.read_text() for p in restarted._store.current.rglob('index.html'))
        self.assertIn('first contents', pages)
        self.assertNotIn('TRANSIENT_CONTENT', pages)

    def test_live_new_hook_is_registered_for_future_monitoring(self):
        controller = self.controller()
        self.addCleanup(controller.stop)
        self.assertTrue(controller.start())
        hook = self.config.parent / 'new-hook.py'
        hook.write_text('def on_post_build(config):\n    pass\n')
        with self.config.open('a') as stream:
            stream.write('\nhooks:\n  - new-hook.py\n')
        self.assertTrue(controller.rebuild())
        self.assertIn(hook, _ManualWatcher.instances[-1].extra_paths)
