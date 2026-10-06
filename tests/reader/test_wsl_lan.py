"""Check mirrored-LAN discovery and exact firewall scope without changing Windows."""

import copy
import http.client
import importlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jlpt_notes.cli import build_parser, main
from jlpt_notes.reader.controller import ReaderController
from jlpt_notes.reader.network import NetworkInspectionError


def network_row():
    return {
        'InterfaceIndex': 10, 'IPAddress': '192.168.5.51', 'NetworkCategory': 'Private',
        'SkipAsSource': False, 'AdapterStatus': 'Up', 'HardwareInterface': True,
        'Virtual': False, 'InterfaceAlias': 'Ethernet', 'InterfaceDescription': 'Physical LAN',
        'MediaType': '802.3', 'PhysicalMediaType': '802.3',
    }


def firewall_state():
    rule = {
        'Name': 'JLPT-iPad-Reader-WSL-Private-LAN', 'Enabled': 'True',
        'Direction': 'Inbound', 'Action': 'Allow', 'Profile': 'Private',
        'Protocol': 'TCP', 'Ports': ['8765'], 'Local': ['192.168.5.51'],
        'Remote': ['192.168.5.0/24'],
    }
    hyperv = {**rule, 'VMCreatorId': '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'}
    rule['Name'] = 'JLPT-iPad-Reader-WSL-Host-Private-LAN'
    return {
        'HostEnabled': 'True', 'HyperVEnabled': 'True', 'HyperVProfileEnabled': 'True',
        'HostLocalRules': 'True', 'HyperVLocalRules': 'True',
        'Native': [rule], 'HyperV': [hyperv],
    }


class WslLanTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('jlpt_notes.reader.wsl'), 'WSL LAN support is missing')
        return importlib.import_module('jlpt_notes.reader.wsl')

    def runner(self, *, mode='mirrored', network=None, guest=None, firewall=None):
        network = network if network is not None else [network_row()]
        guest = guest if guest is not None else [
            {'ifname': 'eth0', 'flags': ['UP'], 'addr_info': [
                {'family': 'inet', 'local': '192.168.5.51', 'prefixlen': 24, 'scope': 'global'},
            ]},
        ]
        firewall = firewall if firewall is not None else firewall_state()

        def run(command, **kwargs):
            if command[0] == 'wslinfo':
                output = mode
            elif command[0] == 'ip':
                output = json.dumps(guest)
            elif command[0] == 'powershell.exe':
                query = command[-1]
                if 'Get-NetConnectionProfile' in query:
                    output = json.dumps(network)
                else:
                    output = json.dumps(firewall)
            else:
                raise AssertionError(f'unexpected external operation: {command}')
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr='')
        return run

    def test_lan_flags_require_the_terminal_and_explicit_configuration(self):
        parser = build_parser()
        args = parser.parse_args(['reader', '--headless', '--lan'])
        self.assertTrue(args.lan)
        self.assertFalse(args.configure_firewall)
        for flags in (['--lan'], ['--configure-firewall'], ['--headless', '--configure-firewall']):
            with self.subTest(flags=flags), self.assertRaises(SystemExit):
                parser.parse_args(['reader', *flags])

    def test_cli_dispatches_lan_configuration_to_terminal_without_repository_writes(self):
        for configure in (False, True):
            arguments = ['jlpt-notes', 'reader', '--headless', '--lan']
            if configure:
                arguments.append('--configure-firewall')
            with self.subTest(configure=configure), patch.object(sys, 'argv', arguments), \
                 patch('jlpt_notes.reader.headless.run', return_value=7) as run, \
                 patch('jlpt_notes.cli.Repository') as repository:
                self.assertEqual(main(), 7)
                repository.assert_not_called()
                run.assert_called_once_with(
                    root=Path('jlpt-notes'), config_path=Path('reader/mkdocs.yml'),
                    program_path=Path(sys.executable).resolve(), port=8765,
                    lan=True, configure_firewall=configure,
                )

    def test_failed_firewall_setup_forces_local_preview_even_with_existing_rules(self):
        from jlpt_notes.reader import headless

        with patch('jlpt_notes.reader.wsl.discover_lan', return_value=self.module().WslLan(
            '192.168.5.51', '192.168.5.0/24',
        )), patch('jlpt_notes.reader.wsl.configure_lan', side_effect=OSError('setup failed')), \
             patch.object(headless, 'ReaderController') as controller:
            controller.return_value.start.return_value = False
            headless.run(Path('notes'), Path('reader/mkdocs.yml'), Path(sys.executable),
                         lan=True, configure_firewall=True)
            self.assertTrue(controller.call_args.kwargs['local_only'])
            self.assertFalse(controller.call_args.kwargs.get('wsl_lan', False))
            controller.return_value.stop.assert_called_once()

    def test_accepts_only_private_windows_addresses_present_on_mirrored_guest(self):
        state = self.module().approved_lan(8765, runner=self.runner())
        self.assertEqual(state.address, '192.168.5.51')
        self.assertEqual(state.subnet, '192.168.5.0/24')

    def test_normalizes_windows_netmask_notation_without_widening_scope(self):
        firewall = firewall_state()
        firewall['Native'][0]['Remote'] = ['192.168.5.0/255.255.255.0']
        state = self.module().approved_lan(8765, runner=self.runner(firewall=firewall))
        self.assertEqual(state.subnet, '192.168.5.0/24')

    def test_rejects_nat_public_virtual_or_unmirrored_interfaces(self):
        public = {**network_row(), 'NetworkCategory': 'Public'}
        virtual = {**network_row(), 'Virtual': True}
        cases = (
            {'mode': 'nat'}, {'network': [public]}, {'network': [virtual]},
            {'guest': []}, {'guest': [{'flags': [], 'addr_info': []}]},
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises(NetworkInspectionError):
                self.module().discover_lan(runner=self.runner(**case))

    def test_requires_both_enabled_private_port_and_subnet_rules(self):
        cases = []
        for layer in ('Native', 'HyperV'):
            for key, value in (
                ('Enabled', 'False'), ('Profile', 'Public'), ('Profile', 'Any'),
                ('Protocol', 'UDP'), ('Ports', ['8765', '80']), ('Remote', ['Any']),
                ('Remote', ['192.168.0.0/16']), ('Local', ['Any']),
            ):
                state = firewall_state()
                state[layer][0][key] = value
                cases.append(state)
            state = firewall_state()
            state[layer] = []
            cases.append(state)
        for key in ('HostEnabled', 'HyperVEnabled', 'HyperVProfileEnabled', 'HostLocalRules', 'HyperVLocalRules'):
            state = firewall_state()
            state[key] = 'False'
            cases.append(state)
        state = firewall_state()
        state['HyperV'][0]['VMCreatorId'] = '{00000000-0000-0000-0000-000000000000}'
        cases.append(state)
        state = firewall_state()
        state['HyperV'].append(copy.deepcopy(state['HyperV'][0]))
        cases.append(state)
        for state in cases:
            with self.subTest(state=state), self.assertRaises(NetworkInspectionError):
                self.module().approved_lan(8765, runner=self.runner(firewall=state))

    def test_malformed_or_failed_inspection_is_a_clear_failure(self):
        for firewall in ('bad-data', {}, []):
            with self.subTest(firewall=firewall), self.assertRaises(NetworkInspectionError):
                self.module().approved_lan(8765, runner=self.runner(firewall=firewall))

        def unavailable(command, **kwargs):
            raise OSError('command unavailable')

        with self.assertRaises(NetworkInspectionError):
            self.module().discover_lan(runner=unavailable)

    def test_controller_serves_lan_with_source_filter_and_falls_back_when_rules_fail(self):
        module = self.module()
        config = Path(__file__).resolve().parents[2] / 'reader/mkdocs.yml'
        for approved in (True, False):
            with self.subTest(approved=approved), TemporaryDirectory() as directory:
                notes = Path(directory) / 'notes'
                notes.mkdir()
                card = notes / 'card.md'
                card.write_text('# LAN card\n\noriginal content\n', encoding='utf-8')
                original = (card.read_bytes(), card.stat().st_mtime_ns)
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                statuses = []
                controller = ReaderController(
                    notes, config, Path(sys.executable), port=port, on_status=statuses.append, wsl_lan=True,
                )
                state = module.WslLan('192.168.5.51', '192.168.5.0/24')
                with patch.object(module, 'approved_lan', return_value=state,
                                  side_effect=None if approved else NetworkInspectionError('missing rule')), \
                     patch('jlpt_notes.reader.controller.private_lan_addresses', side_effect=AssertionError('Windows GUI check')), \
                     patch('jlpt_notes.reader.controller.firewall_rule_present', side_effect=AssertionError('Windows GUI check')):
                    try:
                        self.assertTrue(controller.start())
                        self.assertEqual(statuses[-1].state, 'running' if approved else 'local-only')
                        host = controller._server._httpd.server_address[0]
                        self.assertEqual(host, '0.0.0.0' if approved else '127.0.0.1')
                        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                        try:
                            connection.request('GET', '/')
                            self.assertEqual(connection.getresponse().status, 200)
                        finally:
                            connection.close()
                        self.assertEqual((card.read_bytes(), card.stat().st_mtime_ns), original)
                    finally:
                        controller.stop()

    @unittest.skipUnless(shutil.which('wslpath') and shutil.which('powershell.exe'), 'requires WSL interop')
    def test_firewall_whatif_describes_only_the_private_lan_scope(self):
        script = Path(__file__).resolve().parents[2] / 'reader/configure-wsl-firewall.ps1'
        self.assertTrue(script.is_file(), 'WSL firewall configuration script is missing')
        windows_path = subprocess.check_output(['wslpath', '-w', str(script)], text=True).strip()
        completed = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', windows_path, '-Port', '8765', '-Address', '192.168.5.51',
             '-Subnet', '192.168.5.0/24', '-WhatIf'],
            capture_output=True, text=True, encoding='utf-8', timeout=10, check=True,
        )
        preview = json.loads(completed.stdout)
        self.assertNotEqual(preview['Native']['Name'], preview['HyperV']['Name'])
        self.assertEqual(preview['Native']['Profile'], 'Private')
        self.assertEqual(preview['Native']['LocalAddress'], '192.168.5.51')
        self.assertEqual(preview['Native']['RemoteAddress'], '192.168.5.0/24')
        self.assertEqual(preview['Native']['LocalPort'], 8765)
        self.assertEqual(preview['HyperV']['Profiles'], 'Private')
        self.assertEqual(preview['HyperV']['LocalAddresses'], '192.168.5.51')
        self.assertEqual(preview['HyperV']['RemoteAddresses'], '192.168.5.0/24')
        self.assertEqual(preview['HyperV']['LocalPorts'], 8765)
        self.assertEqual(preview['HyperV']['VMCreatorId'], '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}')
