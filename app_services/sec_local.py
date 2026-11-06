"""Offline, explicitly on-demand SEC-file inbox for the classroom demonstration.

Only reads local files; it never polls SEC or uploads to an external service.
Filing text is untrusted. Matching a watchlist company is NOT a determination
that a corporate event has happened or that eligibility has changed.
"""
import csv
import hashlib
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from app_services.policies import document_text
from app_services.sec import screen_document, local_ollama_extract

SUPPORTED_EXTENSIONS = {'.txt', '.html', '.htm', '.pdf', '.docx'}
MAX_FILE_BYTES = 20 * 1024 * 1024
INBOX = Path(__file__).resolve().parents[1] / 'SEC Filings'


def normalize_cik(cik):
    raw = str(cik or '').strip()
    return str(int(raw)).zfill(10) if raw.isdigit() else ''


def clean_sec_url(url):
    """Return a SEC-only HTTPS link or nothing, to prevent arbitrary local-source links."""
    try:
        parsed = urlparse(str(url or '').strip())
        if parsed.scheme == 'https' and parsed.hostname in ('www.sec.gov', 'sec.gov'):
            return parsed.geturl()
    except ValueError:
        pass
    return ''


def load_manifest(root=INBOX):
    p = Path(root) / 'manifest.csv'
    if not p.exists():
        return {}
    with p.open(newline='', encoding='utf-8-sig') as f:
        return {r['filename'].strip(): r for r in csv.DictReader(f) if r.get('filename','').strip()}


def match_issuer(text, relative_name, watchlist, manifest_row=None):
    """Prefer explicit local manifest CIK, then full name/aliases in filing text.

    Bare tickers such as 'GE' are never used as free-text matches, since they
    easily create false positives. Ambiguous matches require human metadata review.
    """
    row = manifest_row or {}
    target_cik = normalize_cik(row.get('cik'))
    issuer_name = str(row.get('issuer_name') or '').strip().casefold()
    target_ticker = str(row.get('ticker') or '').strip().casefold()
    if target_cik or issuer_name or target_ticker:
        matched = []
        for issuer in watchlist:
            aliases = [issuer.get('name', '')] + issuer.get('aliases', [])
            if ((target_cik and target_cik == normalize_cik(issuer.get('cik'))) or
                (issuer_name and any(issuer_name == str(a).casefold() for a in aliases if a)) or
                (target_ticker and target_ticker == str(issuer.get('ticker','')).casefold())):
                matched.append(issuer)
        if len(matched) == 1:
            return matched[0], 'MATCHED_BY_MANIFEST'
        return None, 'AMBIGUOUS_MANIFEST' if matched else 'UNMATCHED_MANIFEST'
    lowered = text.casefold()
    matched = []
    for issuer in watchlist:
        full_names = [issuer.get('name', '')] + issuer.get('aliases', [])
        # A short name or ticker can be incidental. Require reasonable specificity.
        if any(len(str(n).strip()) >= 6 and re.search(r'(?<!\w)' + re.escape(str(n).casefold()) + r'(?!\w)', lowered)
               for n in full_names if n):
            matched.append(issuer)
    if len(matched) == 1:
        return matched[0], 'MATCHED_BY_DOCUMENT'
    if len(matched) > 1:
        return None, 'AMBIGUOUS_DOCUMENT'
    return None, 'UNMATCHED_DOCUMENT'


def scan_local_filings(state, folder=INBOX, use_llm=False, model='qwen3:4b', force=False):
    """Scan folder once, update in-memory state, return per-file run results.

    Caller is responsible for persisting state and adding an audit event.
    LLM failure falls back visibly to keyword search, never invisibly.
    """
    root = Path(folder).resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(root)
    seen = state.setdefault('processed_local_documents', {})
    alerts = state.setdefault('alerts', [])
    watchlist = state.get('watchlist', [])
    logs = []
    for path in sorted(root.rglob('*')):
        if (not path.is_file() or path.is_symlink() or path.name.lower() == 'readme.txt' or
                path.suffix.lower() not in SUPPORTED_EXTENSIONS):
            continue
        # Don't follow filesystem links or process something outside the inbox.
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        record = {'file': relative, 'company': '', 'status': '', 'event_types': '', 'method': 'keyword'}
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('file exceeds 20 MB size limit')
            contents = path.read_bytes()
            fingerprint = hashlib.sha256(contents).hexdigest()
            cache_key = f'{relative}:{fingerprint}'
            if not force and cache_key in seen:
                record['status'] = 'SKIPPED_ALREADY_SCANNED'
                logs.append(record)
                continue
            text = document_text(relative, contents)
            if not text.strip():
                raise ValueError('no selectable text (scanned image PDFs need OCR)')
            row = manifest.get(relative, {})
            issuer, match_status = match_issuer(text, relative, watchlist, row)
            record['status'] = match_status
            if not issuer:
                seen[cache_key] = {'match': match_status, 'file': relative}
                logs.append(record)
                continue
            record['company'] = issuer['name']
            entry = {'url': clean_sec_url(row.get('source_url')) or f'local-file:{relative}',
                     'form': row.get('form') or 'UNKNOWN',
                     'filing_date': row.get('filing_date') or '',
                     'cik': issuer.get('cik',''), 'accession': f'local-{fingerprint[:16]}'}
            baseline = screen_document(text, entry)
            events = baseline['events']
            llm_error = ''
            llm_verified = []
            if use_llm:
                record['method'] = f'keyword + local Ollama ({model})'
                try:
                    generated = local_ollama_extract(text, entry, model=model)
                    llm_verified = [e for e in generated.get('events', []) if e.get('evidence_verified')]
                except Exception as exc:
                    llm_error = str(exc)[:180]
                    record['method'] += ' [UNAVAILABLE: keyword fallback]'
            all_types = sorted({str(e.get('type','unknown')) for e in events + llm_verified})
            record['event_types'] = ', '.join(all_types)
            record['status'] = 'POSSIBLE_EVENT_REVIEW' if all_types else 'NO_EVENT_TRIGGER'
            if llm_error:
                record['llm_error'] = llm_error
            if all_types:
                alert_id = f'local_{fingerprint[:20]}'
                alert = {'id': alert_id, 'company': issuer['name'], 'cik': issuer.get('cik',''),
                         'headline': f'Possible {", ".join(all_types)} in {relative}',
                         'source_kind': 'local_file', 'source_file': relative,
                         'source_url': clean_sec_url(row.get('source_url')),
                         'filing_date': entry['filing_date'], 'form': entry['form'],
                         'review_status': 'PENDING', 'method': record['method'],
                         'evidence_note': 'Local-file event indicator. Human must verify the issuer, filing, event, and policy impact.',
                         'evidence': events[:5] + llm_verified[:5],
                         'synthetic_source': str(row.get('source_type','')).lower() == 'synthetic'}
                for idx, previous in enumerate(alerts):
                    if previous.get('id') == alert_id:
                        alerts[idx] = alert
                        break
                else:
                    alerts.append(alert)
            seen[cache_key] = {'match': match_status, 'file': relative, 'company': issuer['name'],
                               'events': all_types}
        except Exception as exc:
            record['status'] = 'ERROR'
            record['error'] = str(exc)[:200]
        logs.append(record)
    state['local_checks'] = logs[-200:]
    return logs
