# Investment Compliance & SEC Intelligence — Local MVP

Built as an extension of the supplied `AI-in-Finance-Final-Project-main` repository. The existing `main.py`, `ips_monitor/`, data generator and original tests are retained.

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate             # macOS/Linux
# .venv\\Scripts\\activate          # Windows
pip install -r requirements.txt
streamlit run app.py
```

The first start copies `data/app_seed.json` into `data/app_state.json`. This holds demo accounts, approvals, draft documents, alerts and the audit trail. To reset the app, stop it and delete **only** `data/app_state.json`.

Original CLI still works:

```bash
python main.py demo
python -m unittest discover -s tests -v
```

## Four UI tabs

1. **Portfolios:** Switch among three fictional accounts, inspect positions, sector exposure, cash, policy results and data-quality exceptions.
2. **Policies & Documents:** Upload `.txt`, `.html`, `.pdf`, or `.docx`; use a **regex baseline** to extract candidate restrictions with supporting clauses; review/edit JSON draft; activate new version only after a simulated reviewer approval.
3. **SEC Alerts & Screening:** Historical case-study links (GE, 3M and Kellanova), manual SEC polling, keyword event screening, optional **local-only** Ollama extraction, and a financial screening demo using **explicitly fabricated** metrics. No filing automatically changes eligibility.
4. **Review & Audit:** Record preliminary alert disposition and see audit entries. Policy approvals are separately recorded in the Policies tab.

## Run a local LLM (optional)

Install [Ollama](https://ollama.com/) and use:

```bash
ollama pull qwen3:4b
ollama serve
```

Select the local-model checkbox before refreshing SEC documents. The prototype only allows calls to `127.0.0.1:11434` or `localhost:11434`. Only **public SEC filing text** is passed to the model; client portfolios and client policies are never included in that prompt. LLM event summaries are provisional; evidence quotes are checked against source text and all claims require human review. **Local LLM operation has not been benchmarked on the current dataset**.

## SEC ingestion

SEC filings are obtained through the official `data.sec.gov/submissions/CIK...json` endpoint and the official SEC archive. Provide a genuine contact email to identify your application per SEC fair-access guidance. SEC may refuse access and requires responsible throttling; the app only fetches a small number of filings on demand. For scheduled monitoring, use the one-shot script, for example:

```bash
python monitor_sec.py --cik 40545 --name GE --contact YOUR_EMAIL --limit 3
```

Set a suitable external scheduler if recurring runs are required. The script deduplicates accession numbers in `app_state.json`. The source URLs in `events_seed.json` are historical case-study references, **not files automatically extracted or evaluated by this MVP**.

## What is real vs simulated

- **Real source references:** Public SEC filing URLs for historical corporate actions. Additional public text can be fetched with an internet connection and SEC access.
- **Synthetic:** All client portfolios, IPS thresholds, seeded approvals, account names, and candidate financial metrics.
- **Provisional:** All corporate event/eligibility alerts; none establish real investment compliance or permission to trade.
- **Human control:** New policy versions require explicit demo review; event review never modifies a rule or issuer classification automatically.

## Guardrails and known limitations

- No real authentication, authorization, encryption at rest, concurrent write protection, or tamper-evident logs. **Do not load real client or restricted information.** Demo reviewer name is self-entered.
- Document text/drafts are stored in a local JSON file in plaintext. Keep `data/app_state.json` out of version control.
- SEC polling is on-demand/CLI, not a persistent production scheduler. Company-to-holding matching is a future integration step. Screening metrics are fabricated demonstration values, not real SEC XBRL analytics.
- The rule engine is designed for long-only USD equities + cash. It rejects invalid or incomplete inputs through `DATA_ISSUE`. The fifth business-activity exclusion type requires a **verified** activity classification, and should not be applied based solely on LLM speculation.
- PDFs with scanned images require an OCR process not included here.
- The regex extractor is a baseline, not a comprehensive policy interpreter. It supports basic patterns and may omit complex clauses; manual review is mandatory. The model is optional and currently used only for filing extraction.
- A production implementation requires actual company/issuer mapping, secure roles and segregation of duties, policy authority validation, privacy review, monitoring robustness, and independent financial data verification.

## Architecture

`Portfolio + Approved IPS -> deterministic compliance engine -> account statuses`

`SEC filing -> HTML extraction -> keyword / optional local LLM event proposal -> human investigation -> proposed issuer/rule change -> independent approval -> rerun deterministic checks`

`Uploaded IPS -> extract draft rules -> edit + review -> versioned activation -> rerun deterministic checks`

## Testing

Run `python -m unittest discover -s tests -v`. Additional tests cover missing data, business exclusions, issuer matching, restrictions validation and safeguards against nonlocal LLM endpoints. This is developer-side unit testing; SEC live access, real-model precision/recall and actual multi-user authentication have **not** been validated.

## November 5 UI and local-inbox update

### Horizontal chart category labels

The Portfolio tab now uses an Altair sector bar chart with **horizontal category labels** (`labelAngle=0`). The long "Information Technology" label is shown as "Info Technology" to prevent overlap; hover the bar to see the full name. Altair is included in `requirements.txt`.

### More realistic guideline examples

The seeded fictional mandates include two additional structured rule types:

- `max_top_n_issuers`: the total weight of the largest **N distinct issuers** must remain below a combined threshold (e.g., top five ≤ 25% NAV). A company held via multiple securities is aggregated before ranking.
- `sector_specific_issuer_cap`: a default per-issuer weight cap plus tighter overrides for a specific sector (e.g., 8% normally but 4.5% for technology issuers).

Both use deterministic calculations, with measured values and source clauses displayed beneath the Rule Results table. These are realistic **illustrative contract terms**, not universal legal restrictions. They are included in the seeded clients, and can also be introduced through a manually edited draft policy. The **regex** extractor does not reliably parse conditional or aggregate clauses from unstructured prose; those require explicit human review and manual structuring in this version.

### Offline SEC Filings folder

An `SEC Filings/` directory now exists in the root of the project. Copy `.txt`, `.html`, `.htm`, searchable `.pdf`, or `.docx` filings into it. Open **SEC Alerts & Screening → Scan SEC Filings folder**. This action **does not contact the internet**. It extracts text, identifies a watched issuer, looks for possible event terms, and creates provisional alerts. Repeated runs skip unchanged files by content SHA-256; check **Rescan previously processed files** to re-evaluate when a watchlist changes.

The optional `SEC Filings/manifest.csv` provides metadata for matching issuers. Its columns are:

`filename,issuer_name,ticker,cik,form,filing_date,source_url,source_type`

- `filename` must match the local file's name (or relative path if placed in a subfolder).
- Match on the **CIK** where possible. Bare short ticker text is not enough to identify a document without metadata.
- `source_url` is an optional official SEC link for reference; a manifest is not proof of authenticity.
- `source_type` can be `synthetic` for educational mock filings. All outputs remain **potential review signals**, not confirmed events.
- The included `DEMO_GE_EVENT.txt` is **synthetic training text**, not an official filing. Delete it or keep it as a smoke-test fixture.
- Ambiguous or unmatched documents are reported in the scan-results table instead of guessed into an issuer.
- No image OCR is provided; a scanned PDF without selectable text reports an error.

### Watchlist editor

Add companies in **SEC Alerts & Screening → Companies to monitor** using a company name, optional ticker, optional SEC CIK, and full-name aliases. Remove watchlist companies through the dedicated expander. Changes persist to `data/app_state.json` and generate demo audit events. The offline inbox uses this watchlist. Live SEC polling (optional) uses companies that have a CIK.

### What happens if you do **not** install Ollama or Qwen3?

The app still runs. **No LLM is required for the default mode.**

| Workflow | No Ollama installed | Ollama available, optional model enabled |
|---|---|---|
| Portfolio compliance | Deterministic Python | Same deterministic Python |
| IPS document extraction | Regex baseline with human review | Still regex baseline (not LLM in this version) |
| Local SEC folder scan | Keyword baseline | Keyword baseline + local event extraction proposals |
| Live SEC retrieval | Keyword baseline (internet required for SEC only) | Keyword baseline + local event extraction proposals |
| Compliance/eligibility approval | Simulated human review | Same simulated human review |

In the sidebar, the app checks `http://127.0.0.1:11434/api/tags` to indicate whether Ollama is running. **Nothing is sent to OpenAI or any remote LLM provider.** The Ollama integration only accepts loopback `127.0.0.1` or `localhost` and passes *document text*, not portfolio allocations. If the model is requested but cannot run, the scan displays a model-error message and retains visibly labeled keyword findings. It does not claim an LLM inference occurred.

To enable optional local extraction:

```bash
# separately install Ollama from https://ollama.com/
ollama pull qwen3:4b
# start Ollama service if it is not already running
ollama serve
streamlit run app.py
```

**Important remaining limitations:** This is a student demo, not a secure multi-tenant financial product. It has no authentication or actual role controls. The company matcher, keyword scanner, and SEC event classifier are not validated for real-world precision/recall. The local alert trigger does not yet automatically reclassify holdings or confirm company eligibility. The evidence and policy approval must be manually checked. Files copied into the inbox should be public or synthetic; never place confidential investor or client documents in the demo.
