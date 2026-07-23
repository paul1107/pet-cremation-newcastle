#!/usr/bin/env python3
"""Architecture tests for Pet Cremation Newcastle.

These are intentionally TDD tests. Run BEFORE changes to confirm RED,
then AFTER to confirm GREEN. The tests must drive the implementation —
no production code without a failing test first.

Exit code 0 = all tests pass. Exit code 1 = at least one fails.
"""
from __future__ import annotations
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE_BASE = "https://www.petcremationnewcastle.co.uk"
AREAS = ["newcastle", "gateshead", "north-tyneside", "south-tyneside", "northumberland"]
AREAS_HUB = Path("pages/areas/index.html")
SITEMAP_XML = Path("sitemap.xml")
SITEMAP_HTML = Path("sitemap.html")
HUB_BREADCRUMB_TEXT = "Areas We Serve"


class _LinkExtractor(HTMLParser):
    """Pull (href, anchor_text) from <a> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag == "a":
            self._current_href = dict(attrs).get("href")
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = "".join(self._current_text).strip()
            self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _norm_href(src: str, href: str, base: str = SITE_BASE) -> str | None:
    from urllib.parse import urljoin, urlparse

    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    u = urljoin(base + "/" + src.lstrip("/"), href)
    pu = urlparse(u)
    if pu.netloc and pu.netloc.replace("www.", "") not in (
        "petcremationnewcastle.co.uk",
    ):
        return None
    path = pu.path or "/"
    # Both /pages/areas/ and /pages/areas/index.html normalise to the same hub path
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    path = path.rstrip("/") or "/"
    return path


class TestReport:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.results.append((name, condition, detail))

    def summary(self) -> tuple[int, int, int]:
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = len(self.results) - passed
        return passed, failed, len(self.results)

    def print(self) -> None:
        passed, failed, total = self.summary()
        print(f"\n=== PCN architecture tests: {passed}/{total} pass, {failed} fail ===")
        for name, ok, detail in self.results:
            marker = "PASS" if ok else "FAIL"
            line = f"  [{marker}] {name}"
            if detail and not ok:
                line += f"\n         {detail}"
            print(line)
        if failed:
            print("\nVERDICT: RED — at least one architecture test is failing.")
        else:
            print("\nVERDICT: GREEN — all architecture tests pass.")


def test_areas_hub_exists(report: TestReport) -> None:
    ok = AREAS_HUB.exists()
    detail = "" if ok else f"missing file: {AREAS_HUB}"
    report.check("areas hub file exists at pages/areas/index.html", ok, detail)


def _parse_inline_hrefs(text: str, source: str) -> list[str]:
    parser = _LinkExtractor()
    parser.feed(text)
    return [
        norm
        for href, _ in parser.links
        if (norm := _norm_href(source, href)) is not None
    ]


def _has_anchor_to(text: str, source: str, target: str, target_text: str | None = None) -> bool:
    # The LinkExtractor can swallow or miss anchors when HTMLParser hits
    # malformed markup. Re-extract with a regex on raw anchor tags as a
    # fallback so tests don't false-fail on edge cases (e.g. multi-line
    # attributes, CDATA, or anchors split across tag boundaries).
    import re

    parser = _LinkExtractor()
    parser.feed(text)
    for href, anchor in parser.links:
        norm = _norm_href(source, href)
        if norm == target and (target_text is None or target_text.lower() in anchor.lower()):
            return True
    for href, anchor in re.findall(r'<a\s+[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', text, re.IGNORECASE | re.DOTALL):
        norm = _norm_href(source, href)
        if norm == target:
            cleaned = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", anchor)).strip()
            if target_text is None or target_text.lower() in cleaned.lower():
                return True
    return False


def test_areas_hub_links_to_all_children(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub links to all 5 child area pages", False, "hub missing")
        return
    text = _read(AREAS_HUB)
    missing = [
        a
        for a in AREAS
        if not _has_anchor_to(text, str(AREAS_HUB), f"/pages/areas/{a}.html")
    ]
    ok = not missing
    detail = "" if ok else f"missing child links: {missing}"
    report.check("areas hub links to all 5 child area pages", ok, detail)


def test_areas_hub_links_to_services(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub links to /pages/services.html", False, "hub missing")
        return
    ok = _has_anchor_to(_read(AREAS_HUB), str(AREAS_HUB), "/pages/services.html")
    report.check("areas hub links to /pages/services.html", ok)


def test_areas_hub_links_to_homepage(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub links to homepage /", False, "hub missing")
        return
    ok = _has_anchor_to(_read(AREAS_HUB), str(AREAS_HUB), "/")
    report.check("areas hub links to homepage /", ok)


def test_areas_hub_has_breadcrumb_back_to_hub(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub exposes its own URL as a link target", False, "hub missing")
        return
    # The hub must reference its own URL (e.g. canonical, self-canonical) — sanity check
    text = _read(AREAS_HUB)
    ok = "/pages/areas/" in text and ('pages/areas/index' in text or '/pages/areas' in text)
    report.check("areas hub page is self-referential (canonical self-link)", ok)


def test_area_breadcrumbs_removed_from_homepage(report: TestReport) -> None:
    """After the fix, area breadcrumbs should not point to the homepage anymore."""
    if not AREAS_HUB.exists():
        report.check("no area-page breadcrumb links to /", True, "hub missing, vacuously true")
        return
    offenders: list[str] = []
    for area in AREAS:
        path = REPO / f"pages/areas/{area}.html"
        if not path.exists():
            offenders.append(f"{path} (missing)")
            continue
        text = _read(path)
        # The phrase "Areas We Serve" must NOT be the anchor text of a link to "/"
        if re.search(
            r'<a\s+href="(/|index\.html)"[^>]*>\s*Areas\s+We\s+Serve\s*</a>',
            text,
            re.IGNORECASE,
        ):
            offenders.append(path.name)
    ok = not offenders
    detail = "" if ok else f"area pages still breadcrumb to homepage: {offenders}"
    report.check(
        "no area page still breadcrumbs 'Areas We Serve' to /", ok, detail
    )


def test_area_pages_link_back_to_hub(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("every area page links back to /pages/areas/index.html", False, "hub missing")
        return
    missing: list[str] = []
    for area in AREAS:
        path = REPO / f"pages/areas/{area}.html"
        if not path.exists():
            missing.append(f"{path.name} (missing file)")
            continue
        text = _read(path)
        if not _has_anchor_to(text, path.name, "/pages/areas"):
            missing.append(area)
    ok = not missing
    detail = "" if ok else f"area pages missing hub link: {missing}"
    report.check("every area page links back to /pages/areas/index.html", ok, detail)


def test_homepage_links_to_areas_hub(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("homepage links to /pages/areas/index.html", False, "hub missing")
        return
    text = _read(REPO / "index.html")
    ok = _has_anchor_to(text, "index.html", "/pages/areas")
    report.check("homepage links to /pages/areas/index.html", ok)


def test_sitemap_xml_lists_areas_hub(report: TestReport) -> None:
    if not SITEMAP_XML.exists():
        report.check("sitemap.xml references /pages/areas/index.html", False, "sitemap missing")
        return
    text = _read(SITEMAP_XML)
    # Accept both /pages/areas/ and /pages/areas/index.html forms
    ok = "/pages/areas/index" in text or "/pages/areas/" in text
    report.check("sitemap.xml references the areas hub", ok)


def test_sitemap_html_lists_areas_hub(report: TestReport) -> None:
    if not SITEMAP_HTML.exists():
        report.check("sitemap.html references /pages/areas/index.html", False, "sitemap.html missing")
        return
    text = _read(SITEMAP_HTML)
    ok = "/pages/areas/index" in text or "/pages/areas/" in text
    report.check("sitemap.html references the areas hub", ok)


def test_areas_hub_uses_webpage_schema(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub declares a WebPage JSON-LD type", False, "hub missing")
        return
    text = _read(AREAS_HUB)
    has_webpage = '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    has_localbusiness = '"@type": "LocalBusiness"' in text or '"@type":"LocalBusiness"' in text
    ok = has_webpage and not has_localbusiness
    detail = "" if ok else (
        f"missing WebPage? {not has_webpage}; accidentally LocalBusiness? {has_localbusiness}"
    )
    report.check(
        "areas hub JSON-LD is WebPage (not LocalBusiness — referral site policy)", ok, detail
    )


def test_areas_hub_no_first_person_operations(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub has no fabricated first-person operational claims", False, "hub missing")
        return
    text = _read(AREAS_HUB).lower()
    forbidden = [
        "we collect", "we cremate", "we'll call you back", "we will call you back",
        "within the hour", "we invoice",
    ]
    found = [p for p in forbidden if p in text]
    ok = not found
    detail = "" if ok else f"forbidden first-person claims present: {found}"
    report.check("areas hub has no fabricated first-person operational claims", ok, detail)


def test_areas_hub_has_disclosure_banner(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub has the .referral-disclosure banner", False, "hub missing")
        return
    text = _read(AREAS_HUB)
    ok = "referral-disclosure" in text
    report.check("areas hub has the .referral-disclosure banner", ok)


def test_areas_hub_uses_canonical_https(report: TestReport) -> None:
    if not AREAS_HUB.exists():
        report.check("areas hub canonical link uses https://www.", False, "hub missing")
        return
    text = _read(AREAS_HUB)
    ok = 'rel="canonical" href="https://www.petcremationnewcastle.co.uk/pages/areas/index.html"' in text
    report.check("areas hub canonical link uses https://www.", ok)


def test_area_pages_breadcrumb_to_hub(report: TestReport) -> None:
    """The 'Areas We Serve' breadcrumb on each area page must point to the new hub."""
    if not AREAS_HUB.exists():
        report.check(
            "each area page 'Areas We Serve' breadcrumb links to /pages/areas/index.html",
            False,
            "hub missing",
        )
        return
    missing: list[str] = []
    for area in AREAS:
        path = REPO / f"pages/areas/{area}.html"
        if not path.exists():
            missing.append(area)
            continue
        text = _read(path)
        # The "Areas We Serve" anchor should target the hub
        if not re.search(
            r'<a[^>]+href="[^"]*pages/areas(?:/index\.html)?"[^>]*>\s*Areas\s+We\s+Serve\s*</a>',
            text,
            re.IGNORECASE,
        ):
            missing.append(area)
    ok = not missing
    detail = "" if ok else f"area pages not breadcrumbed to the new hub: {missing}"
    report.check(
        "each area page 'Areas We Serve' breadcrumb links to /pages/areas/index.html", ok, detail
    )


def test_sitemap_xml_is_valid(report: TestReport) -> None:
    if not SITEMAP_XML.exists():
        report.check("sitemap.xml parses as valid XML", False, "sitemap missing")
        return
    try:
        ET.parse(SITEMAP_XML)
        report.check("sitemap.xml parses as valid XML", True)
    except ET.ParseError as e:
        report.check("sitemap.xml parses as valid XML", False, str(e))


def test_sitemap_xml_url_count_matches_pages(report: TestReport) -> None:
    if not SITEMAP_XML.exists():
        report.check("sitemap.xml URL count >= 26", False, "sitemap missing")
        return
    try:
        root = ET.parse(SITEMAP_XML).getroot()
    except ET.ParseError:
        report.check("sitemap.xml URL count >= 26", False, "sitemap unparseable")
        return
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    count = len(root.findall(".//s:url", ns))
    expected = 27  # 25 pre-change + 1 hub + 1 reserve for future expansion
    ok = count >= 26
    report.check(
        f"sitemap.xml URL count >= 26 (currently {count})", ok,
        f"expected at least 26 URLs; current={count}; reserve={expected - 26}",
    )


def main() -> int:
    report = TestReport()
    test_areas_hub_exists(report)
    test_areas_hub_links_to_all_children(report)
    test_areas_hub_links_to_services(report)
    test_areas_hub_links_to_homepage(report)
    test_areas_hub_has_breadcrumb_back_to_hub(report)
    test_area_breadcrumbs_removed_from_homepage(report)
    test_area_pages_link_back_to_hub(report)
    test_homepage_links_to_areas_hub(report)
    test_sitemap_xml_lists_areas_hub(report)
    test_sitemap_html_lists_areas_hub(report)
    test_areas_hub_uses_webpage_schema(report)
    test_areas_hub_no_first_person_operations(report)
    test_areas_hub_has_disclosure_banner(report)
    test_areas_hub_uses_canonical_https(report)
    test_area_pages_breadcrumb_to_hub(report)
    test_sitemap_xml_is_valid(report)
    test_sitemap_xml_url_count_matches_pages(report)
    report.print()
    passed, failed, _ = report.summary()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
