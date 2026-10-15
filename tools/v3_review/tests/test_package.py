import unittest
from tools.v3_review.package import validate_original, ORIGINAL_CODE_PATHS

def fixture():
    pins={p:'synthetic-hash' for p in ORIGINAL_CODE_PATHS}
    old={'kind':'E2EGatewayRegistry','version':'1.0.0','code_pins':pins}
    run=dict(kind='HistoricalGatewayDiagnosticRun',version='3.0.0',code_pins=pins.copy(),engine_called=True,status='SIMULATED_TRADES',production_enabled=False,historical_visibility_proven=False,evidence_grade='RECONSTRUCTED_HISTORY_DIAGNOSTIC',source_epoch='COMPATIBLE_GATEWAY_V3')
    return old,run
class PackageContractTests(unittest.TestCase):
    def test_exact_supported_contract(self):validate_original(*fixture())
    def test_missing_code_scope(self):
        o,r=fixture();o['code_pins'].pop(next(iter(o['code_pins'])))
        with self.assertRaises(ValueError):validate_original(o,r)
    def test_unknown_registry_version(self):
        o,r=fixture();o['version']='future'
        with self.assertRaises(ValueError):validate_original(o,r)
    def test_unrun_not_success(self):
        o,r=fixture();r['engine_called']=False
        with self.assertRaises(ValueError):validate_original(o,r)
    def test_failed_not_success(self):
        o,r=fixture();r['status']='ENGINE_FAILED'
        with self.assertRaises(ValueError):validate_original(o,r)
    def test_production_escalation(self):
        o,r=fixture();r['production_enabled']=True
        with self.assertRaises(ValueError):validate_original(o,r)
    def test_different_pin_binding(self):
        o,r=fixture();r['code_pins'][next(iter(r['code_pins']))]='other'
        with self.assertRaises(ValueError):validate_original(o,r)
