"""Synthetic Node DOM and pure-display tests; no browser, network or private files."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node') or '/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
BOOT = r'''
const vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.events={};this.style={};this.value='';this._text='';}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;this._text='';}
 setAttribute(k,v){this.attrs[k]=String(v);}addEventListener(k,f){this.events[k]=f;}
 get firstChild(){return this.children[0];}set textContent(v){this._text=String(v);this.children=[];}
 get textContent(){return this._text+this.children.map(x=>typeof x==='string'?x:x.textContent).join(' ');}
 querySelectorAll(){return [];}get classList(){return {toggle(){}};}
}
const nodes=[],ids={};const make=t=>{let e=new Element(t);nodes.push(e);return e;};
const document={nodes,querySelector:s=>ids[s]||(ids[s]=make(s)),createElement:make,createElementNS:(_,t)=>make(t),createTextNode:t=>String(t),querySelectorAll:()=>[]};
const context={document,Node:Element,window:{addEventListener(){}},location:{hash:''},fetch:()=>new Promise(()=>{}),console};vm.createContext(context);vm.runInContext(fs.readFileSync('workbench/static/app.js','utf8'),context);
const fixture={version:'2.0.0',run_id:'SYNTHETIC',engine_called:true,status:'SIMULATED_TRADES',net_return:'0.05',maximum_drawdown:'0.10',complete_trades:0,total_fee_cents:500,total_slippage_cents:100,final_cash_cents:10500,dividend_tax_label:'SYNTHETIC_TAX',errors:[],last_completed_session:'2026-01-03',daily:[{session:'2026-01-01',nav_cents:10000,cash_cents:10000,exposure_cents:0,receivable_cents:0,positions:[]},{session:'2026-01-02',nav_cents:9000,cash_cents:5000,exposure_cents:4000,receivable_cents:0,positions:[]},{session:'2026-01-03',nav_cents:10500,cash_cents:10500,exposure_cents:0,receivable_cents:0,positions:[]}],fills:[{session:'2026-01-02',symbol:'SYNTHETIC',side:'BUY',quantity:100,execution_price:'1.00',fees:{notional_cents:10000,commission_cents:500,minimum_commission_uplift_cents:200,sell_tax_cents:0,other_cents:0,exchange_cents:0,slippage_cents:100,total_fee_cents:500},cash_after_cents:5000}],unfilled:[{session:'2026-01-02',symbol:'SYNTHETIC',side:'BUY',reason:'POSITION_COUNT_LIMIT'}],ledger:[{kind:'ACTION_EX',net_receivable_cents:200,cash_delta_cents:0},{kind:'DIVIDEND_PAYMENT',session:'2026-01-03',symbol:'SYNTHETIC',cash_delta_cents:200,cash_after_cents:10500}],dividends:[]};context.fixture=fixture;
vm.runInContext("state={read_at:'SYNTHETIC',gateway_v3:{run:{run_id:'SYNTHETIC',engine_called:true,status:'SIMULATED_TRADES',engine_result_hash:'sha256:SYNTHETIC'},diagnostic:fixture,source:{source:'SYNTHETIC'},api_matrix:[]}}",context);
'''

class PerformanceUITests(unittest.TestCase):
    def js(self, expression):
        code=BOOT+'\nconsole.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',context)));'
        out=subprocess.run([NODE,'-e',code],cwd=ROOT,text=True,capture_output=True,check=True)
        return json.loads(out.stdout)
    def test_money_and_percent_units(self):
        self.assertEqual(self.js('[perfMoney(100005),perfPercent("0.0596976")]'),['¥1,000.05','5.97%'])
    def test_null_is_not_zero(self):
        self.assertEqual(self.js('[perfMoney(null),perfPercent(undefined),perfNumber("")]'),['暂无结果','暂无结果',None])
    def test_zero_is_real_zero(self):
        self.assertEqual(self.js('[perfMoney(0),perfPercent(0)]'),['¥0.00','0.00%'])
    def test_nonfinite_rejected(self):
        self.assertEqual(self.js('[perfNumber("NaN"),perfNumber("Infinity"),perfNumber(false)]'),[None,None,None])
    def test_drawdown_dates_and_recovery(self):
        x=self.js('perfDrawdown(fixture.daily)')
        self.assertEqual((x['peak_session'],x['trough_session'],x['recovery_session']),('2026-01-01','2026-01-02','2026-01-03'))
        self.assertEqual(x['drawdown_fraction'],0.1)
    def test_unrecovered_drawdown(self):
        self.assertIsNone(self.js('perfDrawdown(fixture.daily.slice(0,2)).recovery_session'))
    def test_empty_nav_unknown(self):
        self.assertIsNone(self.js('perfDerived({...fixture,daily:[]}).final_nav_cents'))
    def test_dividend_not_double_counted(self):
        self.assertEqual(self.js('perfDerived(fixture).dividend_cash_cents'),200)
    def test_minimum_uplift_not_added_twice(self):
        self.assertEqual(self.js('perfDerived(fixture).fees.total_fee_cents'),500)
        self.assertEqual(self.js('perfDerived(fixture).fees.minimum_commission_uplift_cents'),200)
    def test_missing_fee_component_stays_unknown(self):
        self.assertIsNone(self.js('delete fixture.fills[0].fees.commission_cents;perfDerived(fixture).fees.commission_cents'))
        self.assertIsNone(self.js('fixture.fills[0].fees.other_cents=null;perfDerived(fixture).fees.other_cents'))
    def test_payload_other_run_not_displayed(self):
        self.assertIsNone(self.js('perfBoundPayload({run:{run_id:"A",engine_result_hash:"H"},performance:{status:"VERIFIED",run_id:"B",engine_result_hash:"H"}})'))
    def test_payload_other_result_not_displayed(self):
        self.assertIsNone(self.js('perfBoundPayload({run:{run_id:"A",engine_result_hash:"H"},performance:{status:"VERIFIED",run_id:"A",engine_result_hash:"OTHER"}})'))
    def test_matching_verified_contributions_display(self):
        result=self.js('state.gateway_v3.performance={status:"VERIFIED",run_id:"SYNTHETIC",engine_result_hash:"sha256:SYNTHETIC",performance:{symbol_contributions:[{symbol:"SYNTHETIC",group:"PCB_SAMPLE",contribution_cents:12345,contribution_fraction:"0.12345",buy_cash_out_cents:10000,sell_cash_in_cents:22345,dividend_paid_cents:0,ending_market_value_cents:0,ending_receivable_cents:0}],group_contributions:[],reconciliation:{status:"SYNTHETIC"}},benchmarks:[]};gatewayDiagnostic();({contribution:main.textContent.includes("¥123.45"),fraction:main.textContent.includes("12.35%"),meaning:main.textContent.includes("不是每只股票自身的持有收益率"),noBenchmark:main.textContent.includes("尚无可核验的基准结果")})')
        self.assertEqual(result,{'contribution':True,'fraction':True,'meaning':True,'noBenchmark':True})
    def test_matching_dates_required_for_benchmark_curve(self):
        result=self.js('state.gateway_v3.performance={status:"VERIFIED",run_id:"SYNTHETIC",engine_result_hash:"sha256:SYNTHETIC",performance:{},benchmarks:[{name:"合成同日基准",nav_series:perfSeries(fixture.daily),net_return:"0.05",max_drawdown:"0.10"},{name:"合成异日基准",nav_series:[{session:"1900-01-01",nav_cents:1,drawdown_fraction:0}]}]};gatewayDiagnostic();({paths:document.nodes.filter(n=>n.tag==="path").length,benchmark:main.textContent.includes("合成同日基准")})')
        self.assertEqual(result,{'paths':5,'benchmark':True})
    def test_chart_renders_svg_and_table_page(self):
        result=self.js('gatewayDiagnostic(); ({svg:document.nodes.filter(n=>n.tag==="svg").length,hasYuan:main.textContent.includes("¥105.00"),hasPct:main.textContent.includes("5.00%"),reasons:main.textContent.includes("已达到最多持仓数量"),technicalClosed:document.nodes.filter(n=>n.tag==="details").every(n=>!n.open)})')
        self.assertEqual(result,{'svg':3,'hasYuan':True,'hasPct':True,'reasons':True,'technicalClosed':True})
    def test_source_blocked_has_no_fake_curve(self):
        result=self.js('state.gateway_v3.run.engine_called=false;state.gateway_v3.diagnostic=null;state.gateway_v3.build_report={errors:["SYNTHETIC_BLOCKED"]};gatewayDiagnostic();({svg:document.nodes.filter(n=>n.tag==="svg").length,blocked:main.textContent.includes("尚无可解释绩效")})')
        self.assertEqual(result,{'svg':0,'blocked':True})
    def test_table_pagination_and_filter(self):
        result=self.js('let t=perfTable("合成表",[{label:"证券",render:r=>r.symbol}],Array.from({length:25},(_,i)=>({symbol:i<13?"A":"B"})));let next=document.nodes.find(n=>n.tag==="button"&&n.textContent==="下一页");next.events.click();let second=t.textContent.includes("第 2/3 页");let filter=document.nodes.find(n=>n.tag==="select");filter.value="B";filter.events.change();({second,filtered:t.textContent.includes("共 12 条 · 第 1/1 页"),nextDisabled:next.disabled})')
        self.assertEqual(result,{'second':True,'filtered':True,'nextDisabled':True})
