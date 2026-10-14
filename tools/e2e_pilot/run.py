"""One-shot local research and historical admission attempt, no network or secrets.
Reads only fixed captured documents; never overwrites output or old frozen assets.
"""
from pathlib import Path
import argparse,datetime,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from experiments.e2e_pilot_v1.research import evaluate,validate_run,digest,seal
from experiments.e2e_pilot_v1.execution import RULES,STRATEGY,NAMESPACE,run_diagnostic,build_portfolio,digest as object_hash
from workbench.e2e_reader import ARCHIVE,CODE,SOURCE_NAMES

def main():
 p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--verify-existing',action='store_true');a=p.parse_args()
 if a.verify_existing:
  from workbench.server import Reader
  from workbench.e2e_reader import load
  result=load(Reader());print(json.dumps({'integrity':result['integrity'],'run_id':result['run_id'],'historical_status':result['diagnostic']['status'],'engine_called':result['diagnostic']['engine_called']},ensure_ascii=False));return
 if not a.output:raise ValueError('OUTPUT_OR_VERIFY_EXISTING_REQUIRED')
 out=Path(a.output)
 if out.resolve()!=out or out.parent!=ARCHIVE:raise ValueError('FIXED_ARCHIVE_OUTPUT_REQUIRED')
 if out.exists():raise ValueError('NO_OVERWRITE_RUN')
 cfgraw=(ROOT/'experiments/e2e_pilot_v1/method.json').read_bytes();protoraw=(ROOT/'experiments/e2e_pilot_v1/protocol.json').read_bytes();cfg=json.loads(cfgraw);proto=json.loads(protoraw)
 inputs=json.loads((ARCHIVE/'data/Financial-Inputs.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 admission={'license_for_local_historical_diagnostic':False,'historical_price_visibility':False,'calendar_complete':False,'execution_domains_complete':False,'membership_scope_explicit':True,'source':'EXISTING_QUARANTINED_GATEWAY_ARCHIVE','product':'daily and associated historical reference capture','purpose':'LOCAL_HISTORICAL_DIAGNOSTIC_REQUESTED_NOT_ADMITTED','evidence_refs':['docs/e2e-pilot-v1/Data-Feasibility.md','docs/backtest-5y-integration/Status.json'],'evidence_kind':'ACTUAL_READ_ONLY_COVERAGE_AUDIT_NOT_LICENSE','gaps':['PROVIDER_LICENSE_UNVERIFIED','HISTORICAL_FIRST_VISIBLE_VERSION_ABSENT','NO_NINE_MEMBER_COMPLETE_HISTORY','SESSION_STATUS_LIMIT_LOT_ACTION_CHAIN_INCOMPLETE','RAW_MARKET_PAYLOAD_NOT_CONSUMED_BY_ENGINE']}
 case={'namespace':NAMESPACE,'strategy_id':STRATEGY,'label':'HISTORICAL_DIAGNOSTIC','run_id':'E2E-PILOT-V1-20261014-DIAGNOSTIC-ATTEMPT-01','rules':RULES,'rules_hash':object_hash(RULES),'method_ref':digest(cfgraw),'preregistration_ref':digest(protoraw),'frozen_at':proto['frozen_at'],'run_at':now,'admission':admission,'admission_hash':object_hash(admission),'calendar':[],'bars':[],'universe':[{'symbol':m['symbol'],'sector':s['id'],'selection_evidence_ref':digest(cfgraw)} for s in cfg['universe'] for m in s['members']],'window':{'first_session':'2025-10-01','last_session':'2026-09-30','status':'TARGET_ONLY_NO_ADMITTED_EXCHANGE_CALENDAR'},'fee_schedule':proto['fee_schedule']}
 casepath=ARCHIVE/'Diagnostic-Case.json'
 if casepath.exists():case=json.loads(casepath.read_text())
 else:
  with casepath.open('x') as f:json.dump(case,f,ensure_ascii=False,indent=2);f.write('\n')
 result=run_diagnostic(case)
 data=evaluate(inputs,cfg)
 portfolio=build_portfolio([],10000000,[],10000000,proto['fee_schedule'],'2026-10-14')
 portfolio.update(state='BLOCKED_NO_COMPLETE_CANDIDATES_OR_ADMITTED_PRICE',cash_cents=portfolio['remaining_cash_cents'],positions=[],planned_orders=portfolio['plans'],risk_budget_cents=100000,account_kind='VIRTUAL_EXPERIMENT_NOT_OWNER_ACCOUNT',builder_called=True,eligibility_rejections=[{'symbol':x['symbol'],'reason':'FULL_SCORE_AND_EXECUTION_INPUTS_INCOMPLETE'} for x in data['companies']])
 pins=[{'path':str(ARCHIVE/n),'sha256':digest((ARCHIVE/n).read_bytes()),'bytes':(ARCHIVE/n).stat().st_size} for n in SOURCE_NAMES]
 package={'kind':'E2EPilotRun','version':'1.0.0','experiment_id':cfg['experiment_id'],'namespace':NAMESPACE,'run_id':'E2E-PILOT-V1-20261014-RESEARCH-01','recorded_at':now,'method_version':'SAMPLE_FINANCIAL_HEALTH_V1 / COMPANY_SEVEN_FACTOR_V1_PARTIAL','result_type':'CURRENT_OBSERVED_EXPERIMENTAL_RESEARCH','method_hash':digest(cfgraw),'protocol_hash':digest(protoraw),'financial_inputs':inputs,'financial_inputs_sha256':digest((ARCHIVE/'data/Financial-Inputs.json').read_bytes()),'diagnostic_case':case,'diagnostic_case_sha256':digest(casepath.read_bytes()),'source_pins':pins,'historical_coverage_audit':json.loads((ARCHIVE/'data/Historical-Coverage-Audit.json').read_text()),'historical_coverage_audit_sha256':digest((ARCHIVE/'data/Historical-Coverage-Audit.json').read_bytes()),**data,'portfolio':portfolio,'diagnostic':result,'productionGate':False,'historical_visibility_proven':False,'limitations':['九家公司是预先固定的业务样本，不代表整个行业。','财务代理分数来自FY2025合并报表，不是原九维板块总分或上涨概率。','公司仅基本面因子可计算；其余因子、风险及总分仍缺证据。','历史任务完成准入尝试；引擎未运行，成交/净值/绩效不存在。','原始PDF仅本地保存；不声明供应方许可、历史PIT或独立人类审核通过。','景旺报告已发现后续修订，本轮固定原件不宣称最新版本。']}
 package['content_hash']=seal(package);validate_run(package,root=ROOT)
 with out.open('x') as f:json.dump(package,f,ensure_ascii=False,indent=2);f.write('\n')
 registry={'kind':'E2EPilotRegistry','version':'1.0.0','package_path':str(out),'package_sha256':digest(out.read_bytes()),'package_content_hash':package['content_hash'],'code_pins':{n:digest((ROOT/n).read_bytes()) for n in CODE},'source_pins':pins,'recorded_at':now,'result_type':package['result_type'],'run_id':package['run_id'],'productionGate':False}
 reg=ROOT/'docs/e2e-pilot-v1/Registry.json'
 with reg.open('x') as f:json.dump(registry,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'run_id':package['run_id'],'companies':len(data['companies']),'financial_components':sum(x['score'] is not None for co in data['companies'] for x in co['components']),'sector_proxy_subtotals':sum(x['financial_proxy_subtotal'] is not None for x in data['sectors']),'company_complete_totals':sum(x['total'] is not None for x in data['companies']),'diagnostic_status':result['status'],'engine_called':result['engine_called']},ensure_ascii=False))
if __name__=='__main__':main()
