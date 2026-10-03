import json
import re
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urljoin, urlsplit

from jlpt_notes.reader.builder import build_site
from jlpt_notes.reader.watcher import snapshot_sources

CONFIG = Path(__file__).resolve().parents[2] / 'reader/mkdocs.yml'


def test_document_links_resolve_without_changing_code_or_external_links(caplog):
    with TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / 'notes'
        draft = root / 'drafts/draft.md'
        card = root / 'grammar/n3/N3-G-0031.md'
        draft.parent.mkdir(parents=True)
        card.parent.mkdir(parents=True)
        card.write_text('# Grammar\n\n## Detail\n', encoding='utf-8')
        (root / 'events.jsonl').write_text('{}\n', encoding='utf-8')
        draft.write_text(
            '# Draft\n\n[formal](../grammar/n3/N3-G-0031.md?view=1#detail)\n\n'
            '[reference][card]\n\n[card]: ../grammar/n3/N3-G-0031.md\n\n'
            '[events](../events.jsonl)\n\n'
            '[external](https://example.com/card.md)\n\n'
            '`[code](../grammar/n3/N3-G-0031.md)`\n', encoding='utf-8'
        )
        before = draft.read_bytes()
        site = base / 'site'
        result = build_site(root, CONFIG, site)
        assert result.success, result.error
        assert 'not found among documentation files' not in caplog.text
        page = site / 'library/drafts/draft.md.__reader_markdown__/index.html'
        html = page.read_text(encoding='utf-8')
        for label in ('formal', 'reference', 'events'):
            href = re.search(r'<a href="([^"]+)">' + label + '</a>', html)[1]
            url = urlsplit(urljoin('/' + page.relative_to(site).as_posix(), href))
            assert (site / unquote(url.path).lstrip('/') / 'index.html').is_file()
            if label == 'formal':
                assert url.query == 'view=1'
                assert url.fragment == 'detail'
        assert 'href="https://example.com/card.md"' in html
        assert '<code>[code](../grammar/n3/N3-G-0031.md)</code>' in html
        assert draft.read_bytes() == before


def _write(root, relative, body):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')
    return path


def _html(site, relative):
    return (site / 'library' / relative.parent /
            f'{relative.name}.__reader_markdown__' / 'index.html').read_text(encoding='utf-8')


def _linked_page(site, relative, html, label):
    href = re.search(r'<a[^>]*href="([^"]+)"[^>]*>' + label + '</a>', html)[1]
    base = '/library/' + relative.parent.as_posix() + '/' + relative.name + '.__reader_markdown__/'
    url = urlsplit(urljoin(base, unescape(href)))
    target = site / unquote(url.path).lstrip('/') / 'index.html'
    assert target.is_file(), href
    return target, url


def test_linked_quiz_evidence_is_safe_readable_and_outside_catalog_and_search(tmp_path, caplog):
    root = tmp_path / 'notes'
    relative = Path('quizzes/answers/test.md')
    answer = _write(root, relative,
                    '[text](../sources/test/page.md.txt)\n\n'
                    '[manifest][m]\n\n[m]: ../sources/test/清单%20%281%29.json?view=1\n\n'
                    '<a href="../sources/test/清单%20%281%29.json?view=2">raw</a>\n\n'
                    '`[literal](../sources/test/missing.txt)`\n')
    text = _write(root, 'quizzes/sources/test/page.md.txt',
                  'UNIQUE_EVIDENCE_TEXT <script>alert(1)</script> [fake](missing.md)')
    manifest = _write(root, 'quizzes/sources/test/清单 (1).json', '{"marker":"UNIQUE_MANIFEST_TEXT"}')
    _write(root, 'quizzes/sources/test/unreferenced.txt', 'PRIVATE_UNREFERENCED')
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (answer, text, manifest)}
    site = tmp_path / 'site'
    result = build_site(root, CONFIG, site)
    assert result.success and not result.warnings, result
    assert 'not found among documentation files' not in caplog.text
    html = _html(site, relative)
    target, _ = _linked_page(site, relative, html, 'text')
    evidence_html = target.read_text(encoding='utf-8')
    assert 'UNIQUE_EVIDENCE_TEXT' in evidence_html
    assert '&lt;script&gt;' in evidence_html and '<script>alert(1)</script>' not in evidence_html
    assert '[fake](missing.md)' in evidence_html
    for label, view in [('manifest', '1'), ('raw', '2')]:
        target, url = _linked_page(site, relative, html, label)
        assert url.query == 'view=' + view
        assert 'UNIQUE_MANIFEST_TEXT' in target.read_text(encoding='utf-8')
    assert '<code>[literal](../sources/test/missing.txt)</code>' in html
    catalog = (site / 'index.html').read_text(encoding='utf-8')
    search = (site / 'search/search_index.json').read_text(encoding='utf-8')
    assert '__reader_evidence__' not in catalog
    assert 'UNIQUE_EVIDENCE_TEXT' not in search and 'UNIQUE_MANIFEST_TEXT' not in search
    assert not list(site.rglob('*.md.txt')) and not list(site.rglob('清单*.json'))
    assert 'PRIVATE_UNREFERENCED' not in ''.join(p.read_text(encoding='utf-8') for p in site.rglob('*.html'))
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before


def test_unavailable_local_links_have_explanation_and_no_dead_href(tmp_path, caplog):
    root = tmp_path / 'notes'
    _write(root, 'card.md', '[missing](missing.md)\n\n[again](missing.md)\n\n'
           '[private](.hidden.md)\n\n[unsupported](secret.txt)\n\n'
           '<a href="missing.md">raw missing</a>\n\n'
           '[escape](../outside.md)\n\n[external](https://example.com/page.md)\n')
    _write(root, '.hidden.md', 'hidden')
    _write(root, 'secret.txt', 'private')
    site = tmp_path / 'site'
    result = build_site(root, CONFIG, site)
    assert result.success, result.error
    assert len(result.warnings) == 4
    assert 'not found among documentation files' not in caplog.text
    html = _html(site, Path('card.md'))
    for href in ('missing.md', '.hidden.md', 'secret.txt', '../outside.md'):
        assert f'href="{href}"' not in html
    assert '本地链接' in html and '不允许发布' in html
    assert 'href="https://example.com/page.md"' in html


def test_evidence_lifecycle_and_new_quizzes_refresh_incremental_site(tmp_path, caplog):
    root = tmp_path / 'notes'
    rel = Path('quizzes/answers/first.md')
    _write(root, rel, '[evidence](../sources/first/manifest.json)\n')
    sites = [tmp_path / f'site-{n}' for n in range(5)]
    first = build_site(root, CONFIG, sites[0])
    assert first.success and first.warnings
    before = snapshot_sources(root)
    evidence = _write(root, 'quizzes/sources/first/manifest.json', '{"value":"FIRST_VALUE"}')
    assert snapshot_sources(root) != before
    second = build_site(root, CONFIG, sites[1], previous_site=sites[0])
    assert second.success and not second.warnings
    target, _ = _linked_page(sites[1], rel, _html(sites[1], rel), 'evidence')
    assert 'FIRST_VALUE' in target.read_text(encoding='utf-8')
    before = snapshot_sources(root)
    evidence.write_text('{"value":"NEXT_VALUE!"}', encoding='utf-8')
    assert snapshot_sources(root) != before
    third = build_site(root, CONFIG, sites[2], previous_site=sites[1])
    assert third.success and third.version != second.version
    target, _ = _linked_page(sites[2], rel, _html(sites[2], rel), 'evidence')
    assert 'NEXT_VALUE!' in target.read_text(encoding='utf-8')
    _write(root, 'quizzes/answers/second.md', '[new](../sources/second/page.md.txt)\n')
    _write(root, 'quizzes/sources/second/page.md.txt', 'second quiz evidence')
    fourth = build_site(root, CONFIG, sites[3], previous_site=sites[2])
    assert fourth.success and not fourth.warnings
    _linked_page(sites[3], rel, _html(sites[3], rel), 'evidence')
    evidence.unlink()
    final = build_site(root, CONFIG, sites[4], previous_site=sites[3])
    assert final.success and final.warnings
    assert 'href="../sources/first/manifest.json"' not in _html(sites[4], rel)
    assert not (sites[4] / target.relative_to(sites[2])).exists()
    full_site = tmp_path / 'full'
    full = build_site(root, CONFIG, full_site)
    assert full.success and full.version == final.version
    assert json.loads((full_site / 'search/search_index.json').read_text(encoding='utf-8')) == json.loads(
        (sites[4] / 'search/search_index.json').read_text(encoding='utf-8'))
    assert 'not found among documentation files' not in caplog.text


def test_raw_link_policy_cannot_be_bypassed_by_generated_css_class(tmp_path):
    root = tmp_path / 'notes'
    _write(root, 'card.md', '<a class="jlpt-card-pager__link" href="missing.md">bad</a>\n\n'
           '<a href="/private.json">absolute</a>\n\n'
           '[absolute](/private.json)\n')
    result = build_site(root, CONFIG, tmp_path / 'site')
    assert result.success and len(result.warnings) == 2
    html = _html(tmp_path / 'site', Path('card.md'))
    assert 'href="missing.md"' not in html and 'href="/private.json"' not in html


def test_multiline_raw_html_anchors_use_the_same_document_policy(tmp_path):
    root = tmp_path / 'notes'
    _write(root, 'target.md', '# Target\n\n## Detail\n')
    _write(root, 'card.md', '<a\nhref="target.md?view=1#detail">good</a>\n\n'
           '<a\thref="missing.md">bad</a>\n')
    site = tmp_path / 'site'
    result = build_site(root, CONFIG, site)
    assert result.success and len(result.warnings) == 1
    html = _html(site, Path('card.md'))
    _, url = _linked_page(site, Path('card.md'), html, 'good')
    assert url.query == 'view=1' and url.fragment == 'detail'
    assert 'href="missing.md"' not in html


def test_author_html_and_markdown_cannot_use_outside_source_paths_as_generated_routes(tmp_path):
    root = tmp_path / 'notes'
    _write(root, 'target.md', '# Target\n')
    _write(root, 'card.md', '<a href="../target.md.__reader_markdown__/">raw</a>\n\n'
           '[ordinary](../target.md.__reader_markdown__/)\n')
    result = build_site(root, CONFIG, tmp_path / 'site')
    assert result.success and len(result.warnings) == 1
    article = _html(tmp_path / 'site', Path('card.md')).split('<article', 1)[1].split('</article>', 1)[0]
    assert 'href="../target.md.__reader_markdown__/"' not in article


def test_source_metadata_cannot_claim_generated_catalog_link_policy(tmp_path):
    root = tmp_path / 'notes'
    _write(root, 'card.md', '---\n{"kind":"catalog"}\n---\n\n'
           '<a href="missing.md">bad</a>\n')
    result = build_site(root, CONFIG, tmp_path / 'site')
    assert result.success and result.warnings
    assert 'href="missing.md"' not in _html(tmp_path / 'site', Path('card.md'))


def test_prospective_documents_reject_windows_rooted_paths_without_writing(tmp_path):
    from jlpt_notes.reader.links import audit_prospective_documents

    assert audit_prospective_documents(tmp_path, {Path('/outside.md'): 'No links'})
    assert not list(tmp_path.iterdir())


def test_corrupt_evidence_and_internal_symlinks_do_not_break_source_policy(tmp_path):
    root = tmp_path / 'notes'
    _write(root, 'card.md', '[json](quizzes/sources/bad.json)\n\n'
           '[alias](quizzes/sources/alias.txt)\n')
    original = _write(root, 'quizzes/sources/real.txt', 'not published through alias')
    alias = root / 'quizzes/sources/alias.txt'
    try:
        alias.symlink_to(original)
    except OSError:
        import pytest
        pytest.skip('symlink privileges unavailable')
    _write(root, 'quizzes/sources/bad.json', '{broken')
    site = tmp_path / 'site'
    result = build_site(root, CONFIG, site)
    assert result.success and result.warnings
    html = _html(site, Path('card.md'))
    target, _ = _linked_page(site, Path('card.md'), html, 'json')
    assert 'JSON 无法解析' in target.read_text(encoding='utf-8')
    assert 'href="quizzes/sources/alias.txt"' not in html
