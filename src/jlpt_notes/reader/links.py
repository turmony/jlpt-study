"""Resolve original document links against the reader's publication snapshot."""

import posixpath
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..asset_links import IMAGE_SUFFIXES, rendered_links

EVIDENCE_SUFFIXES = frozenset({'.txt', '.json'})


def local_target(source: Path, href: str) -> Path | None:
    """Return a root-relative source target; external and self links have none."""
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path)
    if path.startswith('/') or '\\' in path or '\x00' in path:
        raise ValueError('不支持的本地地址')
    relative = posixpath.normpath(posixpath.join(source.parent.as_posix(), path))
    if relative == '..' or relative.startswith('../'):
        raise ValueError('目标越出资料库')
    return Path(relative)


def is_evidence_path(path: Path) -> bool:
    return (path.parts[:2] == ('quizzes', 'sources')
            and path.suffix.lower() in EVIDENCE_SUFFIXES)


@dataclass(frozen=True)
class DocumentLinkIssue:
    source: str
    link: str
    target: str
    reason: str

    def __str__(self) -> str:
        return f'{self.source}: 本地链接 {self.link!r} → {self.target}（{self.reason}）'


class DocumentIndex:
    """Use the same eligible pages for auditing and rendering; never guess names."""

    def __init__(self, root: Path, pages, *, additional_paths=()) -> None:
        self.root = root.resolve(strict=True)
        self.paths = frozenset(page.relative_path for page in pages) | frozenset(additional_paths)

    def issue(self, source: Path, href: str) -> DocumentLinkIssue | None:
        try:
            target = local_target(source, href)
        except ValueError as error:
            return DocumentLinkIssue(source.as_posix(), href, '无法解析', str(error))
        if target is None or target.suffix.lower() in IMAGE_SUFFIXES or target in self.paths:
            return None
        if any(part.startswith('.') for part in target.parts):
            reason = '不允许发布隐藏文件或目录'
        elif not (self.root / target).is_file():
            reason = '目标不存在或不是文件'
        else:
            reason = '不允许发布此文件类型或链接文件'
        return DocumentLinkIssue(source.as_posix(), href, target.as_posix(), reason)

    def check(self, source: Path, body: str) -> tuple[DocumentLinkIssue, ...]:
        return tuple(dict.fromkeys(
            issue for href, image in rendered_links(body) if not image
            if (issue := self.issue(source, href)) is not None
        ))


def audit_document_links(root: Path) -> tuple[DocumentLinkIssue, ...]:
    """Read-only check of every document's local, non-image links."""
    from .sources import load_source_pages

    pages = load_source_pages(root)
    index = DocumentIndex(root, pages)
    return tuple(issue for page in pages for issue in index.check(page.relative_path, page.markdown))


def audit_prospective_documents(root: Path, documents: dict[Path, str], *, generated_paths=()) -> tuple:
    """Check new output before writing, allowing other files in that same batch."""
    from ..asset_links import AssetIndex
    from .metadata import parse_markdown
    from .sources import (
        _is_directory_link,
        iter_supported_visible_source_files,
        iter_visible_evidence,
    )

    resolved = root.resolve(strict=True)
    destination_issues = []
    for relative in (*documents, *generated_paths):
        reason = None
        if relative.anchor or '\x00' in str(relative) or '..' in relative.parts:
            reason = '目标越出资料库'
        elif any(part.startswith('.') for part in relative.parts):
            reason = '不允许发布隐藏文件或目录'
        elif relative.suffix.lower() not in {'.md', '.jsonl'} and not is_evidence_path(relative):
            reason = '不允许发布此文件类型'
        else:
            path = resolved
            for part in relative.parts:
                path /= part
                if path.is_symlink() or (path.exists() and _is_directory_link(path)):
                    reason = '不允许发布链接文件或目录'
                    break
        if reason:
            destination_issues.append(DocumentLinkIssue(relative.as_posix(), relative.as_posix(),
                                                        relative.as_posix(), reason))
    if destination_issues:
        return tuple(destination_issues)
    existing = (path.relative_to(resolved)
                for path in (*iter_supported_visible_source_files(root), *iter_visible_evidence(root)))
    index = DocumentIndex(root, (), additional_paths=(*existing, *documents, *generated_paths))
    assets = AssetIndex(root)
    issues = []
    for relative, text in documents.items():
        body = parse_markdown(relative, text).body
        issues.extend(index.check(relative, body))
        issues.extend(assets.check(relative, body))
    return tuple(issues)
