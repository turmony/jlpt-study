"""Persistent cache must never publish stale bytes or delete foreign files."""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ReaderCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.notes = self.base / 'notes'
        self.notes.mkdir()
        self.card = self.notes / '中文 卡片.md'
        self.card.write_text('# 最初\n', encoding='utf-8')
        self.reader = self.base / 'reader'
        self.reader.mkdir()
        self.config = self.reader / 'mkdocs.yml'
        self.config.write_text('site_name: fixture\n', encoding='utf-8')
        self.site = self.base / 'site'
        self.site.mkdir()
        self.cache_dir = self.base / 'cache'

    def api(self):
        try:
            from jlpt_notes.reader.cache import ReaderCache, input_fingerprint
        except ImportError as error:
            self.fail(f'Persistent verified cache is missing: {error}')
        return ReaderCache, input_fingerprint

    def write_site(self, version='v1', text='first'):
        (self.site / 'index.html').write_text(text, encoding='utf-8')
        (self.site / 'reader-version.json').write_text(
            json.dumps({'version': version, 'pages': {'': version}}), encoding='utf-8')
        (self.site / 'search').mkdir(exist_ok=True)
        (self.site / 'search/search_index.json').write_text('{"docs":[]}', encoding='utf-8')

    def test_restore_exact_success_survives_a_new_cache_instance(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        original = (self.card.read_bytes(), self.card.stat().st_mtime_ns)
        self.assertTrue(cache.save(self.site, signature))
        restored = self.base / 'restored'
        self.assertTrue(ReaderCache(self.notes, self.config, directory=self.cache_dir).restore(restored, signature))
        self.assertEqual((restored / 'index.html').read_text(), 'first')
        (restored / 'index.html').write_text('modified session', encoding='utf-8')
        second = self.base / 'second'
        self.assertTrue(cache.restore(second, signature))
        self.assertEqual((second / 'index.html').read_text(), 'first')
        self.assertEqual((self.card.read_bytes(), self.card.stat().st_mtime_ns), original)

    def test_same_size_and_restored_mtime_input_is_not_reused(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        before = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, before))
        modified = self.card.stat().st_mtime_ns
        self.card.write_text('# 修改\n', encoding='utf-8')
        os.utime(self.card, ns=(modified, modified))
        after = fingerprint(self.notes, self.config)
        self.assertNotEqual(before, after)
        self.assertFalse(cache.restore(self.base / 'restored', after))

    def test_config_asset_and_git_only_commit_invalidate_inputs(self):
        _, fingerprint = self.api()
        self._git('init')
        self._git('config', 'user.name', 'Fixture')
        self._git('config', 'user.email', 'fixture@example.invalid')
        before = fingerprint(self.notes, self.config)
        self._git('add', '--', 'notes')
        self._git('commit', '-m', 'confirm')
        committed = fingerprint(self.notes, self.config)
        self.assertNotEqual(before, committed)
        assets = self.reader / 'assets'
        assets.mkdir()
        (assets / 'reader.js').write_text('var x = 1;')
        self.assertNotEqual(committed, fingerprint(self.notes, self.config))
        current = fingerprint(self.notes, self.config)
        self.config.write_text('site_name: changed\n')
        self.assertNotEqual(current, fingerprint(self.notes, self.config))

    def test_corrupted_output_is_rejected_without_leaving_partial_restore(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature))
        output = next(self.cache_dir.rglob('index.html'))
        output.write_text('tampered', encoding='utf-8')
        destination = self.base / 'restored'
        self.assertFalse(cache.restore(destination, signature))
        self.assertFalse(destination.exists())

    def test_cache_keeps_two_successful_versions_and_foreign_entries(self):
        ReaderCache, fingerprint = self.api()
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        for number in range(4):
            self.write_site(f'v{number}', str(number))
            self.assertTrue(cache.save(self.site, fingerprint(self.notes, self.config)))
        foreign = self.cache_dir / 'foreign'
        foreign.mkdir()
        (foreign / 'index.html').write_text('do not delete')
        cache.cleanup()
        outputs = list(self.cache_dir.rglob('reader-version.json'))
        self.assertEqual(len(outputs), 2)
        self.assertEqual((foreign / 'index.html').read_text(), 'do not delete')
        restored = self.base / 'restored'
        self.assertTrue(cache.restore(restored, fingerprint(self.notes, self.config)))
        self.assertEqual((restored / 'index.html').read_text(), '3')

    def test_over_budget_save_keeps_old_success_and_releases_candidate(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=8000)
        signature = fingerprint(self.notes, self.config)
        self.assertTrue(cache.save(self.site, signature))
        self.write_site('v2', 'x' * 9000)
        self.assertFalse(cache.save(self.site, signature))
        restored = self.base / 'restored'
        self.assertTrue(cache.restore(restored, signature))
        self.assertEqual((restored / 'index.html').read_text(), 'first')
        self.assertEqual(len(list(self.cache_dir.rglob('reader-version.json'))), 1)

    def test_large_unchanged_asset_allows_two_generations_within_global_budget(self):
        ReaderCache, _ = self.api()
        self.write_site()
        asset = self.site / 'large.png'
        asset.write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=18000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        self.assertNotEqual((old / 'site/large.png').stat().st_ino, asset.stat().st_ino)
        self.write_site('v2', 'new html' * 100)
        self.assertTrue(cache.save(self.site, 'new', compatibility='fixture'))
        new = cache._current(cache.project)
        self.assertNotEqual(old, new)
        self.assertEqual(len(cache._generations(cache.project)), 2)
        self.assertEqual((old / 'site/large.png').stat().st_ino, (new / 'site/large.png').stat().st_ino)
        self.assertNotEqual((old / 'site/index.html').stat().st_ino, (new / 'site/index.html').stat().st_ino)
        self.assertLessEqual(cache._usage(), 18000)
        restored = self.base / 'restored'
        self.assertTrue(cache.restore(restored, 'new'))
        self.assertEqual((restored / 'index.html').read_text(), 'new html' * 100)
        self.assertNotEqual((restored / 'large.png').stat().st_ino, (new / 'site/large.png').stat().st_ino)
        (restored / 'large.png').write_bytes(b'edited session')
        self.assertEqual((old / 'site/large.png').read_bytes(), b'a' * 10000)
        self.assertEqual((new / 'site/large.png').read_bytes(), b'a' * 10000)
        cache.max_versions = 1
        cache.cleanup()
        self.assertFalse(old.exists())
        self.assertEqual((new / 'site/large.png').read_bytes(), b'a' * 10000)
        self.assertTrue(cache.restore(self.base / 'after-cleanup', 'new'))

    def test_usage_counts_unique_regular_inodes_including_foreign_files(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        ReaderCache, _ = self.api()
        self.cache_dir.mkdir()
        first = self.cache_dir / 'first'
        first.write_bytes(b'a' * 500)
        foreign = self.cache_dir / 'foreign'
        foreign.mkdir()
        os.link(first, foreign / 'shared')
        (foreign / 'different').write_bytes(b'b' * 300)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertEqual(cache._usage(), 800)
        real_lstat = Path.lstat

        def unavailable_inode(path):
            result = real_lstat(path)
            return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size,
                                   st_dev=result.st_dev, st_ino=0, st_file_attributes=0)

        with patch.object(Path, 'lstat', unavailable_inode):
            self.assertEqual(cache._usage(), 1300)

    def test_shared_asset_is_verified_from_actual_old_bytes_before_reuse(self):
        ReaderCache, _ = self.api()
        self.write_site()
        (self.site / 'large.png').write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=40000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        (old / 'site/large.png').write_bytes(b'x' * 10000)
        self.write_site('v2', 'new')
        self.assertTrue(cache.save(self.site, 'new', compatibility='fixture'))
        new = cache._current(cache.project)
        self.assertEqual((new / 'site/large.png').read_bytes(), b'a' * 10000)
        self.assertNotEqual((old / 'site/large.png').stat().st_ino, (new / 'site/large.png').stat().st_ino)
        self.assertTrue(cache.restore(self.base / 'verified', 'new'))

    def test_unavailable_inode_cannot_claim_shared_budget(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        ReaderCache, _ = self.api()
        self.write_site()
        (self.site / 'large.png').write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=18000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        self.write_site('v2', 'new')
        real_lstat, real_usage = Path.lstat, cache._usage
        observed = []

        def unavailable_inode(path):
            result = real_lstat(path)
            return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size,
                                   st_dev=result.st_dev, st_ino=0, st_file_attributes=0)

        def track_usage():
            usage = real_usage()
            observed.append(usage)
            return usage

        with patch.object(Path, 'lstat', unavailable_inode), patch.object(cache, '_usage', track_usage):
            self.assertFalse(cache.save(self.site, 'new', compatibility='fixture'))
        self.assertLessEqual(max(observed), 18000)
        self.assertEqual(cache._current(cache.project), old)
        self.assertFalse(any(cache.project.glob('candidate-*')))

    def test_corrupt_old_asset_cannot_claim_shared_budget(self):
        ReaderCache, _ = self.api()
        self.write_site()
        (self.site / 'large.png').write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=18000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        (old / 'site/large.png').write_bytes(b'x' * 10000)
        self.write_site('v2', 'new')
        self.assertFalse(cache.save(self.site, 'new', compatibility='fixture'))
        self.assertEqual(cache._current(cache.project), old)
        self.assertEqual(len(cache._generations(cache.project)), 1)
        self.assertFalse(any(cache.project.glob('candidate-*')))
        self.assertLessEqual(cache._usage(), 18000)

    def test_unavailable_hardlinks_preserve_previous_generation_under_tight_budget(self):
        from unittest.mock import patch
        ReaderCache, _ = self.api()
        self.write_site()
        (self.site / 'large.png').write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=18000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        self.write_site('v2', 'new')
        real_copy = shutil.copy2

        def bounded_copy(source, target):
            self.assertLessEqual(cache._usage() + Path(source).stat().st_size, 18000)
            return real_copy(source, target)

        with patch('jlpt_notes.reader.cache.os.link', side_effect=OSError('hardlinks unavailable')), \
                patch('jlpt_notes.reader.cache.shutil.copy2', side_effect=bounded_copy):
            self.assertFalse(cache.save(self.site, 'new', compatibility='fixture'))
        self.assertEqual(cache._current(cache.project), old)
        self.assertFalse(any(cache.project.glob('candidate-*')))
        self.assertEqual(len(cache._generations(cache.project)), 1)
        self.assertLessEqual(cache._usage(), 18000)
        self.assertTrue(cache.restore(self.base / 'old', 'old'))
        self.assertEqual((self.base / 'old/index.html').read_text(), 'first')

    def test_unavailable_hardlinks_copy_with_reserved_fallback_capacity(self):
        from unittest.mock import patch
        ReaderCache, _ = self.api()
        self.write_site()
        (self.site / 'large.png').write_bytes(b'a' * 10000)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir, max_bytes=40000)
        self.assertTrue(cache.save(self.site, 'old', compatibility='fixture'))
        old = cache._current(cache.project)
        self.write_site('v2', 'new')
        with patch('jlpt_notes.reader.cache.os.link', side_effect=OSError('hardlinks unavailable')):
            self.assertTrue(cache.save(self.site, 'new', compatibility='fixture'))
        new = cache._current(cache.project)
        self.assertNotEqual((old / 'site/large.png').stat().st_ino, (new / 'site/large.png').stat().st_ino)
        self.assertLessEqual(cache._usage(), 40000)
        self.assertTrue(cache.restore(self.base / 'new', 'new'))

    def test_reuse_never_links_from_another_project_or_new_site(self):
        ReaderCache, _ = self.api()
        self.write_site()
        asset = self.site / 'asset.png'
        asset.write_bytes(b'generated asset')
        first = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(first.save(self.site, 'first', compatibility='fixture'))
        other_notes = self.base / 'other-notes'
        other_notes.mkdir()
        second = ReaderCache(other_notes, self.config, directory=self.cache_dir)
        self.assertTrue(second.save(self.site, 'second', compatibility='fixture'))
        first_asset = first._current(first.project) / 'site/asset.png'
        second_asset = second._current(second.project) / 'site/asset.png'
        self.assertNotEqual(first_asset.stat().st_ino, second_asset.stat().st_ino)
        self.assertNotEqual(second_asset.stat().st_ino, asset.stat().st_ino)

    def test_output_symlinks_never_enter_or_escape_cache(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        external = self.base / 'external'
        external.mkdir()
        valuable = external / 'keep'
        valuable.write_text('valuable')
        try:
            (self.site / 'linked').symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertFalse(cache.save(self.site, fingerprint(self.notes, self.config)))
        (self.site / 'linked').unlink()
        self.assertTrue(cache.save(self.site, fingerprint(self.notes, self.config)))
        (self.cache_dir / 'generation-foreign').symlink_to(external, target_is_directory=True)
        cache.cleanup()
        self.assertEqual(valuable.read_text(), 'valuable')

    def test_incomplete_success_is_not_saved(self):
        ReaderCache, fingerprint = self.api()
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        (self.site / 'index.html').write_text('partial')
        self.assertFalse(cache.save(self.site, fingerprint(self.notes, self.config)))

    def test_failed_pointer_update_keeps_previous_cache(self):
        from unittest.mock import patch
        ReaderCache, fingerprint = self.api()
        self.write_site()
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        signature = fingerprint(self.notes, self.config)
        self.assertTrue(cache.save(self.site, signature))
        self.write_site('v2', 'second')
        real_replace = os.replace
        def fail_pointer(source, target):
            if Path(target).name == 'current.json':
                raise OSError('injected interrupted pointer update')
            return real_replace(source, target)
        with patch('jlpt_notes.reader.cache.os.replace', side_effect=fail_pointer):
            self.assertFalse(cache.save(self.site, signature))
        restored = self.base / 'restored'
        self.assertTrue(cache.restore(restored, signature))
        self.assertEqual((restored / 'index.html').read_text(), 'first')

    def test_compatible_old_cache_is_a_seed_but_not_an_exact_hit(self):
        from jlpt_notes.reader.cache import configuration_fingerprint
        ReaderCache, fingerprint = self.api()
        self.write_site()
        old_signature = fingerprint(self.notes, self.config)
        compatibility = configuration_fingerprint(self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, old_signature, compatibility=compatibility))
        self.card.write_text('# 新内容\n', encoding='utf-8')
        self.assertFalse(cache.restore(self.base / 'exact', fingerprint(self.notes, self.config)))
        self.assertTrue(cache.restore_previous(self.base / 'seed', compatibility))
        self.config.write_text('site_name: upgraded\n')
        self.assertFalse(cache.restore_previous(self.base / 'incompatible', configuration_fingerprint(self.config)))

    def test_restore_refuses_to_write_inside_learning_library(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature))
        with self.assertRaises(ValueError):
            cache.restore(self.notes / 'forbidden', signature)
        self.assertFalse((self.notes / 'forbidden').exists())

    def test_busy_cache_is_not_deleted_by_another_instance(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, fingerprint(self.notes, self.config)))
        other = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        with cache._locked():
            with self.assertRaises(BlockingIOError):
                other.cleanup()
            self.assertFalse(other.restore(self.base / 'busy', fingerprint(self.notes, self.config)))
        self.assertTrue(other.restore(self.base / 'after', fingerprint(self.notes, self.config)))

    def test_symlinked_cache_metadata_is_rejected(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature))
        marker = next(path for path in self.cache_dir.rglob('.jlpt-reader-owned') if path.parent.name.startswith('generation-'))
        external = self.base / 'external-marker'
        external.write_bytes(marker.read_bytes())
        marker.unlink()
        try:
            marker.symlink_to(external)
        except OSError:
            self.skipTest('symlinks unavailable')
        cache.cleanup()
        self.assertTrue(external.exists())
        self.assertFalse(cache.restore(self.base / 'restored', signature))

    def test_cleanup_collects_marked_interrupted_candidate_but_keeps_latest(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature))
        generation = next(path.parent for path in self.cache_dir.rglob('cache.json'))
        interrupted = generation.parent / ('candidate-' + '0' * 32)
        shutil.copytree(generation, interrupted)
        cache.cleanup()
        self.assertFalse(interrupted.exists())
        self.assertTrue(cache.restore(self.base / 'latest', signature))

    def test_cached_warnings_have_a_real_temporary_log(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature, warnings=('card.md: missing.png',)))
        self.assertTrue(cache.restore(self.base / 'restored', signature))
        self.assertEqual(cache.last_result.warnings, ('card.md: missing.png',))
        self.assertIsNotNone(cache.last_result.log_path)
        self.assertIn('missing.png', cache.last_result.log_path.read_text())

    def test_manual_clear_only_removes_owned_project_cache(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature))
        foreign = self.cache_dir / 'keep.txt'
        foreign.write_text('keep')
        try:
            removed = cache.clear()
        except AttributeError as error:
            self.fail(f'Manual cache clear missing: {error}')
        self.assertEqual(removed, 1)
        self.assertFalse(cache.restore(self.base / 'restored', signature))
        self.assertEqual(foreign.read_text(), 'keep')
        self.assertEqual(self.card.read_text(), '# 最初\n')

    def test_script_resource_mapping_invalidates_compatibility(self):
        from jlpt_notes.reader.cache import configuration_fingerprint
        self.config.write_text('site_name: fixture\nextra_javascript:\n  - path: extra.js\n    async: true\n')
        script = self.reader / 'extra.js'
        script.write_text('one')
        before = configuration_fingerprint(self.config)
        script.write_text('two')
        self.assertNotEqual(before, configuration_fingerprint(self.config))

    def test_cache_directory_inside_notes_is_never_created(self):
        ReaderCache, _ = self.api()
        inside = self.notes / 'cache'
        cache = ReaderCache(self.notes, self.config, directory=inside)
        with self.assertRaises(ValueError):
            cache.cleanup()
        self.assertFalse(inside.exists())

    def test_saved_page_count_excludes_assets_from_reuse_count(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        manifest = self.site / 'reader-version.json'
        manifest.write_text(json.dumps({'version': 'v1', 'pages': {'': 'html', 'image.png': 'image'}}))
        (self.site / 'image.png').write_bytes(b'fixture-image')
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        signature = fingerprint(self.notes, self.config)
        try:
            saved = cache.save(self.site, signature, page_count=1)
        except TypeError as error:
            self.fail(f'Cache cannot distinguish pages from assets: {error}')
        self.assertTrue(saved)
        self.assertTrue(cache.restore(self.base / 'restored', signature))
        self.assertEqual(cache.last_result.reused_pages, 1)

    def test_cli_manual_clear_preserves_study_bytes(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        from jlpt_notes.cli import main
        ReaderCache, fingerprint = self.api()
        self.write_site()
        # Use the command's normal XDG namespace, isolated by a fixture.
        cache = ReaderCache(self.notes, self.config)
        self.assertTrue(cache.save(self.site, fingerprint(self.notes, self.config)))
        before = self.card.read_bytes()
        argv = ['jlpt-notes', 'reader-cache-clean', '--root', str(self.notes), '--config', str(self.config)]
        with patch('sys.argv', argv), redirect_stdout(StringIO()) as output:
            try:
                status = main()
            except SystemExit as error:
                self.fail(f'Manual cache-clean CLI missing: {error}')
        self.assertEqual(status, 0)
        self.assertIn('缓存', output.getvalue())
        self.assertFalse(cache.restore(self.base / 'restored', fingerprint(self.notes, self.config)))
        self.assertEqual(self.card.read_bytes(), before)

    def test_busy_restore_never_removes_another_restores_destination(self):
        from contextlib import contextmanager
        from threading import Event, Thread
        from unittest.mock import patch
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        first = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        second = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(first.save(self.site, signature))
        destination = self.base / 'shared-destination'
        waiting, copied, release = Event(), Event(), Event()
        results = {}
        real_locked, real_copy = second._locked, shutil.copytree

        @contextmanager
        def delayed_lock():
            waiting.set()
            self.assertTrue(copied.wait(5))
            with real_locked():
                yield

        def delayed_copy(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            copied.set()
            self.assertTrue(release.wait(5))
            return result

        def restore(cache, name):
            results[name] = cache.restore(destination, signature)

        with patch.object(second, '_locked', delayed_lock), patch('jlpt_notes.reader.cache.shutil.copytree', delayed_copy):
            loser = Thread(target=restore, args=(second, 'second'))
            winner = Thread(target=restore, args=(first, 'first'))
            loser.start()
            try:
                self.assertTrue(waiting.wait(5))
                winner.start()
                self.assertTrue(copied.wait(5))
                loser.join(5)
            finally:
                release.set()
                winner.join(5)
                loser.join(5)
        self.assertEqual(results, {'first': True, 'second': False})
        self.assertEqual((destination / 'index.html').read_text(), 'first')

    def test_cached_warning_log_never_follows_a_preexisting_sibling_link(self):
        ReaderCache, fingerprint = self.api()
        self.write_site()
        signature = fingerprint(self.notes, self.config)
        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        self.assertTrue(cache.save(self.site, signature, warnings=('missing asset',)))
        destination = self.base / 'restored'
        log = self.base / 'restored.warnings.log'
        try:
            log.symlink_to(self.card)
        except OSError:
            self.skipTest('symlinks unavailable')
        original = self.card.read_bytes()
        self.assertTrue(cache.restore(destination, signature))
        self.assertEqual(self.card.read_bytes(), original)
        self.assertNotEqual(cache.last_result.log_path, log)
        self.assertEqual(cache.last_result.log_path.read_text(), 'missing asset\n')

    def test_hook_edit_invalidates_inherited_configuration(self):
        from jlpt_notes.reader.cache import configuration_fingerprint
        inherited = self.reader / 'base.yml'
        inherited.write_text('hooks:\n  - build_hook.py\n')
        self.config.write_text('INHERIT: base.yml\nsite_name: fixture\n')
        hook = self.reader / 'build_hook.py'
        hook.write_text('value = 1\n')
        before = configuration_fingerprint(self.config)
        hook.write_text('value = 2\n')
        self.assertNotEqual(before, configuration_fingerprint(self.config))

    def test_windows_reparse_directory_is_not_cached(self):
        import stat
        from types import SimpleNamespace
        from unittest.mock import patch
        ReaderCache, fingerprint = self.api()
        self.write_site()
        linked = self.site / 'junction'
        linked.mkdir()
        (linked / 'foreign.html').write_text('external bytes')
        signature = fingerprint(self.notes, self.config)
        real_lstat = Path.lstat

        def reparse_lstat(path):
            if path == linked:
                return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
                                       st_mode=real_lstat(path).st_mode)
            return real_lstat(path)

        cache = ReaderCache(self.notes, self.config, directory=self.cache_dir)
        with patch.object(Path, 'lstat', reparse_lstat):
            self.assertFalse(cache.save(self.site, signature))
        self.assertFalse(self.cache_dir.exists())

    def _git(self, *args):
        subprocess.run(['git', '-C', str(self.base), *args], check=True, capture_output=True)
