"""Investment Compliance & SEC Intelligence — educational, local Streamlit MVP."""
import json
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st

from app_services.store import DATA, load_state, save_state, append_event, read_json
from app_services.policies import document_text, candidates, validate_rule
from app_services.compliance import evaluate
from app_services.sec import recent_filings, download_filing, screen_document, local_ollama_extract
from app_services.sec_local import INBOX, scan_local_filings, normalize_cik

st.set_page_config(page_title='Investment Compliance Console', page_icon='📊', layout='wide')
st.title('Investment Compliance & SEC Intelligence')
st.caption('Educational local prototype · Fictional accounts and mandates · No autonomous trading or policy changes')

state = load_state()
state.setdefault('watchlist', read_json(DATA / 'app_seed.json', {}).get('watchlist', []))
state.setdefault('processed_local_documents', {})
state.setdefault('local_checks', [])
clients = {c['name']: c for c in state['clients']}

@st.cache_data(ttl=15)
def ollama_status():
    try:
        response = requests.get('http://127.0.0.1:11434/api/tags', timeout=0.7)
        response.raise_for_status()
        return [m.get('name','') for m in response.json().get('models', [])]
    except Exception:
        return None

with st.sidebar:
    st.header('Demo session')
    selected_name = st.selectbox('Client / account', list(clients))
    client = clients[selected_name]
    actor = st.text_input('Reviewer display name', 'Demo Compliance Analyst')
    st.caption('No login/role enforcement. Do not upload confidential records.')
    st.markdown('**Document-analysis mode**')
    model = st.text_input('Optional local Ollama model', 'qwen3:4b')
    available = ollama_status()
    if available is None:
        st.warning('Ollama not running. Keyword screening still works without an LLM.')
    elif any(model == m or model.split(':')[0] == m.split(':')[0] for m in available):
        st.success(f'Local Ollama available: {model}')
    else:
        st.info('Ollama running, but selected model not detected. Pull the model before enabling LLM extraction.')
    st.caption('Policy upload always uses a regex baseline in this MVP. SEC extraction optionally calls localhost only; it never sends portfolio allocations to an API.')

policy = state['policies'][client['policy_id']]
snapshot = read_json(DATA / 'portfolios' / client['portfolio'])
report = evaluate(snapshot, policy['rules'])


def pretty(value):
    return json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (list,dict)) else str(value)


def policy_draft(rules, source_name, source_text=''):
    item = {'id': f'D{len(state["drafts"])+1}', 'client_id': client['id'],
            'source_name': source_name, 'source_text': source_text,
            'rules': rules, 'created_by': actor, 'status': 'DRAFT'}
    state['drafts'].append(item)
    append_event(state, actor, 'draft_created', {'client': client['id'], 'draft': item['id']})
    save_state(state)


tabs = st.tabs(['Portfolios', 'Policies & Documents', 'SEC Alerts & Screening', 'Review & Audit'])

with tabs[0]:
    st.subheader(f'{selected_name} — portfolio')
    m1, m2, m3, m4 = st.columns(4)
    m1.metric('Illustrative NAV', f'${report["nav"]:,.0f}')
    m2.metric('Cash weight', f'{report["cash_weight"]:.1%}' if report['cash_weight'] is not None else 'Unknown')
    m3.metric('Approved policy version', str(policy['version']))
    m4.metric('Overall check', report['overall'])

    positions = []
    for p in snapshot['positions']:
        mv = (p.get('quantity') or 0) * (p.get('price') or 0)
        positions.append({'Ticker':p.get('ticker'), 'Issuer':p.get('issuer'), 'Sector':p.get('sector'),
                          'Value (USD)':mv, 'Weight':mv / report['nav'] if report['nav'] else 0,
                          'Price date':p.get('price_date')})
    if positions:
        st.dataframe(pd.DataFrame(positions).style.format({'Value (USD)':'${:,.0f}', 'Weight':'{:.2%}'}), use_container_width=True)
        st.markdown('**Sector allocation**')
        sector_data = pd.DataFrame([{'Sector': k,
            'Display': 'Info Technology' if k == 'Information Technology' else k,
            'Weight': v} for k,v in report['sector_weights'].items()])
        # Altair allows explicit horizontal tick labels; Streamlit's default st.bar_chart rotated them.
        chart = alt.Chart(sector_data).mark_bar(size=43).encode(
            x=alt.X('Display:N', sort=None, title='Sector',
                    axis=alt.Axis(labelAngle=0, labelLimit=175, labelOverlap=False, labelFontSize=12)),
            y=alt.Y('Weight:Q', title='Portfolio weight', axis=alt.Axis(format='%')),
            tooltip=[alt.Tooltip('Sector:N'), alt.Tooltip('Weight:Q', format='.2%')]
        ).properties(height=265)
        st.altair_chart(chart, use_container_width=True)
        st.caption('Sector names are horizontal; “Info Technology” is a display abbreviation. Hover for the complete name.')

    st.markdown('**Rule results — with underlying calculations**')
    st.dataframe(pd.DataFrame([{
        'Rule':r['rule_id'], 'Type':r['type'], 'Status':r['status'],
        'Measured result':r.get('observed',''),
        'Offenders / issues':pretty(r['offenders'] if r['offenders'] else r['data_issues']) if (r['offenders'] or r['data_issues']) else 'None'
    } for r in report['results']]), hide_index=True, use_container_width=True)
    for result in report['results']:
        if result['type'] in {'max_top_n_issuers', 'sector_specific_issuer_cap'} or result['status'] != 'PASS':
            with st.expander(f'{result["rule_id"]} — {result["type"]} — {result["status"]}'):
                st.write(result.get('explanation',''))
                st.write('Observed:', result.get('observed',''))
                st.write('Source clause:', result.get('source',''))
                if result['offenders']:
                    st.json(result['offenders'])
                if result['data_issues']:
                    st.warning('; '.join(result['data_issues']))

    with st.expander('Realistic complex-rule examples (fictional mandates)'):
        st.markdown('**Top-N aggregate issuer rule:** “The five largest issuers together cannot exceed 25% of NAV.” Securities of the same issuer are combined first; this can fail even if each issuer passes its individual cap.')
        st.markdown('**Sector-specific issuer exception:** “The default issuer limit is 8%, but technology issuers have a stricter 4.5% limit.” Each position must be checked against the correct sector limit.')
        st.caption('These examples are supported by the deterministic engine and seeded into different demo client policies. They are illustrative client instructions, not universally applicable regulations. The regex document extractor does not automatically understand all such clauses; an analyst can add them as structured draft rules.')
    st.info('Missing/stale financial data produce DATA_ISSUE; even a suspected restriction breach cannot be treated as a confirmed automated conclusion without valid inputs.')

with tabs[1]:
    st.subheader('Policy document upload & controlled revisions')
    doc = st.file_uploader('New IPS or guideline (TXT, HTML, PDF, DOCX)', type=['txt','html','htm','pdf','docx'])
    if doc is not None and st.button('Extract draft restrictions'):
        try:
            doc_text = document_text(doc.name, doc.getvalue())
            extracted, unsupported = candidates(doc_text, doc.name)
            if unsupported:
                st.error('Some source citations could not be verified. Draft was not saved.')
            elif not extracted:
                st.warning('No supported baseline rules found. Try a plain-language draft or copy the current policy and edit it manually.')
            else:
                policy_draft(extracted, doc.name, doc_text)
                st.success(f'{len(extracted)} candidate rules extracted with regex. Review before approval.')
        except Exception as exc:
            st.error(f'Unable to read document: {exc}')
    st.markdown('**Active approved policy**')
    st.dataframe(pd.DataFrame([{'ID':r['id'], 'Type':r['type'], 'Value':pretty(r['value']),
                               'Evidence / rationale':r.get('clause_text','')} for r in policy['rules']]),
                 hide_index=True, use_container_width=True)
    if st.button('Create change proposal from active policy'):
        policy_draft(json.loads(json.dumps(policy['rules'])), f'Manual amendment to v{policy["version"]}')
        st.success('Draft created. Active policy is unchanged.')
    drafts = [d for d in state['drafts'] if d['client_id'] == client['id'] and d['status'] == 'DRAFT']
    if drafts:
        chosen = st.selectbox('Draft awaiting review', drafts,
                              format_func=lambda d:f'{d["id"]} — {d["source_name"]}')
        st.caption('Edit, add or remove draft rules as JSON. An active rule can only be changed by approving a new policy version.')
        revised = st.text_area('Draft rules JSON', json.dumps(chosen['rules'], indent=2), height=280)
        approved = st.checkbox('I verified these rules against the authorized mandate and approve a new policy version (demo only)')
        left, right = st.columns(2)
        def parse_rules():
            rules = json.loads(revised)
            if not isinstance(rules, list) or not rules:
                raise ValueError('Expected a nonempty list of rules')
            ids = [r.get('id') for r in rules]
            if len(set(ids)) != len(ids):
                raise ValueError('Rule identifiers must be unique')
            for r in rules:
                validate_rule(r)
            return rules
        with left:
            if st.button('Save draft corrections'):
                try:
                    chosen['rules'] = parse_rules()
                    append_event(state, actor, 'draft_edited', {'draft':chosen['id']})
                    save_state(state)
                    st.success('Draft saved. Active policy unchanged.')
                except Exception as exc:
                    st.error(str(exc))
        with right:
            if st.button('Approve new version', disabled=not approved):
                try:
                    rules = parse_rules()
                    policy.update({'version':policy['version']+1, 'rules':rules, 'approved_by':actor,
                                   'approved_at':datetime.now(timezone.utc).isoformat()})
                    chosen['status'] = 'APPROVED'
                    append_event(state, actor, 'policy_version_approved',
                                 {'client':client['id'],'version':policy['version'],'draft':chosen['id']})
                    save_state(state)
                    st.success('New demo policy activated. The compliance results will update on rerun.')
                except Exception as exc:
                    st.error(str(exc))
    else:
        st.caption('No pending drafts. Upload a policy or create a change proposal from the active policy.')

with tabs[2]:
    st.subheader('SEC document screening & analyst watchlist')
    st.caption('A filing or keyword hit creates an investigation task, NOT an automatic eligibility decision.')
    st.markdown('**Companies to monitor**')
    if state['watchlist']:
        st.dataframe(pd.DataFrame([{'Company':w['name'],'Ticker':w.get('ticker',''),
                                    'CIK (for live SEC polling)':w.get('cik',''),
                                    'Full-name aliases':', '.join(w.get('aliases',[]))}
                                   for w in state['watchlist']]), hide_index=True, use_container_width=True)
    with st.form('watchlist_add', clear_on_submit=True):
        c1,c2,c3 = st.columns([3,1,2])
        name = c1.text_input('Company name')
        ticker = c2.text_input('Ticker')
        cik = c3.text_input('SEC CIK (optional for local scans)')
        aliases = st.text_input('Additional full legal names / aliases (comma separated)')
        if st.form_submit_button('Add company to watchlist'):
            if not name.strip():
                st.error('Enter a company name.')
            elif cik.strip() and not normalize_cik(cik):
                st.error('CIK must contain digits only.')
            elif any(w['name'].casefold()==name.strip().casefold() for w in state['watchlist']):
                st.warning('Company already on watchlist.')
            else:
                item = {'id':f'w{len(state["watchlist"])+1}_{datetime.now(timezone.utc).strftime("%H%M%S")}',
                        'name':name.strip(), 'ticker':ticker.strip().upper(),
                        'cik':normalize_cik(cik),
                        'aliases':[x.strip() for x in aliases.split(',') if x.strip()]}
                state['watchlist'].append(item)
                append_event(state, actor, 'watchlist_company_added', {'company':item['name']})
                save_state(state)
                st.success('Added. For reliable local-file matching, reference the issuer in SEC Filings/manifest.csv.')
    if state['watchlist']:
        with st.expander('Remove a company from watchlist'):
            remove_id = st.selectbox('Select company', state['watchlist'],
                                     format_func=lambda w:w['name'])
            if st.button('Remove company from watchlist'):
                state['watchlist'] = [w for w in state['watchlist'] if w['id']!=remove_id['id']]
                append_event(state, actor, 'watchlist_company_removed', {'company':remove_id['name']})
                save_state(state)
                st.success('Removed from future scans. Historical alerts remain in the audit record.')

    st.divider()
    st.markdown('**Scan saved SEC documents (offline demo)**')
    st.write('Drop `.txt`, `.html`, `.pdf`, or `.docx` files into the project folder below, then click Scan. No live SEC wait and no internet required.')
    st.code(str(INBOX), language='text')
    st.caption('Optional manifest.csv maps a filename to company/CIK, filing date and SEC source. Without it, the parser attempts full company-name matches; ambiguous filings require manual identification. Scanned-image PDFs need OCR.')
    present_files = [p.relative_to(INBOX).as_posix() for p in INBOX.rglob('*')
                     if p.is_file() and p.suffix.lower() in {'.txt','.htm','.html','.pdf','.docx'} and p.name.lower()!='readme.txt']
    st.write(f'{len(present_files)} supported document(s) in local inbox: ' + (', '.join(present_files[:8]) or 'none'))
    use_local_llm = st.checkbox('Run optional local Ollama extraction during folder scan', value=False,
                                key='local_llm')
    force = st.checkbox('Rescan previously processed files', value=False)
    if st.button('Scan SEC Filings folder', type='primary'):
        logs = scan_local_filings(state, use_llm=use_local_llm, model=model, force=force)
        append_event(state, actor, 'local_sec_inbox_scan',
                     {'files':len(logs),'alerts':sum(r['status']=='POSSIBLE_EVENT_REVIEW' for r in logs),
                      'llm_requested':use_local_llm})
        save_state(state)
        st.success(f'Scanned {len(logs)} files; {sum(r["status"]=="POSSIBLE_EVENT_REVIEW" for r in logs)} potential event alerts. Examine results below.')
        if use_local_llm and any('llm_error' in r for r in logs):
            st.warning('At least one local LLM call failed; keyword results are retained and clearly labeled.')
    if state.get('local_checks'):
        st.dataframe(pd.DataFrame(state['local_checks']), hide_index=True, use_container_width=True)

    st.divider()
    with st.expander('Optional: retrieve recent live filings from SEC EDGAR'):
        selectable = [w for w in state['watchlist'] if normalize_cik(w.get('cik'))]
        if not selectable:
            st.caption('Add a company with a valid CIK to enable live SEC retrieval.')
        else:
            issuer = st.selectbox('Watched issuer', selectable, format_func=lambda w:w['name'])
            contact = st.text_input('SEC User-Agent contact email', '')
            limit = st.slider('Recent filings to examine', 1, 5, 2)
            use_live_llm = st.checkbox('Use local Ollama for extracted event proposals', value=False, key='live_llm')
            if st.button('Fetch and screen recent SEC filings'):
                try:
                    entries = recent_filings(issuer['cik'], contact, limit=limit)
                    inserted = 0
                    for entry in entries:
                        if entry['accession'] in state.setdefault('processed_accessions', []):
                            continue
                        doc_text = download_filing(entry, contact)
                        extraction = screen_document(doc_text, entry)
                        if use_live_llm:
                            try:
                                extraction['local_llm'] = local_ollama_extract(doc_text, entry, model=model)
                            except Exception as exc:
                                extraction['local_llm_error'] = str(exc)
                        if extraction['events'] or extraction.get('local_llm',{}).get('events'):
                            state['alerts'].append({'id':entry['accession'],'company':issuer['name'],
                                'cik':issuer['cik'],'headline':f'Possible event in {entry["form"]}',
                                'source_kind':'sec_live', 'source_url':entry['url'],
                                'filing_date':entry['filing_date'],'form':entry['form'],
                                'review_status':'PENDING', 'evidence_note':json.dumps(extraction)[:3000]})
                            inserted += 1
                        state['processed_accessions'].append(entry['accession'])
                    append_event(state, actor, 'sec_live_scan',
                                 {'issuer':issuer['name'], 'filings_checked':len(entries), 'alerts':inserted})
                    save_state(state)
                    st.success(f'Checked {len(entries)} filings and queued {inserted} provisional alerts.')
                except Exception as exc:
                    st.error(f'SEC retrieval unavailable: {exc}')

    st.divider()
    st.markdown('**Company event alerts awaiting review**')
    for event in state.get('alerts',[]):
        with st.expander(f'{event.get("company","Unknown")}: {event.get("headline",event.get("form","Filing"))}'):
            st.write('Status:',event.get('review_status','PENDING'))
            st.write('Source:', event.get('source_file', 'SEC live filing'), '· Form:', event.get('form','Unknown'),
                     '· Filing date:', event.get('filing_date','Unknown'))
            st.write(event.get('evidence_note','Review needed.'))
            if event.get('synthetic_source'):
                st.warning('Synthetic training document; not an actual SEC filing.')
            if event.get('source_url'):
                st.markdown(f'[Open public SEC reference]({event["source_url"]})')
            if event.get('evidence'):
                st.json(event['evidence'])
            st.caption('Review source authenticity, event status and portfolio policy before any change.')
    with st.expander('Historical public filing examples (reference links, not scanned)'):
        for event in read_json(DATA/'watchlist'/'events_seed.json', []):
            st.markdown(f'**{event["company"]}** — {event["headline"]}')
            st.markdown(f'[Open SEC reference]({event["source_url"]})')

    st.divider()
    st.markdown('**Candidate financial screening — fabricated demo values**')
    demo_candidates = pd.read_csv(DATA/'watchlist'/'candidates.csv')
    min_cap = st.slider('Minimum market cap (synthetic $bn)',0,200,10)
    min_growth = st.slider('Minimum revenue growth (synthetic %)',-10,30,0)
    min_margin = st.slider('Minimum operating margin (synthetic %)',-10,40,0)
    only_review = st.checkbox('Only companies requiring eligibility review', value=True)
    filtered = demo_candidates[(demo_candidates.market_cap_usd_b >= min_cap) &
                               (demo_candidates.revenue_growth_pct >= min_growth) &
                               (demo_candidates.operating_margin_pct >= min_margin)]
    if only_review:
        filtered = filtered[filtered.review_status == 'NEEDS_ELIGIBILITY_REVIEW']
    st.dataframe(filtered, hide_index=True, use_container_width=True)
    st.warning('These metrics are synthetic. Passing a screen is not a compliance approval or an investment recommendation.')

with tabs[3]:
    st.subheader('Exception reviews & audit history')
    st.warning('Reviewer names are self-entered. This is a classroom demonstration, not secure authorization.')
    all_alerts = read_json(DATA/'watchlist'/'events_seed.json', []) + state.get('alerts',[])
    if all_alerts:
        alert = st.selectbox('Case', all_alerts, format_func=lambda a:f'{a["id"]}: {a.get("company","Unknown")}')
        decision = st.selectbox('Disposition',
                                ['NEEDS_MORE_EVIDENCE','NO_POLICY_IMPACT','ESCALATE_FOR_POLICY_REVIEW','REJECT_FALSE_POSITIVE'])
        note = st.text_area('Reviewer rationale')
        if st.button('Record review decision'):
            if not note.strip():
                st.error('A rationale is required.')
            else:
                state.setdefault('reviews',[]).append({'alert_id':alert['id'], 'decision':decision,
                    'reviewer':actor, 'note':note, 'time':datetime.now(timezone.utc).isoformat()})
                append_event(state, actor, 'alert_reviewed',{'id':alert['id'],'decision':decision})
                save_state(state)
                st.success('Review recorded. No issuer classification or active policy changed.')
    st.markdown('**Review decisions**')
    st.dataframe(pd.DataFrame(state.get('reviews', [])), hide_index=True, use_container_width=True)
    st.markdown('**Audit events**')
    st.dataframe(pd.DataFrame(state.get('audit', [])[-100:]), hide_index=True, use_container_width=True)
