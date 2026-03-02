# RoboSnap

Fast robots.txt checker for the command line.

## Installation

```
pip install requests
```

## Usage

```
python3 robosnap.py <url>
python3 robosnap.py                          # Interactive mode
```

## Optional Flags

| Flag | Description |
|------|-------------|
| `--filter` | Highlight interesting paths (admin, backup, login etc.) |
| `--probe` | Check status codes of disallow paths (200, 403, 301...) |
| `--headers` | Show HTTP response headers + report missing security headers |
| `--sitemap` | Fetch referenced sitemap.xml and list entries |
| `--export json` | Export results as JSON |
| `--export csv` | Export results as CSV |
| `--bulk domains.txt` | Scan multiple domains from file |

Flags can be combined:

```
python3 robosnap.py example.com --filter --probe --headers --export json
```

## Bulk Scan

Create a text file with one domain per line:

```
example.com
github.com
stackoverflow.com
```

```
python3 robosnap.py --bulk domains.txt --filter --export csv
```

## Disclaimer

This tool only reads publicly accessible files. Use responsibly.
