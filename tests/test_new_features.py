"""Offline tests for the new policy examples and local SEC inbox."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from app_services.compliance import evaluate
from app_services.policies import validate_rule
from app_services.sec_local import scan_local_filings, match_issuer, normalize_cik


class ExtendedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'as_of':'2026-11-05', 'cash':200,
          'positions':[
            {'ticker':'AAA','issuer':'A Holdings','sector':'Technology','quantity':40,'price':10,'price_date':'2026-11-05'},
            {'ticker':'BBB','issuer':'B Holdings','sector':'Technology','quantity':25,'price':10,'price_date':'2026-11-05'},
            {'ticker':'CCC','issuer':'C Holdings','sector':'Industrials','quantity':15,'price':10,'price_date':'2026-11-05'}
          ]}
        # NAV $1000, issuer weights 40%, 25%, 15%, cash 20%.

    def test_top_two_aggregation(self):
        r = {'id':'T1','type':'max_top_n_issuers','value':{'n':2,'max_weight':0.60},'clause_text':'Top 2 <= 60%'}
        out = evaluate(self.snapshot, [r])
        self.assertEqual(out['overall'], 'FLAGGED')
        self.assertAlmostEqual(out['results'][0]['offenders']['top_n_total'], 0.65)
        self.assertIn('65.00%', out['results'][0]['observed'])
        r['value']['max_weight'] = 0.65
        self.assertEqual(evaluate(self.snapshot,[r])['overall'], 'COMPLIANT')

    def test_sector_specific_caps(self):
        r = {'id':'S1','type':'sector_specific_issuer_cap',
             'value':{'default':0.50,'overrides':{'Technology':0.35}},'clause_text':'Tech 35%; otherwise 50%'}
        out = evaluate(self.snapshot,[r])
        self.assertEqual(out['results'][0]['status'], 'FAIL')
        self.assertEqual(list(out['results'][0]['offenders']), ['A Holdings'])
        r['value']['overrides']['Technology'] = 0.40
        self.assertEqual(evaluate(self.snapshot,[r])['overall'],'COMPLIANT')

    def test_invalid_rule_configs(self):
        for value in [{'n':0,'max_weight':0.5},{'n':True,'max_weight':0.5},{'n':3,'max_weight':2.0}]:
            with self.assertRaises(ValueError):
                validate_rule({'type':'max_top_n_issuers','value':value,'clause_text':'sample'})
        with self.assertRaises(ValueError):
            validate_rule({'type':'sector_specific_issuer_cap',
                           'value':{'default':0.1,'overrides':{'Technology':-0.1}},'clause_text':'sample'})

    def test_bad_data_prevents_false_pass_even_with_complex_rule(self):
        self.snapshot['positions'][2]['price_date'] = None
        r = {'id':'T1','type':'max_top_n_issuers','value':{'n':2,'max_weight':0.99}}
        out=evaluate(self.snapshot,[r])
        self.assertEqual(out['overall'], 'DATA_ISSUE')


class OfflineInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.watch = [{'id':'ge','name':'General Electric / GE Aerospace','ticker':'GE',
                       'cik':'0000040545','aliases':['General Electric Company','GE Aerospace']}]
        self.state = {'watchlist': copy.deepcopy(self.watch),'alerts':[],
                      'processed_local_documents':{},'local_checks':[]}
    def tearDown(self):
        self.temp.cleanup()

    def test_file_scanning_offline_and_deduplicated(self):
        (self.root/'event.txt').write_text('General Electric Company completed a spin-off of its energy business.',encoding='utf-8')
        one = scan_local_filings(self.state,self.root)
        self.assertEqual(one[0]['status'],'POSSIBLE_EVENT_REVIEW')
        self.assertEqual(len(self.state['alerts']),1)
        self.assertEqual(self.state['alerts'][0]['source_kind'],'local_file')
        two = scan_local_filings(self.state,self.root)
        self.assertEqual(two[0]['status'],'SKIPPED_ALREADY_SCANNED')
        self.assertEqual(len(self.state['alerts']),1)
        three = scan_local_filings(self.state,self.root,force=True)
        self.assertEqual(three[0]['status'],'POSSIBLE_EVENT_REVIEW')
        self.assertEqual(len(self.state['alerts']),1)

    def test_manifest_matching_and_no_event(self):
        (self.root/'filing.txt').write_text('Quarterly statement with no corporate action.',encoding='utf-8')
        (self.root/'manifest.csv').write_text('filename,issuer_name,ticker,cik,form,filing_date,source_url,source_type\n'
              'filing.txt,,GE,0000040545,10-Q,2026-11-05,,public\n',encoding='utf-8')
        out=scan_local_filings(self.state,self.root)
        self.assertEqual(out[0]['status'],'NO_EVENT_TRIGGER')
        self.assertEqual(len(self.state['alerts']),0)

    def test_unknown_company_is_not_assigned(self):
        (self.root/'unmatched.txt').write_text('An unknown corporation completed a merger.',encoding='utf-8')
        out=scan_local_filings(self.state,self.root)
        self.assertEqual(out[0]['status'],'UNMATCHED_DOCUMENT')
        self.assertEqual(len(self.state['alerts']),0)

    def test_manifest_ambiguity_fails_closed(self):
        self.state['watchlist'].append({'id':'duplicate','name':'GE Holdings','ticker':'GE','cik':'0000040545'})
        (self.root/'event.txt').write_text('A spin-off was completed.',encoding='utf-8')
        (self.root/'manifest.csv').write_text('filename,issuer_name,ticker,cik\nevent.txt,,,0000040545\n',encoding='utf-8')
        out=scan_local_filings(self.state,self.root)
        self.assertEqual(out[0]['status'],'AMBIGUOUS_MANIFEST')
        self.assertEqual(len(self.state['alerts']),0)

    def test_no_model_required_and_errors_visible(self):
        (self.root/'event.txt').write_text('General Electric Company completed a spin-off.',encoding='utf-8')
        out=scan_local_filings(self.state,self.root,use_llm=True,model='nonexistent')
        self.assertEqual(out[0]['status'],'POSSIBLE_EVENT_REVIEW')
        self.assertIn('llm_error',out[0])
        self.assertIn('fallback',out[0]['method'])
        self.assertEqual(len(self.state['alerts']),1)

    def test_cik_normalization(self):
        self.assertEqual(normalize_cik('40545'),'0000040545')
        self.assertEqual(normalize_cik('GE'),'')


if __name__=='__main__':
    unittest.main()
