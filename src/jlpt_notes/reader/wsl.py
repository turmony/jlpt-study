"""Inspect mirrored WSL networking and narrowly scoped Windows firewall rules."""

import ipaddress
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .network import NetworkInspectionError, private_lan_addresses

RULE_NAME = "JLPT-iPad-Reader-WSL-Private-LAN"
HOST_RULE_NAME = "JLPT-iPad-Reader-WSL-Host-Private-LAN"
WSL_CREATOR = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"
_PRIVATE_RANGES = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))


@dataclass(frozen=True)
class WslLan:
    address: str
    subnet: str


def _run(command, runner=None, *, timeout=15):
    try:
        return (runner or subprocess.run)(
            command, capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        raise NetworkInspectionError(f"无法检查 WSL 局域网：{detail}") from error


def discover_lan(*, runner=None) -> WslLan:
    """Match an active mirrored IPv4 interface to a physical Windows Private LAN."""
    if _run(["wslinfo", "--networking-mode"], runner) != "mirrored":
        raise NetworkInspectionError("WSL 必须使用 mirrored 镜像网络模式。")
    candidates = private_lan_addresses(runner=runner)
    try:
        interfaces = json.loads(_run(["ip", "-j", "-4", "address", "show"], runner))
        for candidate in candidates:
            for interface in interfaces:
                if "UP" not in interface["flags"]:
                    continue
                for address in interface["addr_info"]:
                    if (address.get("family") != "inet" or address.get("scope") != "global"
                            or address.get("local") != candidate.address):
                        continue
                    prefix = address["prefixlen"]
                    if isinstance(prefix, bool) or not isinstance(prefix, int):
                        raise TypeError("invalid IPv4 prefix")
                    subnet = ipaddress.ip_interface(f"{candidate.address}/{prefix}").network
                    if any(subnet.subnet_of(private) for private in _PRIVATE_RANGES):
                        return WslLan(candidate.address, str(subnet))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise NetworkInspectionError(f"无法解析 WSL 网卡信息：{error}") from error
    raise NetworkInspectionError("未找到与 WSL 镜像网卡匹配的 Windows 专用物理网络。")


def approved_lan(port: int, *, runner=None) -> WslLan:
    """Require both enabled firewall layers and exact reader address/port/subnet scope."""
    _validate_port(port)
    lan = discover_lan(runner=runner)
    try:
        state = json.loads(_run([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _STATE_QUERY,
        ], runner))
        if not all(state[key] == "True" for key in (
            "HostEnabled", "HyperVEnabled", "HyperVProfileEnabled",
            "HostLocalRules", "HyperVLocalRules",
        )):
            raise ValueError("专用网络防火墙或本地规则未启用")
        expected = {
            "Name": RULE_NAME, "Enabled": "True", "Direction": "Inbound", "Action": "Allow",
            "Profile": "Private", "Protocol": "TCP", "Ports": [str(port)],
            "Local": [lan.address], "Remote": [lan.subnet],
        }
        for layer in ("Native", "HyperV"):
            rules = state[layer]
            if not isinstance(rules, list) or len(rules) != 1:
                raise ValueError(f"{layer} 阅读器规则缺失或重复")
            rule = dict(rules[0])
            rule["Remote"] = [str(ipaddress.ip_network(value)) for value in rule["Remote"]]
            layer_expected = {**expected, "Name": HOST_RULE_NAME if layer == "Native" else RULE_NAME}
            if not all(rule[key] == value for key, value in layer_expected.items()):
                raise ValueError(f"{layer} 阅读器规则与当前地址、端口或子网不匹配")
            if layer == "HyperV" and rules[0]["VMCreatorId"].upper() != WSL_CREATOR:
                raise ValueError("Hyper-V 规则未指向 WSL")
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise NetworkInspectionError(
            f"防火墙检查未通过：{error}；请使用 --headless --lan --configure-firewall 配置。"
        ) from error
    return lan


def configure_lan(script_path: Path, port: int, *, runner=None) -> WslLan:
    """Explicitly configure only the reader's two Private-LAN firewall rules."""
    _validate_port(port)
    lan = discover_lan(runner=runner)
    windows_path = _run(["wslpath", "-w", str(script_path.resolve(strict=True))], runner)
    _run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", windows_path, "-Port", str(port), "-Address", lan.address, "-Subnet", lan.subnet,
    ], runner, timeout=120)
    return approved_lan(port, runner=runner)


def _validate_port(port):
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("端口必须是 1024 到 65535 之间的整数")


_STATE_QUERY = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$name = 'JLPT-iPad-Reader-WSL-Private-LAN'
$hostName = 'JLPT-iPad-Reader-WSL-Host-Private-LAN'
$creator = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
$hostProfile = Get-NetFirewallProfile -PolicyStore ActiveStore -Name Private
$vm = Get-NetFirewallHyperVVMSetting -PolicyStore ActiveStore -Name $creator
$vmProfile = Get-NetFirewallHyperVProfile -PolicyStore ActiveStore |
    Where-Object { $_.Profile.ToString() -eq 'Private' }
$native = @(Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue -Name $hostName |
    ForEach-Object {
        $port = $_ | Get-NetFirewallPortFilter
        $address = $_ | Get-NetFirewallAddressFilter
        [pscustomobject]@{
            Name = $_.Name; Enabled = $_.Enabled.ToString(); Direction = $_.Direction.ToString()
            Action = $_.Action.ToString(); Profile = $_.Profile.ToString()
            Protocol = [string]$port.Protocol
            Ports = @($port.LocalPort | ForEach-Object { [string]$_ })
            Local = @($address.LocalAddress | ForEach-Object { [string]$_ })
            Remote = @($address.RemoteAddress | ForEach-Object { [string]$_ })
        }
    })
$hyperv = @(Get-NetFirewallHyperVRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue -Name $name |
    ForEach-Object {
        [pscustomobject]@{
            Name = $_.Name; Enabled = $_.Enabled.ToString(); Direction = $_.Direction.ToString()
            Action = $_.Action.ToString(); Profile = $_.Profiles.ToString()
            Protocol = [string]$_.Protocol; VMCreatorId = [string]$_.VMCreatorId
            Ports = @($_.LocalPorts | ForEach-Object { [string]$_ })
            Local = @($_.LocalAddresses | ForEach-Object { [string]$_ })
            Remote = @($_.RemoteAddresses | ForEach-Object { [string]$_ })
        }
    })
[pscustomobject]@{
    HostEnabled = $hostProfile.Enabled.ToString(); HyperVEnabled = $vm.Enabled.ToString()
    HyperVProfileEnabled = $vmProfile.Enabled.ToString()
    HostLocalRules = $hostProfile.AllowLocalFirewallRules.ToString()
    HyperVLocalRules = $vmProfile.AllowLocalFirewallRules.ToString()
    Native = $native; HyperV = $hyperv
} | ConvertTo-Json -Depth 6 -Compress
""".strip()
