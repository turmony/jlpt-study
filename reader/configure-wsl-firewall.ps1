[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][ValidateRange(1024, 65535)][int]$Port,
    [Parameter(Mandatory = $true)][string]$Address,
    [Parameter(Mandatory = $true)][string]$Subnet
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

# Validate the proposed scope even in preview mode. No 'Any', IPv6 or public addresses.
$ip = [Net.IPAddress]::Parse($Address)
if ($ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw 'IPv4 required' }
$octets = $ip.GetAddressBytes()
if (-not ($octets[0] -eq 10 -or ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or
    ($octets[0] -eq 192 -and $octets[1] -eq 168))) { throw 'Private IPv4 required' }
$parts = $Subnet.Split('/')
if ($parts.Count -ne 2 -or $parts[1] -notmatch '^\d{1,2}$') { throw 'IPv4 CIDR required' }
$prefix = [int]$parts[1]
$minimum = if ($octets[0] -eq 10) { 8 } elseif ($octets[0] -eq 172) { 12 } else { 16 }
if ($prefix -lt $minimum -or $prefix -gt 32) { throw 'Subnet must remain within private IPv4 space' }
$networkBytes = [byte[]]@(0, 0, 0, 0)
for ($i = 0; $i -lt 4; $i++) {
    $bits = [Math]::Min(8, [Math]::Max(0, $prefix - $i * 8))
    $mask = if ($bits -eq 0) { 0 } else { 256 - [Math]::Pow(2, 8 - $bits) }
    $networkBytes[$i] = $octets[$i] -band [int]$mask
}
$expectedSubnet = ([Net.IPAddress]::new($networkBytes)).ToString() + '/' + $prefix
if ($Subnet -ne $expectedSubnet) { throw 'Subnet does not match address' }

$name = 'JLPT-iPad-Reader-WSL-Private-LAN'
$native = @{
    Name = 'JLPT-iPad-Reader-WSL-Host-Private-LAN'; DisplayName = 'JLPT iPad Reader (WSL Host Private LAN)'
    Enabled = 'True'; Direction = 'Inbound'; Action = 'Allow'; Protocol = 'TCP'
    LocalPort = $Port; Profile = 'Private'; LocalAddress = $Address; RemoteAddress = $Subnet
}
$hyperv = @{
    Name = $name; DisplayName = 'JLPT iPad Reader (WSL Private LAN)'
    VMCreatorId = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
    Enabled = 'True'; Direction = 'Inbound'; Action = 'Allow'; Protocol = 'TCP'
    LocalPorts = $Port; Profiles = 'Private'; LocalAddresses = $Address; RemoteAddresses = $Subnet
}
if ($WhatIfPreference) {
    @{ Native = $native; HyperV = $hyperv } | ConvertTo-Json -Depth 4 -Compress
    exit 0
}

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Port ' + $Port +
        ' -Address "' + $Address + '" -Subnet "' + $Subnet + '"'
    $child = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $child.ExitCode
}

# Re-check the actual adapter after elevation, before touching either rule.
$physical = @(Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and -not $_.Virtual })
$private = @(Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Private' })
$matching = @(Get-NetIPAddress -AddressFamily IPv4 -IPAddress $Address | Where-Object {
    $_.PrefixLength -eq $prefix -and $_.AddressState -eq 'Preferred' -and -not $_.SkipAsSource -and
    $_.InterfaceIndex -in $physical.InterfaceIndex -and $_.InterfaceIndex -in $private.InterfaceIndex
})
if ($matching.Count -ne 1) { throw 'Address must belong to the current physical Private LAN' }

if ($PSCmdlet.ShouldProcess($name, 'Configure Windows and WSL Hyper-V Private LAN rules')) {
    # Replace only our named rules, clearing any old wider filters or executable paths.
    Get-NetFirewallRule -PolicyStore PersistentStore -Name $native.Name -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule
    New-NetFirewallRule @native | Out-Null
    Get-NetFirewallHyperVRule -PolicyStore PersistentStore -Name $name -ErrorAction SilentlyContinue |
        Remove-NetFirewallHyperVRule
    New-NetFirewallHyperVRule @hyperv | Out-Null
}
