"""Command-line entry points for the JLPT note repository."""

import argparse
import sys
from datetime import date
from pathlib import Path

from .analytics import aggregate_attempts, render_daily_report
from .repository import Repository


class _ReaderArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        parsed = super().parse_args(args, namespace)
        if parsed.command == "reader":
            if parsed.lan and not parsed.headless:
                self.error("--lan 需要 --headless")
            if parsed.configure_firewall and not (parsed.headless and parsed.lan):
                self.error("--configure-firewall 需要 --headless --lan")
        return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = _ReaderArgumentParser(prog="jlpt-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("init", "create a learner data repository"), ("validate", "validate the repository"),
                            ("validate-links", "check publishable local image links without writing"),
                            ("validate-reader-links", "check local reader document and image links without writing"),
                            ("report-daily", "render today's read-only review brief"), ("backup", "create a local backup")):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--root", default="jlpt-notes")
    subparsers.choices["report-daily"].add_argument("--limit", type=int, default=15)
    reader = subparsers.add_parser("reader", help="open the manual iPad LAN reader")
    reader.add_argument("--root", default="jlpt-notes")
    reader.add_argument("--config", default="reader/mkdocs.yml")
    reader.add_argument("--port", type=_reader_port, default=8765)
    reader.add_argument("--headless", action="store_true", help="run in the terminal for local preview without a GUI")
    reader.add_argument("--lan", action="store_true", help="enable the mirrored WSL Private LAN after firewall checks")
    reader.add_argument("--configure-firewall", action="store_true", help="configure the reader's WSL Private LAN firewall rules")
    clean_cache = subparsers.add_parser('reader-cache-clean', help='clear this project\'s disposable reader cache')
    clean_cache.add_argument('--root', default='jlpt-notes')
    clean_cache.add_argument('--config', default='reader/mkdocs.yml')
    return parser


def main() -> int:
    """Run the command-line application."""
    args = build_parser().parse_args()
    if args.command == 'reader-cache-clean':
        from .reader.cache import ReaderCache
        cache = ReaderCache(Path(args.root), Path(args.config))
        try:
            removed = cache.clear()
        except (OSError, ValueError) as error:
            print(f'缓存清理未完成：{error}', file=sys.stderr)
            return 1
        print(f'已清理本项目 {removed} 个页面缓存版本：{cache.directory}')
        return 0
    if args.command == "reader":
        if args.headless:
            from .reader.headless import run
        else:
            from .reader.launcher import run

        return run(
            root=Path(args.root),
            config_path=Path(args.config),
            program_path=Path(sys.executable).resolve(),
            port=args.port,
            **({"lan": True, "configure_firewall": args.configure_firewall} if args.lan else {}),
        )
    repo = Repository(Path(args.root))
    if args.command == "init":
        repo.init_layout()
        print(f"已创建资料库：{repo.root}")
    elif args.command in {"validate", "validate-links", "validate-reader-links"}:
        from .asset_links import audit_assets

        if not repo.root.is_dir():
            print(f"资料库不存在：{repo.root}", file=sys.stderr)
            return 1
        issues = audit_assets(repo.root)
        if args.command == 'validate-reader-links':
            from .reader.links import audit_document_links
            issues += audit_document_links(repo.root)
        for issue in issues:
            print(issue, file=sys.stderr)
        if issues:
            print(f"发现 {len(issues)} 个资源链接问题", file=sys.stderr)
            return 1
        print('阅读器资源链接校验通过' if args.command == 'validate-reader-links' else '图片资源链接校验通过')
    elif args.command == "report-daily":
        repo.init_layout()
        print(render_daily_report(aggregate_attempts([]), 0, 0, 0, args.limit))
    elif args.command == "backup":
        print(repo.create_backup(date.today()))
    return 0


def _reader_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("端口必须是整数") from error
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须是 1024 到 65535 之间的整数")
    return port
