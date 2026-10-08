import test from 'node:test';import assert from 'node:assert/strict';
import {load,transition,execute,exportCloud} from '../display.mjs';
for(const name of ['Actual-Collector-Readiness.json','Snapshot-B-Readiness.json','Forward-Paper-Readiness.json','Owner-Activation-Report.json','Historical-PIT-Three-Symbol-Matrix.json','Historical-PIT-Closure-Progress.json']){
 test(`${name}: readiness is not native authority`,()=>{const x=load(name);assert.equal(x.body.actual_forward_days,0);assert.equal(x.body.productionGate,false);assert.equal(transition(x,'LOCAL_READINESS_DISPLAY'),x);assert.throws(()=>transition(x,'OrderIntent'));});}
test('copied display cannot promote',()=>{assert.throws(()=>transition({...load('Owner-Activation-Report.json')},'LOCAL_READINESS_DISPLAY'));});
test('native Signal cannot load',()=>assert.throws(()=>load('SignalEvent.json')));
test('capture display cannot execute',()=>assert.throws(()=>execute(load('Actual-Collector-Readiness.json'))));
test('Forward display cannot execute trade',()=>assert.throws(()=>execute(load('Forward-Paper-Readiness.json'))));
test('cloud export remains blocked',()=>assert.throws(()=>exportCloud(load('Owner-Activation-Report.json'))));
test('nested displayed actual count cannot be forged',()=>{const x=load('Actual-Collector-Readiness.json');assert.throws(()=>{x.body.body.actual_forward_days=99;});assert.equal(x.body.body.actual_forward_days,0);assert.equal(transition(x,'LOCAL_READINESS_DISPLAY'),x);});
