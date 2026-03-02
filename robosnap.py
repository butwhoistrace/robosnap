#!/usr/bin/env python3
"""
RoboSnap - robots.txt Checker

Usage:
  python3 robosnap.py <url>                 Basic scan
  python3 robosnap.py <url> --filter        Highlight interesting paths
  python3 robosnap.py <url> --probe         Check status codes of found paths
  python3 robosnap.py <url> --headers       Show HTTP response headers
  python3 robosnap.py <url> --sitemap       Fetch referenced sitemaps
  python3 robosnap.py <url> --export json   Export results as JSON
  python3 robosnap.py <url> --export csv    Export results as CSV
  python3 robosnap.py --bulk domains.txt    Scan multiple domains from file
  python3 robosnap.py                       Interactive mode

Flags can be combined:
  python3 robosnap.py example.com --filter --probe --headers --sitemap --export json
"""

import sys
import os
import time
import json
import csv
import shutil
import argparse
import requests
from urllib.parse import urlparse

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"

BANNER = (
    "\n"
    f"  {CYAN}\u2588\u2580\u2588 \u2588\u2580\u2588 \u2588\u2584\u2584 \u2588\u2580\u2588 {WHITE}\u2588\u2580 \u2588\u2584 \u2588 \u2584\u2580\u2588 \u2588\u2580\u2588\n"
    f"  {CYAN}\u2588\u2580\u2584 \u2588\u2584\u2588 \u2588\u2584\u2588 \u2588\u2584\u2588 {WHITE}\u2584\u2588 \u2588 \u2580\u2588 \u2588\u2580\u2588 \u2588\u2580\u2580{RESET}\n"
)

INTERESTING_KEYWORDS = [
    "admin", "backup", "config", "secret", "hidden", "internal",
    "private", "debug", "test", "staging", "api", "login",
    "dashboard", "database", "dump", "env", "password", "user",
    "data", "upload", "panel", "manage", "console", "dev",
    "old", "tmp", "temp", "bak", "sql", "log", "cgi-bin"
]


def loading_bar():
    width = min(shutil.get_terminal_size().columns - 10, 40)
    block = "\u2588"
    empty = "\u2591"
    for i in range(width + 1):
        bar = block * i + empty * (width - i)
        print(f"\r  {CYAN}{bar}{RESET}", end="", flush=True)
        time.sleep(0.02)
    print()


def normalize_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return parsed, f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def get_disallow_paths(content):
    paths = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("disallow:"):
            path = stripped.split(":", 1)[1].strip()
            if path:
                paths.append(path)
    return paths


def get_sitemap_urls(content):
    urls = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped.split(":", 1)[1].strip()
            if url:
                urls.append(url)
    return urls


# === FEATURE: --filter ===
def filter_interesting(paths):
    interesting = []
    for path in paths:
        for kw in INTERESTING_KEYWORDS:
            if kw in path.lower():
                interesting.append(path)
                break
    return interesting


# === FEATURE: --probe ===
def probe_paths(base_url, paths):
    results = []
    print(f"\n  {BOLD}Probing {len(paths)} paths...{RESET}\n")
    for path in paths:
        if "*" in path or "$" in path or "?" in path:
            continue
        url = f"{base_url}{path}"
        try:
            r = requests.head(url, timeout=5, allow_redirects=False, headers={
                "User-Agent": "RoboSnap/1.0"
            })
            code = r.status_code
            if code == 200:
                color = GREEN
            elif code in (301, 302):
                color = YELLOW
            elif code == 403:
                color = RED
            else:
                color = DIM
            print(f"  {color}{code}{RESET}  {path}")
            results.append({"path": path, "status": code})
        except requests.RequestException:
            print(f"  {DIM}ERR{RESET}  {path}")
            results.append({"path": path, "status": "ERR"})
    return results


# === FEATURE: --headers ===
def show_headers(base_url):
    print(f"\n  {BOLD}HTTP Headers{RESET}\n")
    try:
        r = requests.head(base_url, timeout=5, headers={
            "User-Agent": "RoboSnap/1.0"
        })
        interesting_headers = [
            "server", "x-powered-by", "x-frame-options",
            "x-content-type-options", "strict-transport-security",
            "content-security-policy", "x-xss-protection",
            "access-control-allow-origin", "x-aspnet-version",
            "x-generator"
        ]
        header_data = {}
        for key, value in r.headers.items():
            header_data[key] = value
            if key.lower() in interesting_headers:
                print(f"  {YELLOW}{key}:{RESET} {value}")
            else:
                print(f"  {DIM}{key}:{RESET} {value}")

        missing = []
        security_headers = [
            "X-Frame-Options", "X-Content-Type-Options",
            "Strict-Transport-Security", "Content-Security-Policy"
        ]
        for h in security_headers:
            if not any(k.lower() == h.lower() for k in r.headers):
                missing.append(h)
        if missing:
            print(f"\n  {RED}Missing security headers:{RESET}")
            for h in missing:
                print(f"    {RED}> {h}{RESET}")

        return header_data
    except requests.RequestException as e:
        print(f"  {RED}Error: {e}{RESET}")
        return {}


# === FEATURE: --sitemap ===
def fetch_sitemap(sitemap_urls):
    if not sitemap_urls:
        print(f"\n  {DIM}No sitemap referenced in robots.txt.{RESET}")
        return []
    all_entries = []
    for url in sitemap_urls:
        print(f"\n  {BOLD}Sitemap:{RESET} {url}")
        try:
            r = requests.get(url, timeout=10, headers={
                "User-Agent": "RoboSnap/1.0"
            })
            if r.status_code == 200:
                content = r.text
                count = content.count("<loc>")
                print(f"  {GREEN}{r.status_code} OK{RESET} - {count} entries found")
                entries = []
                for line in content.splitlines():
                    if "<loc>" in line:
                        loc = line.split("<loc>")[1].split("</loc>")[0].strip()
                        entries.append(loc)
                for entry in entries[:10]:
                    print(f"    {DIM}{entry}{RESET}")
                if len(entries) > 10:
                    print(f"    {DIM}... and {len(entries) - 10} more{RESET}")
                all_entries.extend(entries)
            else:
                print(f"  {RED}{r.status_code}{RESET}")
        except requests.RequestException as e:
            print(f"  {RED}Error: {e}{RESET}")
    return all_entries


# === FEATURE: --export ===
def export_results(data, fmt, domain):
    filename = f"robosnap_{domain}.{fmt}"
    if fmt == "json":
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    elif fmt == "csv":
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["type", "value", "extra"])
            for path in data.get("disallow_paths", []):
                writer.writerow(["disallow", path, ""])
            for path in data.get("allow_paths", []):
                writer.writerow(["allow", path, ""])
            for s in data.get("sitemaps", []):
                writer.writerow(["sitemap", s, ""])
            for p in data.get("probe_results", []):
                writer.writerow(["probe", p["path"], p["status"]])
    print(f"\n  {GREEN}Exported: {filename}{RESET}")


def fetch_robots(url, args):
    parsed, robots_url = normalize_url(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc.replace(":", "_")

    print(f"\n  {DIM}{robots_url}{RESET}\n")
    loading_bar()

    export_data = {
        "url": robots_url,
        "domain": parsed.netloc,
        "disallow_paths": [],
        "allow_paths": [],
        "sitemaps": [],
        "interesting_paths": [],
        "probe_results": [],
        "headers": {}
    }

    try:
        response = requests.get(robots_url, timeout=10, headers={
            "User-Agent": "RoboSnap/1.0"
        })

        if response.status_code == 200:
            content = response.text.strip()
            if content:
                print(f"\n  {GREEN}200 OK{RESET}\n")
                print(content)

                disallow_paths = get_disallow_paths(content)
                allow_paths = [
                    l.split(":", 1)[1].strip()
                    for l in content.splitlines()
                    if l.strip().lower().startswith("allow:")
                    and l.split(":", 1)[1].strip()
                ]
                sitemap_urls = get_sitemap_urls(content)

                export_data["disallow_paths"] = disallow_paths
                export_data["allow_paths"] = allow_paths
                export_data["sitemaps"] = sitemap_urls

                if args.filter:
                    interesting = filter_interesting(disallow_paths)
                    export_data["interesting_paths"] = interesting
                    if interesting:
                        print(f"\n  {BOLD}Interesting paths{RESET}\n")
                        for p in interesting:
                            print(f"    {RED}> {p}{RESET}")
                    else:
                        print(f"\n  {DIM}No interesting paths found.{RESET}")

                if args.probe:
                    export_data["probe_results"] = probe_paths(base_url, disallow_paths)

                if args.sitemap:
                    fetch_sitemap(sitemap_urls)

            else:
                print(f"\n  {YELLOW}Empty - no rules found.{RESET}")

        elif response.status_code == 404:
            print(f"\n  {RED}404 - No robots.txt found.{RESET}")
        else:
            print(f"\n  {YELLOW}{response.status_code}{RESET}")

    except requests.ConnectionError:
        print(f"\n  {RED}Connection failed.{RESET}")
    except requests.Timeout:
        print(f"\n  {RED}Timeout.{RESET}")
    except requests.RequestException as e:
        print(f"\n  {RED}Error: {e}{RESET}")

    if args.headers:
        export_data["headers"] = show_headers(base_url)

    if args.export:
        export_results(export_data, args.export, domain)

    print()


def interactive_mode(args):
    print(f"\n  {DIM}Enter a URL or 'exit' to quit{RESET}")
    flags = get_active_flags(args)
    print(f"  {DIM}Active flags: {', '.join(flags) or 'none'}{RESET}")
    while True:
        try:
            url = input(f"\n  {CYAN}>{RESET} ").strip()
            if url.lower() in ("exit", "quit", "q"):
                break
            if url:
                fetch_robots(url, args)
        except (KeyboardInterrupt, EOFError):
            print()
            break


def get_active_flags(args):
    flags = []
    if args.filter:
        flags.append("--filter")
    if args.probe:
        flags.append("--probe")
    if args.headers:
        flags.append("--headers")
    if args.sitemap:
        flags.append("--sitemap")
    if args.export:
        flags.append(f"--export {args.export}")
    if args.bulk:
        flags.append(f"--bulk {args.bulk}")
    return flags


def main():
    parser = argparse.ArgumentParser(
        description="RoboSnap - robots.txt Checker",
        add_help=False
    )
    parser.add_argument("url", nargs="?", default=None)
    parser.add_argument("--filter", action="store_true",
                        help="Highlight interesting paths")
    parser.add_argument("--probe", action="store_true",
                        help="Check status codes of disallow paths")
    parser.add_argument("--headers", action="store_true",
                        help="Show HTTP response headers")
    parser.add_argument("--sitemap", action="store_true",
                        help="Fetch referenced sitemaps")
    parser.add_argument("--export", choices=["json", "csv"], default=None,
                        help="Export results (json or csv)")
    parser.add_argument("--bulk", default=None,
                        help="File with URLs (one per line)")
    parser.add_argument("-h", "--help", action="store_true")

    args = parser.parse_args()

    print(BANNER)

    if args.help:
        print(__doc__)
        return

    if args.bulk:
        if not os.path.isfile(args.bulk):
            print(f"  {RED}File not found: {args.bulk}{RESET}")
            return
        with open(args.bulk) as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"  {BOLD}{len(urls)} domains loaded{RESET}\n")
        for url in urls:
            fetch_robots(url, args)
        return

    if args.url:
        fetch_robots(args.url, args)
    else:
        interactive_mode(args)


if __name__ == "__main__":
    main()
