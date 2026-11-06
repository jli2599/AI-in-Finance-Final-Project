"""One-shot local SEC polling. Schedule with cron/Task Scheduler if desired.

python monitor_sec.py --cik 40545 --name GE --contact analyst@example.org --limit 3
SEC access may throttle or refuse automated calls. Set a truthful contact email.
"""
import argparse
import json
from app_services.sec import recent_filings,download_filing,screen_document,local_ollama_extract
from app_services.store import load_state,save_state,append_event

def monitor(cik,name,contact,limit=3,use_ollama=False,model='qwen3:4b'):
    state=load_state(); new_alerts=[]
    for entry in recent_filings(cik,contact,limit=limit):
        accession=entry['accession']
        if accession in state.get('processed_accessions',[]):continue
        text=download_filing(entry,contact)
        outcome=screen_document(text,entry)
        if use_ollama:
            outcome['local_llm']=local_ollama_extract(text,entry,model=model)
        if outcome['events'] or outcome.get('local_llm',{}).get('events'):
            alert={'id':accession,'company':name,'cik':str(cik),'headline':f'Possible corporate event in {entry["form"]}',
                  'source_url':entry['url'],'filing_date':entry['filing_date'],'form':entry['form'],
                  'review_status':'PENDING','evidence_note':json.dumps(outcome)[:2500]}
            state.setdefault('alerts',[]).append(alert);new_alerts.append(alert)
        state.setdefault('processed_accessions',[]).append(accession)
    append_event(state,'SEC local monitor','sec_monitor_run',{'company':name,'new_alerts':len(new_alerts)})
    save_state(state)
    return new_alerts

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cik',required=True);p.add_argument('--name',required=True)
    p.add_argument('--contact',required=True);p.add_argument('--limit',type=int,default=3)
    p.add_argument('--ollama',action='store_true');p.add_argument('--model',default='qwen3:4b')
    a=p.parse_args();alerts=monitor(a.cik,a.name,a.contact,a.limit,a.ollama,a.model)
    print(json.dumps(alerts,indent=2))
