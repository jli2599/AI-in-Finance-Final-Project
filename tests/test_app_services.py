import unittest
from app_services.compliance import evaluate
from app_services.policies import candidates,validate_rule
from app_services.sec import screen_document,local_ollama_extract

class AppServicesTest(unittest.TestCase):
    def setUp(self):
        self.snap={'as_of':'2026-11-05','cash':100.,'positions':[{'ticker':'GE','issuer':'GE','sector':'Industrials','quantity':9,'price':100,'price_date':'2026-11-05','business_activities':['aerospace']}]}
    def test_concentration(self):
        r=evaluate(self.snap,[{'id':'x','type':'max_issuer_weight','value':.5}]);self.assertEqual(r['overall'],'FLAGGED')
    def test_business_eligibility(self):
        r=evaluate(self.snap,[{'id':'x','type':'excluded_business_activities','value':['aerospace']}]);self.assertEqual(r['overall'],'FLAGGED')
    def test_missing_classification_fails_closed(self):
        del self.snap['positions'][0]['business_activities']
        r=evaluate(self.snap,[{'id':'x','type':'excluded_business_activities','value':['aerospace']}]);self.assertEqual(r['overall'],'DATA_ISSUE')
    def test_prohibited_issuer_name_and_ticker(self):
        self.snap['positions'][0]['issuer']='General Electric'
        r=evaluate(self.snap,[{'id':'x','type':'prohibited_issuers','value':['GE']}]);self.assertEqual(r['overall'],'FLAGGED')
    def test_missing_price_fails_closed(self):
        self.snap['positions'][0]['price']=None
        r=evaluate(self.snap,[{'id':'x','type':'min_cash','value':.01}]);self.assertEqual(r['overall'],'DATA_ISSUE')
    def test_local_only(self):
        with self.assertRaises(ValueError):local_ollama_extract('test',{'url':'https://www.sec.gov'},endpoint='https://external.example')
    def test_event_screen_is_proposal(self):
        r=screen_document('The company completed a spin-off of its subsidiary.',{'url':'https://www.sec.gov'})
        self.assertEqual(r['proposed_status'],'NEEDS_REVIEW');self.assertEqual(r['method'],'keyword_baseline')
    def test_exclusions_extract(self):
        rules,invalid=candidates('5.2 Excluded business activities: coal mining, tobacco manufacturing','test.txt')
        self.assertFalse(invalid);self.assertEqual(rules[0]['type'],'excluded_business_activities')
    def test_rule_validation(self):
        with self.assertRaises(ValueError):validate_rule({'type':'max_issuer_weight','value':1.2,'clause_text':'x'})
if __name__=='__main__':unittest.main()
