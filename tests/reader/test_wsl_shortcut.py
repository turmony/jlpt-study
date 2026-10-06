"""Exercise the WSL desktop launch contract with real Windows script previews."""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from .windows_tools import WSL_AVAILABLE, local_path, run_powershell, windows_path

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "reader/install-wsl-shortcut.ps1"


@unittest.skipUnless(WSL_AVAILABLE, "requires a WSL distribution and Windows PowerShell interop")
class WslShortcutTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "WSL shortcut installer is missing")

    def test_preview_uses_current_distribution_project_and_uv_without_overwriting_shortcut(self):
        with TemporaryDirectory(prefix="阅读器 with spaces ") as directory:
            desktop = Path(directory)
            shortcut = desktop / "JLPT iPad 阅读器.lnk"
            shortcut.write_bytes(b"existing shortcut must survive preview")
            before = (shortcut.read_bytes(), shortcut.stat().st_mtime_ns)
            preview = json.loads(run_powershell(
                SCRIPT, "-DesktopPath", windows_path(desktop), "-WhatIf",
            ).stdout)
            self.assertEqual(preview["Distribution"], os.environ["WSL_DISTRO_NAME"])
            self.assertEqual(preview["ProjectRoot"], str(PROJECT))
            self.assertEqual(Path(preview["UvPath"]).resolve(), Path(shutil.which("uv")).resolve())
            self.assertEqual(PureWindowsPath(preview["TargetPath"]).name.lower(), "wsl.exe")
            self.assertTrue(local_path(preview["ShortcutPath"]).samefile(shortcut))
            self.assertIn(f'--distribution {os.environ["WSL_DISTRO_NAME"]}', preview["Arguments"])
            self.assertIn(f'--cd "{PROJECT}"', preview["Arguments"])
            self.assertIn('--exec "', preview["Arguments"])
            self.assertIn('run python -m jlpt_notes reader --headless --lan --port 8765', preview["Arguments"])
            self.assertNotIn('--configure-firewall', preview["Arguments"])
            self.assertNotIn('pythonw.exe', preview["Arguments"])
            self.assertEqual((shortcut.read_bytes(), shortcut.stat().st_mtime_ns), before)
            self.assertEqual(list(desktop.iterdir()), [shortcut])

    def test_preview_arguments_start_the_reader_in_an_independent_windows_process(self):
        with TemporaryDirectory() as directory:
            preview = json.loads(run_powershell(SCRIPT, '-DesktopPath', windows_path(Path(directory)), '-WhatIf').stdout)
            result = self._launch(preview, extra=' --help')
            self.assertEqual(result['ExitCode'], 0, result)
            self.assertIn('jlpt-notes reader', result['Output'])
            self.assertIn('--headless', result['Output'])

    def test_preview_supports_project_paths_with_spaces_and_non_ascii(self):
        with TemporaryDirectory(prefix="日本語 reader ") as directory:
            base = Path(directory)
            root = base / "project with spaces"
            root.mkdir()
            (root / "reader").mkdir()
            (root / "reader/mkdocs.yml").write_text("site_name: test\n", encoding="utf-8")
            (root / "src/jlpt_notes").mkdir(parents=True)
            (root / "src/jlpt_notes/cli.py").touch()
            (root / "pyproject.toml").touch()
            (root / "jlpt-notes").mkdir()
            uv = base / 'uv with spaces' / 'uv'
            uv.parent.mkdir()
            uv.write_text(
                '#!/bin/sh\nif [ "$1" = "--version" ]; then echo uv-fixture; else printf "%s\\n" "$PWD" "$@"; fi\n',
                encoding='utf-8',
            )
            uv.chmod(0o755)
            desktop = base / "desktop"
            desktop.mkdir()
            preview = json.loads(run_powershell(
                SCRIPT, "-Distribution", os.environ["WSL_DISTRO_NAME"], "-ProjectRoot", str(root),
                "-DesktopPath", windows_path(desktop), "-Port", "8766", "-WhatIf",
                '-UvPath', str(uv),
            ).stdout)
            self.assertEqual(preview["ProjectRoot"], str(root))
            self.assertIn(f'--cd "{root}"', preview["Arguments"])
            self.assertIn('--port 8766', preview["Arguments"])
            self.assertEqual(tuple(desktop.iterdir()), ())
            result = self._launch(preview)
            self.assertEqual(result['ExitCode'], 0, result)
            self.assertEqual(result['Output'].splitlines(), [
                str(root), 'run', 'python', '-m', 'jlpt_notes', 'reader', '--headless', '--lan', '--port', '8766',
            ])

    def test_invalid_project_fails_before_touching_desktop(self):
        with TemporaryDirectory() as directory:
            desktop = Path(directory)
            with self.assertRaises(subprocess.CalledProcessError):
                run_powershell(
                    SCRIPT, "-Distribution", os.environ["WSL_DISTRO_NAME"], "-ProjectRoot", str(desktop),
                    "-DesktopPath", windows_path(desktop), "-WhatIf",
                )
            self.assertEqual(tuple(desktop.iterdir()), ())

    def test_install_creates_real_shortcut_and_backs_up_previous_version(self):
        with TemporaryDirectory(prefix="阅读器 desktop ") as directory:
            desktop = Path(directory)
            installed = json.loads(run_powershell(SCRIPT, "-DesktopPath", windows_path(desktop)).stdout)
            shortcut = local_path(installed["ShortcutPath"])
            self.assertTrue(shortcut.is_file())
            self.assertIsNone(installed["BackupPath"])
            path_literal = windows_path(shortcut).replace("'", "''")
            query = (
                "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
                "$shell=New-Object -ComObject WScript.Shell; "
                f"$link=$shell.CreateShortcut('{path_literal}'); "
                "$link | Select-Object TargetPath,Arguments,WorkingDirectory,Description,WindowStyle | ConvertTo-Json -Compress"
            )
            actual = json.loads(subprocess.check_output(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', query],
                text=True, encoding='utf-8', timeout=10,
            ))
            self.assertEqual(actual['TargetPath'].casefold(), installed['TargetPath'].casefold())
            self.assertEqual(actual['Arguments'], installed['Arguments'])
            self.assertEqual(actual['WorkingDirectory'], installed['WorkingDirectory'])
            self.assertEqual(actual['WindowStyle'], 1)
            subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                 query.split('$link |')[0] + '$link.WindowStyle=7; $link.Save()'], check=True,
                capture_output=True, timeout=10,
            )
            original = shortcut.read_bytes()
            repeated = json.loads(run_powershell(SCRIPT, "-DesktopPath", windows_path(desktop)).stdout)
            backup = local_path(repeated['BackupPath'])
            try:
                self.assertEqual(backup.read_bytes(), original)
                self.assertTrue(shortcut.is_file())
                actual = json.loads(subprocess.check_output(
                    ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', query],
                    text=True, encoding='utf-8', timeout=10,
                ))
                self.assertEqual(actual['WindowStyle'], 1)
            finally:
                backup.unlink(missing_ok=True)

    def _launch(self, preview, *, extra=''):
        data = json.dumps(preview, ensure_ascii=False).replace("'", "''")
        program = r'''
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$ErrorActionPreference='Stop'
$preview='PREVIEW_LITERAL' | ConvertFrom-Json
$base=Join-Path $env:TEMP ([Guid]::NewGuid().ToString('N'))
$outFile=$base+'.out'
$errFile=$base+'.err'
try {
    $process=Start-Process -FilePath $preview.TargetPath -ArgumentList ($preview.Arguments+'EXTRA_LITERAL') -WorkingDirectory $preview.WorkingDirectory -Wait -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    @{ExitCode=$process.ExitCode;Output=[IO.File]::ReadAllText($outFile);Errors=[IO.File]::ReadAllText($errFile)} | ConvertTo-Json -Compress
} finally { Remove-Item -LiteralPath $outFile,$errFile -ErrorAction SilentlyContinue }
'''.replace('PREVIEW_LITERAL', data).replace('EXTRA_LITERAL', extra.replace("'", "''"))
        return json.loads(subprocess.check_output([
            'powershell.exe', '-NoProfile', '-NonInteractive', '-Command', program,
        ], text=True, encoding='utf-8', timeout=30))

    def test_linked_worktree_with_arbitrary_name_is_rejected(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            repository = base / 'repository'
            worktree = base / 'temporary-checkout'
            desktop = base / 'desktop'
            desktop.mkdir()
            subprocess.run(['git', 'init', '-q', str(repository)], check=True, capture_output=True)
            subprocess.run(
                ['git', '-C', str(repository), '-c', 'user.name=Fixture', '-c',
                 'user.email=fixture@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'fixture'],
                check=True, capture_output=True,
            )
            subprocess.run(['git', '-C', str(repository), 'worktree', 'add', '-q', '--detach', str(worktree)],
                           check=True, capture_output=True)
            for relative in ('pyproject.toml', 'reader/mkdocs.yml', 'src/jlpt_notes/cli.py'):
                destination = worktree / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.touch()
            (worktree / 'jlpt-notes').mkdir()
            with self.assertRaises(subprocess.CalledProcessError):
                run_powershell(
                    SCRIPT, '-Distribution', os.environ['WSL_DISTRO_NAME'], '-ProjectRoot', str(worktree),
                    '-DesktopPath', windows_path(desktop), '-WhatIf',
                )
            self.assertEqual(tuple(desktop.iterdir()), ())

    def test_save_failure_restores_the_original_shortcut(self):
        self._check_failed_save(existing=True)

    def test_failed_creation_leaves_no_partial_shortcut(self):
        self._check_failed_save(existing=False)

    def _check_failed_save(self, *, existing):
        with TemporaryDirectory(prefix='rollback desktop ') as directory:
            desktop = Path(directory)
            shortcut = desktop / 'JLPT iPad 阅读器.lnk'
            original = b'original shortcut bytes preserved after failed save'
            if existing:
                shortcut.write_bytes(original)
            program = r'''
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
function New-Object {
    param([string]$ComObject)
    if ($ComObject -ne 'WScript.Shell') { throw 'Unexpected COM request' }
    $shell = [pscustomobject]@{}
    Add-Member -InputObject $shell -MemberType ScriptMethod -Name CreateShortcut -Value {
        param($path)
        $script:FailurePath = $path
        $link = [pscustomobject]@{TargetPath=''; Arguments=''; WorkingDirectory=''; Description=''; WindowStyle=1}
        Add-Member -InputObject $link -MemberType ScriptMethod -Name Save -Value {
            [IO.File]::WriteAllText($script:FailurePath, 'partial failed write')
            throw 'injected save failure'
        }
        return $link
    }
    return $shell
}
$failed = $false
try { . 'SCRIPT_LITERAL' -DesktopPath 'DESKTOP_LITERAL' }
catch {
    if ($_.Exception.Message -notmatch 'injected save failure') { throw }
    $failed = $true
}
if (-not $failed) { throw 'Expected failed save' }
@{BackupPath=$backupPath} | ConvertTo-Json -Compress
'''.replace('SCRIPT_LITERAL', windows_path(SCRIPT).replace("'", "''")).replace(
                'DESKTOP_LITERAL', windows_path(desktop).replace("'", "''"),
            )
            result = json.loads(subprocess.check_output(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', program],
                text=True, encoding='utf-8', timeout=30,
            ))
            if not existing:
                self.assertIsNone(result['BackupPath'])
                self.assertFalse(shortcut.exists())
                return
            backup = local_path(result['BackupPath'])
            try:
                self.assertEqual(shortcut.read_bytes(), original)
                self.assertEqual(backup.read_bytes(), original)
            finally:
                backup.unlink(missing_ok=True)
