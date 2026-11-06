"""Policy ingestion and draft/approval lifecycle."""
from pathlib import Path
from ips_monitor.extract import extract_rules,verify_citations

SUPPORTED={'max_issuer_weight','max_sector_weight','min_cash','prohibited_issuers','excluded_business_activities','max_top_n_issuers','sector_specific_issuer_cap'}

def document_text(name,contents):
    ext=Path(name).suffix.lower()
    if ext in ('.txt','.md','.html','.htm'):
        if ext in ('.html','.htm'):
            from bs4 import BeautifulSoup
            return BeautifulSoup(contents,'html.parser').get_text('\n',strip=True)
        return contents.decode('utf-8')
    if ext=='.pdf':
        import fitz
        doc=fitz.open(stream=contents,filetype='pdf')
        return '\n'.join(page.get_text() for page in doc)
    if ext=='.docx':
        from io import BytesIO
        from docx import Document
        return '\n'.join(p.text for p in Document(BytesIO(contents)).paragraphs)
    raise ValueError('Supported policy files: TXT, HTML, PDF, DOCX')


def candidates(text,name):
    rules=extract_rules(text,name)
    import re
    for match in re.finditer(r'(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:excluded|prohibited)\s+(?:business\s+)?(?:activities|industries)\s*:\s*(.+)$',text):
        activities=[v.strip().lower() for v in match.group(1).split(',') if v.strip()]
        if activities:
            rules.append({'id':f'R{len(rules)+1}','type':'excluded_business_activities','value':activities,
                          'clause_ref':'business-exclusion','clause_text':match.group(0).strip(),
                          'source_doc':name,'extractor':'regex_baseline'})
    return rules,verify_citations(rules,text)


def validate_rule(rule):
    t=rule.get('type');v=rule.get('value')
    if t not in SUPPORTED: raise ValueError('Unsupported rule type')
    if t in {'max_issuer_weight','max_sector_weight','min_cash'}:
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=1:
            raise ValueError('Weight must be a numeric fraction between 0 and 1')
    elif t=='max_top_n_issuers':
        if (not isinstance(v,dict) or type(v.get('n')) is not int or not 1<=v['n']<=100 or
            type(v.get('max_weight')) not in (int,float) or not 0<=v['max_weight']<=1):
            raise ValueError('Top-N rule expects {"n": positive integer, "max_weight": fraction}')
    elif t=='sector_specific_issuer_cap':
        if (not isinstance(v,dict) or type(v.get('default')) not in (int,float) or
            not 0<=v['default']<=1 or not isinstance(v.get('overrides'),dict) or
            not all(isinstance(k,str) and k.strip() and type(x) in (int,float) and 0<=x<=1
                    for k,x in v['overrides'].items())):
            raise ValueError('Sector issuer caps expect {"default": fraction, "overrides": {sector: fraction}}')
    else:
        if not isinstance(v,list) or not v or not all(isinstance(x,str) and x.strip() for x in v):
            raise ValueError('Restricted values must be a nonempty list of strings')
    if not rule.get('clause_text'): raise ValueError('A source clause is required')
    return True
