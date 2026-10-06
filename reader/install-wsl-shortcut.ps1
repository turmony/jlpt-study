[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Distribution,
    [string]$ProjectRoot,
    [string]$UvPath,
    [string]$DesktopPath,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$OutputEncoding = [Text.UTF8Encoding]::new()
$wslExe = (Get-Command wsl.exe -ErrorAction Stop).Source
$windowsRoot = (Resolve-Path -LiteralPath (Split-Path $PSScriptRoot -Parent)).ProviderPath
if ([string]::IsNullOrWhiteSpace($Distribution)) {
    if ($windowsRoot -match '^\\\\(?:wsl\.localhost|wsl\$)\\([^\\]+)\\') {
        $Distribution = $Matches[1]
    } else {
        throw 'Specify -Distribution when the script is not located in a WSL share.'
    }
}
if ($Distribution -notmatch '^[a-zA-Z0-9._-]+$') { throw 'Invalid WSL distribution name' }

function Invoke-Wsl {
    param([string[]]$Command)
    $output = & $wslExe --distribution $Distribution @Command 2>&1
    if ($LASTEXITCODE -ne 0) { throw "WSL validation failed: $($output -join ' ')" }
    return $output
}

function Assert-LinuxPath {
    param([string]$Value)
    if (-not $Value.StartsWith('/') -or $Value -match '["\\\r\n\x00]') {
        throw 'Use an absolute Linux path without quotes, backslashes or control characters.'
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Invoke-Wsl -Command @('--exec', 'wslpath', '-u', $windowsRoot) | Out-String).Trim()
}
Assert-LinuxPath $ProjectRoot
$ProjectRoot = (Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', '/bin/pwd', '-P') | Out-String).Trim()
Assert-LinuxPath $ProjectRoot
if ($ProjectRoot -match '/(?:\.worktrees|worktrees)(?:/|$)') {
    throw 'Install the shortcut from the stable project, not a disposable worktree.'
}
# Linked Git worktrees have a .git file even when their directory has an arbitrary name.
& $wslExe --distribution $Distribution --cd $ProjectRoot --exec /usr/bin/test -f .git
if ($LASTEXITCODE -eq 0) {
    $gitDir = (Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', 'git', 'rev-parse', '--absolute-git-dir') | Out-String).Trim()
    $commonDir = (Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', 'git', 'rev-parse', '--path-format=absolute', '--git-common-dir') | Out-String).Trim()
    if ($gitDir -ne $commonDir) { throw 'Install the shortcut from the stable repository, not a linked Git worktree.' }
} elseif ($LASTEXITCODE -ne 1) { throw 'Unable to inspect project Git location' }
foreach ($file in @('pyproject.toml', 'reader/mkdocs.yml', 'src/jlpt_notes/cli.py')) {
    Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', '/usr/bin/test', '-f', $file) | Out-Null
}
Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', '/usr/bin/test', '-d', 'jlpt-notes') | Out-Null
if ([string]::IsNullOrWhiteSpace($UvPath)) {
    $UvPath = (Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', '/bin/bash', '-lc', 'command -v uv') | Out-String).Trim()
}
Assert-LinuxPath $UvPath
Invoke-Wsl -Command @('--cd', $ProjectRoot, '--exec', $UvPath, '--version') | Out-Null

if ([string]::IsNullOrWhiteSpace($DesktopPath)) {
    $DesktopPath = [Environment]::GetFolderPath('Desktop')
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) { throw 'Desktop directory not found' }
$desktop = (Resolve-Path -LiteralPath $DesktopPath).ProviderPath
$readerName = -join [char[]](0x9605, 0x8BFB, 0x5668)
$shortcutPath = Join-Path $desktop "JLPT iPad $readerName.lnk"
# WSL may treat quotes as part of a distribution name in a native command line.
# Distribution is already validated as a single safe token; paths remain quoted.
$arguments = "--distribution $Distribution --cd `"$ProjectRoot`" --exec `"$UvPath`" run python -m jlpt_notes reader --headless --lan --port $Port"
$backupDirectory = Join-Path $env:LOCALAPPDATA 'JLPTReader\shortcut-backups'
$backupPath = if (Test-Path -LiteralPath $shortcutPath) {
    Join-Path $backupDirectory ("reader-{0}-{1}.lnk" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [Guid]::NewGuid().ToString('N'))
} else { $null }
$preview = [ordered]@{
    ShortcutPath = $shortcutPath; TargetPath = $wslExe; Arguments = $arguments
    WorkingDirectory = $env:USERPROFILE; Description = 'Manual JLPT iPad Reader (WSL)'
    WindowStyle = 1
    Distribution = $Distribution; ProjectRoot = $ProjectRoot; UvPath = $UvPath; Port = $Port
    BackupPath = $backupPath
}
if ($WhatIfPreference) {
    [pscustomobject]$preview | ConvertTo-Json -Compress
    return
}
if ($PSCmdlet.ShouldProcess($shortcutPath, 'Create manual WSL reader shortcut with previous shortcut backup')) {
    if ($backupPath) {
        New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
        Copy-Item -LiteralPath $shortcutPath -Destination $backupPath
    }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $preview.TargetPath
        $shortcut.Arguments = $preview.Arguments
        $shortcut.WorkingDirectory = $preview.WorkingDirectory
        $shortcut.Description = $preview.Description
        $shortcut.WindowStyle = $preview.WindowStyle
        $shortcut.Save()
    } catch {
        if ($backupPath) { Copy-Item -LiteralPath $backupPath -Destination $shortcutPath -Force }
        elseif (Test-Path -LiteralPath $shortcutPath -PathType Leaf) { Remove-Item -LiteralPath $shortcutPath }
        throw
    }
    [pscustomobject]$preview | ConvertTo-Json -Compress
}
