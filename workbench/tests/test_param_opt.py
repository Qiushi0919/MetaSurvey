import json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from workbench.server import Reader,ReadError,digest
from workbench.param_opt_reader import load
from workbench.tests import test_performance_ui as perfui
class ReaderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()/'repo';self.root.mkdir();self.r=Reader(root=self.root)
  self.data=dict(kind='ParameterOptimizationReview',version='1.0.0',experiment='CORE40_PARAM_OPT_V1',search_configs=108,table=[{}]*108,classification='EXPOSED_HISTORY_EXPLORATORY_OPTIMIZATION',locked_ids=['P009'])
  pins={}
  for name in ('experiments/param_opt_v1/engine.py','tools/param_opt/run.py','tools/param_opt/report.py','workbench/param_opt_reader.py'):
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# SYNTHETIC\n');pins[name]=digest(p.read_bytes())
  self.registry=dict(kind='ParameterOptimizationRegistry',version='1.0.0',code_pins=pins)
  self.save()
 def save(self):
  p=self.root/'docs/param-opt-v1';p.mkdir(parents=True,exist_ok=True);r=p/'Results.json';r.write_text(json.dumps(self.data));self.registry['results_hash']=digest(r.read_bytes());(p/'Registry.json').write_text(json.dumps(self.registry))
 def test_public_without_private_never_claims_recomputed(self):self.assertEqual(load(self.r)['status'],'PUBLIC_ARCHIVED_METADATA_ONLY')
 def test_changed_result_blocks(self):
  (self.root/'docs/param-opt-v1/Results.json').write_text(json.dumps(dict(self.data,search_configs=107)))
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_RESULTS_HASH'):load(self.r)
 def test_changed_code_blocks(self):
  (self.root/'tools/param_opt/run.py').write_text('# changed')
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_CODE_CHANGED'):load(self.r)
 def test_unknown_version_blocks(self):
  self.registry['version']='2.0.0';self.save()
  with self.assertRaises(ReadError):load(self.r)
 def test_parent_escape_blocks(self):
  self.registry['code_pins']['../private.py']='sha256:'+'0'*64;self.save()
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_CODE_SCOPE'):load(self.r)
 def test_partial_pin_list_blocks(self):
  self.registry['code_pins']={};self.save()
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_CODE_PINS_MISSING'):load(self.r)
 def test_oos_relabel_blocks(self):
  self.data['classification']='OOS';self.save()
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_SCOPE'):load(self.r)
 def test_more_than_three_locked_blocks(self):
  self.data['locked_ids']=['A','B','C','D'];self.save()
  with self.assertRaisesRegex(ReadError,'PARAM_OPT_SCOPE'):load(self.r)
 def test_missing_result_blocks(self):
  (self.root/'docs/param-opt-v1/Results.json').unlink()
  with self.assertRaisesRegex(ReadError,'FILE_MISSING'):load(self.r)
 def test_private_archive_symlink_blocks(self):
  p=self.root.parent/'.p1b-archives';p.mkdir();(p/'param-opt-20261020').symlink_to(self.root,target_is_directory=True)
  try:
   with self.assertRaisesRegex(ReadError,'PARAM_OPT_PRIVATE_SCOPE'):load(self.r)
  finally:
   (p/'param-opt-20261020').unlink();p.rmdir()
class ParamUITests(unittest.TestCase):
 def js(self,expression):
  code=perfui.BOOT+"\nconsole.log(JSON.stringify(vm.runInContext("+json.dumps(expression)+",context)));"
  r=subprocess.run([perfui.NODE,"-"],input=code,cwd=perfui.ROOT,text=True,capture_output=True,check=True)
  return json.loads(r.stdout)
 def test_error_does_not_render_performance(self):
  self.assertEqual(self.js('state.param_opt={status:"INTEGRITY_ERROR",reason:"SYNTHETIC_CHANGED"};optimization();({error:main.textContent.includes("SYNTHETIC_CHANGED"),charts:document.nodes.filter(n=>n.tag==="svg").length})'),{'error':True,'charts':0})
 def test_absent_has_no_zero_return(self):
  self.assertEqual(self.js('state.param_opt=null;optimization();({missing:main.textContent.includes("尚无已登记运行"),zero:main.textContent.includes("0.00%")})'),{'missing':True,'zero':False})
 def test_real_projection_units_controls_and_selectors(self):
  # Published aggregate only, never private originals. Render exact values, then switch window.
  p=Path(__file__).parents[2]/'docs/param-opt-v1/Results.json';data=json.loads(p.read_text())
  result=self.js('state.param_opt='+json.dumps({'status':'PUBLIC_ARCHIVED_METADATA_ONLY','data':data},ensure_ascii=False)+';optimization();let initial=main.textContent;let w=document.nodes.find(n=>n.attrs["aria-label"]==="比较时间分区");w.value="selection";w.events.change();({public:initial.includes("未重新验算"),pct:initial.includes("37.06%"),cash:initial.includes("¥137,064.89"),controls:initial.includes("BUY_HOLD")||initial.includes("九股持有"),selection:main.textContent.includes("17.13%"),charts:document.nodes.filter(n=>n.tag==="svg").length})')
  self.assertTrue(result['public']);self.assertTrue(result['pct']);self.assertTrue(result['cash']);self.assertTrue(result['controls']);self.assertGreaterEqual(result['charts'],3)
