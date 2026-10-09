import copy, hashlib, http.client, json, tempfile, threading, unittest
from pathlib import Path
from workbench.server import Reader, ReadError, FILES, SYMBOLS, Handler, ThreadingHTTPServer, digest

class AdapterTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()/'repo';self.root.mkdir();self.private=Path(self.temp.name).resolve()/'reports';self.private.mkdir();self.reader=Reader(self.root,self.private)
  self.integration={'kind':'RootP1HistoricalIntegrationGate','version':'1.0.0','engineering_integration':'PASS_WITH_CONDITIONS','strategy':{'actual_PIT_admitted':0,'formal_windows_executed':0,'engine':'ENGINE_NOT_RUN','economic_metrics':None}}
  self.forward={'kind':'Day1RevealStatus','version':'1.0.0','actual_D1':'BLOCKED','actual_forward_days':0}
  self.write('integration',self.integration);self.write('forward',self.forward)
  self.write('integration-report','7,567股票价格日期、582财务报告期记录')
  artifacts=[]
  for symbol in SYMBOLS:
   text=f'# 合成夹具（{symbol}）— 本地真实研究报告 2.0\n本轮观察截止：2026-10-06T07:50:49Z；最新接收：未知\n## 最强反证\nSYNTHETIC / NOT_PRODUCTION\n'
   p=self.private/(symbol+'.report.md');p.write_text(text);raw=p.read_bytes();artifacts.append({'name':p.name,'path':str(p),'bytes':len(raw),'sha256':digest(raw)})
  self.manifest={'version':'1.0.0','artifacts':artifacts};self.write('manifest',self.manifest)
  self.write('readback',{'kind':'MetaSurveyHandoffReadOnlyEvidenceIndex','version':'1.0.0','read_only_replay':{'old_pin_differences':[]}})
 def write(self,key,data):
  p=self.root/FILES[key];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data) if isinstance(data,dict) else data)
 def reject(self,code,callback):
  with self.assertRaises(ReadError) as caught: callback()
  self.assertEqual(caught.exception.code,code)
 def test_values_are_actual_source_values(self):
  state=self.reader.state();self.assertEqual(state['coverage']['price_dates'],7567);self.assertEqual(state['panels']['integration']['data']['strategy']['economic_metrics'],None)
 def test_refresh_reads_changes_without_cache(self):
  self.reader.state();self.forward['actual_forward_days']=7;self.write('forward',self.forward);self.assertEqual(self.reader.state()['panels']['forward']['data']['actual_forward_days'],7)
 def test_missing_file_is_visible_error_not_zero(self):
  (self.root/FILES['integration']).unlink();state=self.reader.state();self.assertNotIn('integration',state['panels']);self.assertTrue(any(e['code']=='FILE_MISSING' for e in state['errors']))
 def test_unsupported_version_blocks_panel(self):
  self.integration['version']='999';self.write('integration',self.integration);self.assertEqual(self.reader.state()['errors'][0]['code'],'UNSUPPORTED_VERSION')
 def test_unknown_state_blocks_panel(self):
  self.integration['strategy']['engine']='MAGIC';self.write('integration',self.integration);self.assertEqual(self.reader.state()['errors'][0]['code'],'UNKNOWN_STATUS')
 def test_wrong_kind_blocks_panel(self):
  self.integration['kind']='Other';self.write('integration',self.integration);self.assertEqual(self.reader.state()['errors'][0]['code'],'UNSUPPORTED_KIND')
 def test_bool_is_not_day_count(self):
  self.forward['actual_forward_days']=True;self.write('forward',self.forward);self.assertTrue(any(e['code']=='INVALID_SHAPE' for e in self.reader.state()['errors']))
 def test_malformed_json_is_visible(self):
  self.write('forward','not json');self.assertTrue(any(e['code']=='INVALID_JSON' for e in self.reader.state()['errors']))
 def test_report_matches_frozen_hash(self):
  result=self.reader.research(SYMBOLS[0]);self.assertEqual(result['sha256'],result['expected_sha256']);self.assertFalse(result['formal_candidate']);self.assertIsNone(result['formal_grade'])
 def test_changed_report_is_rejected(self):
  p=self.private/(SYMBOLS[0]+'.report.md');p.write_text(p.read_text()+'changed');self.reject('HASH_MISMATCH',lambda:self.reader.research(SYMBOLS[0]))
 def test_wrong_size_is_rejected(self):
  self.manifest['artifacts'][0]['bytes']+=1;self.write('manifest',self.manifest);self.reject('HASH_MISMATCH',lambda:self.reader.research(SYMBOLS[0]))
 def test_missing_private_report(self):
  (self.private/(SYMBOLS[0]+'.report.md')).unlink();self.assertEqual(self.reader.state()['studies'][0]['error'],'FILE_MISSING')
 def test_private_manifest_cannot_choose_path(self):
  self.manifest['artifacts'][0]['path']='/tmp/secret.txt';self.write('manifest',self.manifest);self.reject('MANIFEST_PATH_INVALID',lambda:self.reader.research(SYMBOLS[0]))
 def test_duplicate_manifest_entry_blocks(self):
  self.manifest['artifacts'].append(self.manifest['artifacts'][0]);self.write('manifest',self.manifest);self.reject('MANIFEST_ENTRY_INVALID',lambda:self.reader.research(SYMBOLS[0]))
 def test_account_template_is_read_only(self):
  self.write('account-template',{'profile_kind':'UNCONFIGURED','account_id':'UNSET_REQUIRED'});self.assertIn('UNSET_REQUIRED',self.reader.document('account-template')['content'])
 def test_runtime_account_cannot_replace_template(self):
  self.write('account-template',{'profile_kind':'ACTUAL','account_id':'real-account'});self.reject('RUNTIME_ACCOUNT_NOT_EXPOSED',lambda:self.reader.document('account-template'))
 def test_traversal_blocked(self): self.reject('NOT_ALLOWLISTED',lambda:self.reader.document('../../passwords'))
 def test_unapproved_symbol_blocked(self): self.reject('NOT_ALLOWLISTED',lambda:self.reader.research('000001.SZ'))
 def test_symlink_blocked(self):
  p=self.root/FILES['forward'];p.unlink();p.symlink_to(self.root/FILES['integration']);self.reject('UNSAFE_PATH',lambda:self.reader.document('forward'))
 def test_sensitive_content_blocked(self):
  self.write('integration-report','token="'+'x'*40+'"');self.reject('SENSITIVE_CONTENT_BLOCKED',lambda:self.reader.document('integration-report'))
 def test_report_unsupported_version(self):
  p=self.private/(SYMBOLS[0]+'.report.md');p.write_text(p.read_text().replace('报告 2.0','报告 9.0'));raw=p.read_bytes();self.manifest['artifacts'][0].update(bytes=len(raw),sha256=digest(raw));self.write('manifest',self.manifest);self.reject('UNSUPPORTED_REPORT_VERSION',lambda:self.reader.research(SYMBOLS[0]))
 def test_reads_preserve_all_input_bytes(self):
  files=[p for folder in (self.root,self.private) for p in folder.rglob('*') if p.is_file()];before={str(p):digest(p.read_bytes()) for p in files};self.reader.state();[self.reader.research(s) for s in SYMBOLS];self.assertEqual(before,{str(p):digest(p.read_bytes()) for p in files})

class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.server.reader=Reader();cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
 def request(self,path,method='GET',headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request(method,path,headers=headers or {});r=c.getresponse();body=r.read();headers=dict(r.getheaders());c.close();return r.status,headers,body
 def test_index_runs_with_local_assets(self):
  status,headers,body=self.request('/');self.assertEqual(status,200);self.assertIn(b'/app.js',body);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
 def test_actual_state_fields(self):
  status,_,body=self.request('/api/state');self.assertEqual(status,200);v=json.loads(body);self.assertEqual(v['mode'],'LOCAL_READ_ONLY');self.assertEqual(v['task_runtime'],'NOT_CONNECTED_NO_LIVE_HEARTBEAT')
 def test_post_does_not_execute(self): self.assertEqual(self.request('/api/state','POST')[0],405)
 def test_foreign_origin_rejected(self): self.assertEqual(self.request('/api/state',headers={'Origin':'https://attacker.example'})[0],403)
 def test_foreign_host_rejected(self): self.assertEqual(self.request('/api/state',headers={'Host':'attacker.example'})[0],403)
 def test_cross_site_request_rejected(self): self.assertEqual(self.request('/api/state',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
 def test_no_directory_or_database_endpoint(self):
  for path in ('/package.json','/../AGENTS.md','/api/evidence/../../.env','/api/evidence/evidence.sqlite'):
   self.assertIn(self.request(path)[0],(404,422))
 def test_queries_not_logged_or_accepted(self): self.assertEqual(self.request('/api/state?token=example')[0],400)
 def test_encoded_research_evidence_id(self):
  status,_,body=self.request('/api/evidence/research%3A603993.SH');self.assertIn(status,(200,422));self.assertNotEqual(json.loads(body).get('error'),'NOT_ALLOWLISTED')

if __name__=='__main__': unittest.main()
