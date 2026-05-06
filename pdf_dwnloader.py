#!/usr/bin/env python3
"""
Local PDF downloader with resume support and download_report.json output.

Usage:
    python pdf_dwnloader.py --download --input agrirxiv_final_data.json

By default it writes PDFs to ./downloaded_files and the report to ./download_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Tuple
from urllib.parse import urljoin

import requests
from urllib import robotparser
try:
    from seleniumbase import SB
except Exception:
    SB = None

ROBOTS_TXT = '''
Sitemap: https://www.cabidigitallibrary.org/sitemap-index-1.txt
User-agent: *
Disallow: /action
Disallow: /help
Disallow: /search
Disallow: /feedback
Disallow: /rss
Disallow: /page/account-confirmation-thanks
Disallow: /media
Disallow: /medical-research
Disallow: /servlet/linkout
Disallow: /na101/
Disallow: /na101v1/
Disallow: /na102/
Disallow: /doi/mlt/
Disallow: /topic
Disallow: /author/
Disallow: /doi/metrics/
Disallow: /authored-by/
Disallow: /history/
Allow: /action/showJournal
Allow: /action/showPublications
Allow: /action/showXml
Allow: /action/showTopic
Allow: /action/showBook
Allow: /action/showCoverImage
Allow: /.well-known/tdmrep.json

User-agent: facebookexternalhit
User-agent: LinkedInBot
User-agent: Twitterbot
Allow: /

User-agent: GPTBot
Disallow: /

Crawl-delay: 1
'''

DEFAULT_USER_AGENT = 'Mozilla/5.0 (compatible; PDFDownloaderLocal/1.0; +https://example.org/)'


def sanitize_filename(value: str, max_length: int = 180) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', '_', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value[:max_length].rstrip(' ._') or 'downloaded_file'


def build_pdf_filename(article: dict) -> str:
    doi = article.get('doi') or ''
    title = article.get('title') or 'article'
    base = sanitize_filename(doi.replace('/', '_') if doi else title)
    return f"{base}.pdf"


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json_atomic(path: Path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


class RobotsChecker:
    def __init__(self, robots_txt: str, user_agent: str):
        self.parser = robotparser.RobotFileParser()
        self.parser.parse(robots_txt.splitlines())
        self.user_agent = user_agent

    def is_allowed(self, url: str) -> bool:
        try:
            return self.parser.can_fetch(self.user_agent, url)
        except Exception:
            return False


def download_pdf_securely(url: str, target_path: Path, cookies: dict, user_agent: str, referer: str, timeout: int = 30) -> Tuple[bool, str]:
    """Download a PDF directly to disk using verified cookies and browser headers."""
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and target_path.stat().st_size > 0:
        return True, str(target_path.resolve())

    temp_path = target_path.with_suffix(target_path.suffix + '.part')

    try:
        request_headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': referer,
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }

        with requests.Session() as verified_session:
            verified_session.cookies.update(cookies)
            verified_session.headers.update(request_headers)

            response = verified_session.get(url, stream=True, timeout=timeout, allow_redirects=True)
            if response.status_code != 200:
                return False, f'HTTP {response.status_code}'

            with open(temp_path, 'wb') as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)

        if temp_path.exists() and temp_path.stat().st_size > 0:
            temp_path.replace(target_path)
            return True, str(target_path.resolve())

        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False, 'empty'

    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False, str(exc)


def download_with_resume(session: requests.Session, url: str, out_path: Path, headers: dict, timeout: int = 90) -> Tuple[bool, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix('.pdf.part')

    # If final file exists and non-empty, skip
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, str(out_path)

    existing = tmp_path.stat().st_size if tmp_path.exists() else 0

    req_headers = dict(headers)
    if existing > 0:
        req_headers['Range'] = f'bytes={existing}-'

    try:
        with session.get(url, headers=req_headers, stream=True, timeout=timeout) as resp:
            if resp.status_code in (403, 401):
                return False, f'HTTP {resp.status_code}'

            if resp.status_code == 416:
                # Range not satisfiable; assume complete
                if tmp_path.exists():
                    tmp_path.rename(out_path)
                    return True, str(out_path)
                return False, f'HTTP {resp.status_code}'

            if resp.status_code not in (200, 206):
                return False, f'HTTP {resp.status_code}'

            mode = 'ab' if existing > 0 and resp.status_code == 206 else 'wb'
            with open(tmp_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)

        # basic validation: non-empty
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            tmp_path.replace(out_path)
            return True, str(out_path)

        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False, 'empty'

    except Exception as exc:
        return False, str(exc)


def selenium_verified_download_context(pdf_url: str, base_url: str, wait_timeout: int = 300) -> Tuple[dict, str, str, str]:
    """Open viewer, wait for human verification, then return cookies, final URL, referer, and browser UA."""
    if SB is None:
        print("ERROR: SeleniumBase not available for human verification.")
        return {}, '', '', ''

    try:
        print(f"\n{'='*70}")
        print(f"Opening {pdf_url} in browser for human verification...")
        print(f"{'='*70}")
        print("Please complete any verification steps (CAPTCHA, login, etc.) in the browser.")
        print("Do not click browser download. Just complete verification and keep the viewer tab open.")
        print("The script will download the PDF into your output folder after verification succeeds.")
        print(f"{'='*70}\n")

        with SB(uc=True, test=True, locale='en') as sb:
            # Open the page directly first; reconnect can fail on some Chrome/UC states.
            try:
                sb.open(pdf_url)
            except Exception:
                sb.uc_open_with_reconnect(pdf_url, 10)
            sb.sleep(4)

            # Different page variants expose different selectors for the final PDF URL.
            candidate_selectors = [
                'a.navbar-download',
                'a.btn--pdf',
                'a[href*="/doi/pdf/"]',
                'a[href$=".pdf"]',
                'iframe[src*="pdf"]',
                'embed[type="application/pdf"]',
                'object[type="application/pdf"]',
            ]

            def _extract_final_url() -> str:
                for selector in candidate_selectors:
                    if sb.is_element_present(selector):
                        href = sb.get_attribute(selector, 'href') or sb.get_attribute(selector, 'src') or ''
                        if href:
                            return urljoin(base_url, href)

                current_url = ''
                try:
                    current_url = sb.get_current_url() or ''
                except Exception:
                    current_url = ''
                if current_url:
                    # If we are already at a direct PDF endpoint, use it.
                    if '.pdf' in current_url.lower() or '/doi/pdf/' in current_url.lower():
                        return current_url
                return ''

            deadline = time.time() + wait_timeout
            last_status_log = 0.0

            while time.time() < deadline:
                # Verification flows sometimes open a new tab/window; stay on the latest one.
                try:
                    handles = sb.driver.window_handles
                    if handles:
                        sb.driver.switch_to.window(handles[-1])
                except Exception:
                    pass

                final_url = _extract_final_url()
                if final_url:
                    cookies = {}
                    try:
                        raw = sb.get_cookies()
                    except Exception:
                        try:
                            raw = sb.driver.get_cookies()
                        except Exception:
                            raw = []

                    for c in raw:
                        name = c.get('name')
                        val = c.get('value')
                        if name and val is not None:
                            cookies[name] = val

                    referer_url = ''
                    browser_ua = ''
                    try:
                        referer_url = sb.get_current_url() or ''
                    except Exception:
                        referer_url = ''
                    try:
                        browser_ua = sb.execute_script('return navigator.userAgent') or ''
                    except Exception:
                        browser_ua = ''

                    print(f"PDF viewer ready. Extracted {len(cookies)} cookies from verified session.")
                    return cookies, final_url, referer_url, browser_ua

                now = time.time()
                if now - last_status_log >= 10:
                    current_url = ''
                    title = ''
                    try:
                        current_url = sb.get_current_url() or ''
                    except Exception:
                        current_url = ''
                    try:
                        title = sb.get_title() or ''
                    except Exception:
                        title = ''
                    print(
                        "Waiting for verification / PDF viewer to become ready... "
                        f"(url={current_url or 'n/a'}, title={title or 'n/a'})"
                    )
                    last_status_log = now

                sb.sleep(2)

            print(
                "Verification timed out before a PDF/download element became available. "
                "Please confirm the CAPTCHA/login was completed and the PDF viewer tab is open."
            )
            return {}, '', '', ''
    except Exception as e:
        print(f"ERROR during human verification: {e}")
        return {}, '', '', ''


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Download PDFs from agrirxiv_final_data.json with resume support and robots compliance',
        epilog='Examples:\n  python pdf_dwnloader.py --download\n  python pdf_dwnloader.py --download -i agrirxiv_final_data.json -o downloaded_files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument('--download', action='store_true', help='Download-only mode: reads PDF URLs from input JSON and downloads them')
    p.add_argument('--input', '-i', default='agrirxiv_final_data.json', help='Input JSON with article metadata (default: agrirxiv_final_data.json)')
    p.add_argument('--output-dir', '-o', default='downloaded_files', help='Local folder to save PDFs (default: downloaded_files)')
    p.add_argument('--report', '-r', default='download_report.json', help='Output report JSON (default: download_report.json)')
    p.add_argument('--delay', '-d', type=float, default=1.0, help='Seconds between requests (default: 1.0)')
    p.add_argument('--user-agent', default=DEFAULT_USER_AGENT, help='Custom User-Agent string')
    p.add_argument('--timeout', type=int, default=90, help='HTTP request timeout in seconds (default: 90)')
    args = p.parse_args(argv)

    if not args.download:
        print('Error: --download flag is required. Use: python pdf_dwnloader.py --download', file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Input file not found: {input_path}', file=sys.stderr)
        sys.exit(2)

    articles = load_json(input_path)
    if not isinstance(articles, list):
        print('Expected a list of article records in the input JSON', file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = Path(args.report)
    existing_report = []
    if report_path.exists():
        try:
            existing_report = load_json(report_path)
        except Exception:
            existing_report = []

    # map DOI or link to status from existing report for quick lookup
    existing_index = {}
    for rec in existing_report:
        key = rec.get('doi') or rec.get('link') or rec.get('title')
        if key:
            existing_index[key] = rec

    robots = RobotsChecker(ROBOTS_TXT, args.user_agent)

    session = requests.Session()
    session.headers.update({'User-Agent': args.user_agent, 'Accept': 'application/pdf,application/octet-stream,*/*'})

    report = []
    downloaded = 0

    for article in articles:
        key = article.get('doi') or article.get('link') or article.get('title')
        rec = dict(article)

        # If previous report already marked success, reuse
        prev = existing_index.get(key)
        if prev and prev.get('download_status'):
            rec['pdf_path'] = prev.get('pdf_path', '')
            rec['download_status'] = True
            report.append(rec)
            continue

        pdf_url = article.get('pdf_url')
        rec['pdf_path'] = ''
        rec['download_status'] = False

        if not article.get('is_pdf_available') or not pdf_url:
            report.append(rec)
            continue

        if not robots.is_allowed(pdf_url):
            print(f"SKIP robots blocked: {key}")
            report.append(rec)
            continue

        filename = build_pdf_filename(article)
        out_path = out_dir / filename

        # Try direct download first using secure method with session headers
        direct_cookies = requests.utils.dict_from_cookiejar(session.cookies)
        success, info = download_pdf_securely(
            pdf_url,
            out_path,
            cookies=direct_cookies,
            user_agent=session.headers.get('User-Agent', args.user_agent),
            referer='https://www.cabidigitallibrary.org',
            timeout=args.timeout,
        )
        
        if success:
            rec['pdf_path'] = str(out_path.resolve())
            rec['download_status'] = True
            downloaded += 1
            print(f'Downloaded: {key} -> {out_path.name}')
        else:
            # Download failed; record error and continue to next PDF
            rec['pdf_path'] = ''
            rec['download_status'] = False
            rec['download_error'] = info
            print(f'Failed: {key} -> {info}')

        report.append(rec)

        # incremental save so we can resume the report
        try:
            save_json_atomic(report_path, report)
        except Exception as e:
            print('Warning: failed to save report incrementally:', e)

        time.sleep(args.delay)

    # final save (merge with any remaining items not processed)
    try:
        save_json_atomic(report_path, report)
    except Exception as e:
        print('Error saving final report:', e)

    print(f'Finished. Downloaded {downloaded} PDFs out of {len(articles)} records.')
    print(f'Report saved to: {report_path}')


if __name__ == '__main__':
    main()
