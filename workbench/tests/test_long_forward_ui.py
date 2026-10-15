"""Synthetic-only rendering for new independent historical/forward sections."""
import json
import subprocess
import unittest
from workbench.tests.test_performance_ui import BOOT, NODE, ROOT

class LongForwardUITests(unittest.TestCase):
    def js(self,expression):
        code=BOOT+'\nconsole.log(JSON.stringify(vm.runInContext('+json.dumps(expression)+',context)));'
        r=subprocess.run([NODE,'-e',code],cwd=ROOT,capture_output=True,text=True,check=True)
        return json.loads(r.stdout)
    def test_no_registered_outputs_stay_unrun(self):
        r=self.js('state.long_forward={status:"VERIFIED",history:null,forward:null};longForwardView();({history:main.textContent.includes("尚无已登记的历史运行"),forward:main.textContent.includes("尚未登记可核验的前向产物"),zero:main.textContent.includes("¥0.00")})')
        self.assertEqual(r,{'history':True,'forward':True,'zero':False})
    def test_integrity_error_has_no_false_performance(self):
        r=self.js('state.long_forward={status:"INTEGRITY_ERROR",reason:"SYNTHETIC_CHANGED"};longForwardView();({error:main.textContent.includes("产物完整性校验失败"),charts:document.nodes.filter(n=>n.tag==="svg").length})')
        self.assertEqual(r,{'error':True,'charts':0})
    def test_history_data_blocked_not_run_no_trades(self):
        r=self.js('longHistoryView({run_id:"SYNTHETIC",status:"DATA_BLOCKED",engine_called:false,window:{first_session:"2021-10-01"},errors:["SYNTHETIC_MISSING"]});({error:main.textContent.includes("SYNTHETIC_MISSING"),distinction:main.textContent.includes("不是运行后无交易"),zero:main.textContent.includes("0.00%")})')
        self.assertEqual(r,{'error':True,'distinction':True,'zero':False})
    def test_yearly_money_and_fraction_units(self):
        r=self.js('longHistoryView({run_id:"SYNTHETIC",status:"RUN_NO_TRADES",engine_called:true,overall:{initial_cash_cents:100000,final_nav_cents:105000,net_profit_cents:5000,net_return_fraction:"0.05",max_drawdown_fraction:"0.1",complete_trades:0,filled_orders:0},yearly:[{year:2025,first_session:"2025-01-02",last_session:"2025-12-31",net_return_fraction:"0.05",max_drawdown_fraction:"0.1",filled_orders:0,fees_cents:0}],controls:[],exposure:{average_exposure_fraction:"0",maximum_exposure_fraction:"0",exposed_sessions:0,terminal_cash_cents:105000}});({money:main.textContent.includes("¥1,050.00"),pct:main.textContent.includes("5.00%"),year:main.textContent.includes("2025-01-02 → 2025-12-31"),noTrades:main.textContent.includes("引擎运行完成，无成交")})')
        self.assertEqual(r,{'money':True,'pct':True,'year':True,'noTrades':True})
    def test_forward_missed_does_not_create_plan(self):
        r=self.js('longForwardAView({strategy_a:{status:"MISSED",activation:null,plan:null,settlements:[],observed_sessions:0,next_execution:null},strategy_b:{status:"BLOCKED",module:"SYNTHETIC_B",reason:"缺失原件"}});({missed:main.textContent.includes("错过冻结或执行条件"),noPlan:main.textContent.includes("尚无已验证的冻结计划"),blocked:main.textContent.includes("缺失原件")})')
        self.assertEqual(r,{'missed':True,'noPlan':True,'blocked':True})
    def test_forward_frozen_plan_not_simulated_fill(self):
        r=self.js('longForwardAView({strategy_a:{status:"PLAN_FROZEN",activation:"SYNTHETIC",observed_sessions:0,settlements:[],plan:{run_id:"SYNTHETIC",source_session:"2026-01-01",frozen_at:"2026-01-02T12:00:00+08:00",execution_session:"2026-01-05",bootstrap:true,bootstrap_skipped_sessions:["2026-01-02"],pending_buys:[{symbol:"SYNTHETIC"}],pending_sells:{}}},strategy_b:{status:"BLOCKED"}});({frozen:main.textContent.includes("计划已冻结，等待执行"),nonFill:main.textContent.includes("冻结买入计划（非成交）"),future:main.textContent.includes("2026-01-05"),noDays:main.textContent.includes("不计为真实前向天数")})')
        self.assertEqual(r,{'frozen':True,'nonFill':True,'future':True,'noDays':True})
