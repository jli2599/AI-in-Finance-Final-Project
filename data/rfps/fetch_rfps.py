"""Download public pension RFP/IPS PDFs into data/rfps/downloaded/.

Usage: python data/rfps/fetch_rfps.py --all
       python data/rfps/fetch_rfps.py --only surs_2026_public_equity
No account details are sent. Uses only the official URL manifest.
"""
import argparse
import csv
import hashlib
import pathlib
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
MAX_BYTES = 40 * 1024 * 1024

def get_sources():
    with (HERE / "sources.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def fetch(record):
    output = HERE / 'downloaded'
    output.mkdir(exist_ok=True)
    filename = pathlib.Path(record['filename']).name
    destination = output / filename
    req = urllib.request.Request(record['pdf_url'], headers={
        'User-Agent': 'Mozilla/5.0 (compatible; ResearchStudyPublicRFPs/1.0)',
        'Accept': 'application/pdf',
    })
    with urllib.request.urlopen(req, timeout=40) as response:
        size = 0
        temporary = destination.with_suffix('.pdf.tmp')
        try:
            with temporary.open('wb') as handle:
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('PDF exceeds 40 MB maximum')
                    handle.write(chunk)
            with temporary.open('rb') as handle:
                if handle.read(5) != b'%PDF-':
                    raise ValueError('Source was not a PDF; use official landing page')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination, hashlib.sha256(destination.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument('--all', action='store_true')
    choices.add_argument('--only', nargs='+', metavar='ID')
    args = parser.parse_args()
    sources = get_sources()
    available = {r['source_id'] for r in sources}
    if args.only:
        unknown = set(args.only) - available
        if unknown:
            parser.error(f'Unknown source IDs: {sorted(unknown)}')
        sources = [r for r in sources if r['source_id'] in args.only]
    rows = []
    for record in sources:
        try:
            path, digest = fetch(record)
            print(f"OK {record['source_id']}: {path.name}")
            rows.append([record['source_id'], path.name, digest, record['pdf_url']])
        except Exception as exc:
            print(f"FAILED {record['source_id']}: {exc}")
        time.sleep(1)
    if rows:
        output = HERE / 'downloaded' / 'checksums.csv'
        previous = {}
        if output.exists():
            with output.open(newline='', encoding='utf-8') as h:
                previous = {r['source_id']: r for r in csv.DictReader(h)}
        for row in rows:
            previous[row[0]] = dict(zip(['source_id', 'filename', 'sha256', 'pdf_url'], row))
        with output.open('w', newline='', encoding='utf-8') as h:
            w = csv.DictWriter(h, fieldnames=['source_id','filename','sha256','pdf_url'])
            w.writeheader()
            w.writerows(previous.values())

if __name__ == '__main__':
    main()
