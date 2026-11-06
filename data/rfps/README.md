# Public Institutional RFP Dataset — source collection

This dataset supplements the existing **investment policy / portfolio compliance** prototype.
It is **data for a future RFP intake experiment, not implemented application logic**. Existing UI and compliance rules are unchanged.

## Contents

- `sources.csv`: 5 verified public **official** PDF links: two issued pension manager RFPs, a sample RFP, a sample investment-manager agreement (IMA), and a public IPS.
- `criteria_examples.csv`: selected **human-curated, paraphrased** clauses from the documents, with PDF page references and classification. This is **not** a comprehensive set of extracted rules or an LLM benchmark yet.
- `fetch_rfps.py`: locally download the PDFs into `downloaded/` with file validation and SHA-256 provenance. Downloaded PDFs are not bundled because the working environment could not reach the official servers. No credentials or external LLM service are required.

## Download commands

Run from the repository root:

```bash
python data/rfps/fetch_rfps.py --all
# or only the two actual RFPs:
python data/rfps/fetch_rfps.py --only surs_2026_public_equity massprim_2026_global_core
```

The script accesses the public PDF URLs only when invoked. If institutional websites block automated requests, use the `pdf_url` in `sources.csv` manually and save under the exact `filename` in `downloaded/`.

## Semantics to preserve

1. **Hard manager qualifications**: gate whether an applicant may proceed in a specific procurement. They are not weighted away by a good portfolio.
2. **Preferred selection criteria**: may inform evaluation; scores and weights must be disclosed or marked *illustrative*, never attributed to the pension fund without evidence.
3. **Portfolio characteristics requested in a questionnaire**: sometimes a request to **describe** a strategy's exposures, not a mandate limit.
4. **Binding investment restrictions**: become applicable through final authorized investment guidelines, contracts, IPS, and amendments; a public procurement document is not automatically an account-level approved rule.
5. **True compliance breach** vs **relative fit**: never relabel a hard violation as compliant because its distance from a limit is small. Missing or uncertain information becomes `NEEDS_REVIEW`.

## Suggested prototype separation

**Pre-award:** RFP intake -> clause type classification -> manager eligibility gate -> preference-fit analysis -> human assessment.

**Post-award:** approved mandate intake -> approved policy versions -> current portfolio deterministic checks -> SEC filing event review -> human authorization and audit.

Investor/pension fund controls the procurement and final restrictions. Asset manager uses the tool to triage RFPs, develop eligible proposals, and monitor managed accounts.

All examples here are source-derived **paraphrases** with page locations. Verify against the live PDFs before using them as operational rules or evaluation ground truth.
