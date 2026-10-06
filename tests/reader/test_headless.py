"""Exercise the terminal reader through its real CLI and HTTP service."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from jlpt_notes.cli import build_parser
from jlpt_notes.reader.controller import ReaderController

PROJECT = Path(__file__).resolve().parents[2]
BOOTSTRAP = """
import sys
sys.modules['tkinter'] = None
from jlpt_notes.reader import controller
def forbidden(*args, **kwargs):
    raise SystemExit('headless must not inspect or configure Windows networking')
controller.private_lan_addresses = forbidden
controller.firewall_rule_present = forbidden
controller.configure_firewall_rule = forbidden
from jlpt_notes.cli import main
raise SystemExit(main())
"""


class HeadlessReaderTests(unittest.TestCase):
    def test_headless_is_opt_in(self):
        parser = build_parser()
        self.assertFalse(getattr(parser.parse_args(['reader']), 'headless', None))
        self.assertTrue(parser.parse_args(['reader', '--headless']).headless)

    @unittest.skipIf(os.name == 'nt', 'POSIX signal lifecycle runs on Linux')
    def test_serves_updates_without_tk_or_windows_checks_and_cleans_up_on_signals(self):
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=stop_signal), TemporaryDirectory() as directory:
                base = Path(directory)
                notes = base / 'notes'
                notes.mkdir()
                card = notes / 'card.md'
                card.write_text('# Card\n\ninitial-reader-content\n', encoding='utf-8')
                original = (card.read_bytes(), card.stat().st_mtime_ns)
                sessions = base / 'sessions'
                sessions.mkdir()
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                url = f'http://127.0.0.1:{port}'
                process = self._start(notes, sessions, port)
                lines = Queue()
                output = []

                def collect_output(process=process, output=output, lines=lines):
                    for line in process.stdout:
                        output.append(line)
                        lines.put(line)

                reader = Thread(target=collect_output, daemon=True)
                reader.start()
                try:
                    self._wait_for_url(process, lines, output, url)
                    self.assertEqual((card.read_bytes(), card.stat().st_mtime_ns), original)
                    manifest = json.loads(self._read(url + '/reader-version.json'))
                    route = next(route for route in manifest['pages'] if 'card.md' in route)
                    self.assertIn('initial-reader-content', self._read(url + '/' + route))
                    self.assertTrue(tuple(sessions.glob('jlpt-reader-*')))
                    version = manifest['version']
                    card.write_text('# Card\n\nupdated-reader-content\n', encoding='utf-8')
                    changed = (card.read_bytes(), card.stat().st_mtime_ns)
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        if json.loads(self._read(url + '/reader-version.json'))['version'] != version:
                            break
                        time.sleep(0.1)
                    else:
                        self.fail('source change was not published')
                    self.assertIn('updated-reader-content', self._read(url + '/' + route))
                    process.send_signal(stop_signal)
                    self.assertEqual(process.wait(timeout=10), 0)
                    reader.join(timeout=2)
                    self.assertNotIn('headless must not', ''.join(output))
                    self.assertEqual((card.read_bytes(), card.stat().st_mtime_ns), changed)
                    self.assertEqual(tuple(sessions.iterdir()), ())
                    self.assertIn('已停止', ''.join(output))
                    # Mirrored WSL networking may time out instead of refusing
                    # a closed loopback port; rebinding below proves release.
                    with self.assertRaises((URLError, TimeoutError)):
                        self._read(url)
                    # The listening socket was released, not merely made unresponsive.
                    with socket.socket() as probe:
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        probe.bind(('127.0.0.1', port))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                    reader.join(timeout=2)
                    process.stdout.close()

    def test_startup_failure_exits_nonzero_and_removes_partial_session(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            notes = base / 'notes'
            notes.mkdir()
            (notes / 'broken.md').write_bytes(b'\xff\xfe')
            sessions = base / 'sessions'
            sessions.mkdir()
            process = self._start(notes, sessions, 8765)
            try:
                output, _ = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 1, output)
                self.assertIn('首次构建失败', output)
                self.assertIn('.log', output)
                self.assertIn('已停止', output)
                self.assertNotIn('headless must not', output)
                self.assertEqual(tuple(sessions.iterdir()), ())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_occupied_port_exits_nonzero_and_cleans_built_site(self):
        with TemporaryDirectory() as directory, socket.socket() as occupied:
            base = Path(directory)
            notes = base / 'notes'
            notes.mkdir()
            (notes / 'card.md').write_text('# Card\n', encoding='utf-8')
            sessions = base / 'sessions'
            sessions.mkdir()
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            process = self._start(notes, sessions, occupied.getsockname()[1])
            try:
                output, _ = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 1, output)
                self.assertIn('端口', output)
                self.assertIn('已停止', output)
                self.assertEqual(tuple(sessions.iterdir()), ())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_invalid_input_restores_the_callers_signal_handlers(self):
        from jlpt_notes.reader.headless import run

        previous = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()) as output:
            result = run(Path(directory) / 'missing', PROJECT / 'reader/mkdocs.yml', Path(sys.executable))
        self.assertEqual(result, 1)
        self.assertIn('找不到资料目录', output.getvalue())
        for signum, handler in previous.items():
            self.assertIs(signal.getsignal(signum), handler)

    def test_local_only_controller_cannot_enable_lan(self):
        with TemporaryDirectory() as directory:
            statuses = []
            controller = ReaderController(
                Path(directory), PROJECT / 'reader/mkdocs.yml', Path(sys.executable),
                on_status=statuses.append, local_only=True,
            )
            self.assertFalse(controller.configure_firewall())
            self.assertEqual(statuses[-1].state, 'local-only')
            self.assertEqual(controller.urls, ())

    def _start(self, notes, sessions, port):
        return subprocess.Popen(
            [sys.executable, '-c', BOOTSTRAP, 'reader', '--headless',
             '--root', str(notes), '--config', str(PROJECT / 'reader/mkdocs.yml'),
             '--port', str(port)],
            cwd=PROJECT,
            env={**os.environ, 'TMPDIR': str(sessions), 'TEMP': str(sessions),
                 'TMP': str(sessions), 'PYTHONIOENCODING': 'utf-8'},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
        )

    def _wait_for_url(self, process, lines, output, url):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.1)
            except Empty:
                if process.poll() is not None:
                    self.fail('reader exited before serving: ' + ''.join(output))
                continue
            if url in line:
                return
        self.fail('reader never printed its access URL: ' + ''.join(output))

    def _read(self, url):
        with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
            return response.read().decode('utf-8')
