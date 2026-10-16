/* Synthetic adapter contract. Node is a developer dependency, not a skill runtime. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const chart=require('../../../skills/vps-health/assets/chart-adapter.js');
function rows(){return Array.from({length:5},(_,i)=>({t:1800000000+i*300,value:.95,execution:.4,pressure:.02,cfs:0,quality:false,breaks:{value:false,execution:false,pressure:false,cfs:false}}));}
test('aligned channels retain exact values and original indices',()=>{const p=chart.prepare(rows());assert.equal(p.data.length,5);assert.deepEqual(p.indices,[0,1,2,3,4]);assert.deepEqual(p.data[2],[.4,.4,.4,.4,.4]);});
test('gap in one channel does not invent a measurement in others',()=>{const r=rows();r[2].breaks.pressure=true;const p=chart.prepare(r);assert.equal(p.indices[2],-1);assert.equal(p.data[3][2],null);assert.equal(p.data[1][2],undefined);assert.equal(p.data[2][2],undefined);assert.equal(p.data[0][2],1800000450);});
test('invalid interval remains null in every rendered series',()=>{const r=rows();r[2].quality=true;const p=chart.prepare(r);for(let i=1;i<=4;i++)assert.equal(p.data[i][2],null);});
test('missing context is null rather than zero',()=>{const r=rows();delete r[2].cfs;assert.equal(chart.prepare(r).data[4][2],null);});
test('time translation preserves y values and break alignment',()=>{const r=rows();r[2].breaks.execution=true;const a=chart.prepare(r),b=chart.prepare(r.map(p=>({...p,t:p.t+86400})));assert.deepEqual(b.data[0],a.data[0].map(t=>t+86400));assert.deepEqual(b.data.slice(1),a.data.slice(1));assert.deepEqual(b.indices,a.indices);});
test('caller data is not mutated',()=>{const r=rows();r[2].breaks.value=true;const before=structuredClone(r);chart.prepare(r);assert.deepEqual(r,before);});
test('invalid and repeated time fails before rendering',()=>{for(const value of [NaN,Infinity,null,1800000000]){const r=rows();r[1].t=value;assert.throws(()=>chart.prepare(r));}});
test('non-numeric ratios are refused',()=>{for(const value of ['0.98',true,Infinity,-.1,1.9]){const r=rows();r[1].execution=value;assert.throws(()=>chart.prepare(r));}});
test('CSV is bounded to the selected display window',()=>{const s=chart.csv(rows(),1800000300,1800000600).trim().split('\n');assert.equal(s.length,3);assert.ok(s[1].startsWith('2027-01-15T08:05:00.000Z'));assert.ok(!s.join('\n').includes('undefined'));});
test('CSV preserves unknown fields and never inserts synthetic midpoint rows',()=>{const r=rows();r[2].execution=null;r[2].breaks.pressure=true;const s=chart.csv(r,0,Infinity).trim().split('\n');assert.equal(s.length,6);assert.ok(s[3].includes('0.95,,0.02'));});
test('invalid observations have no apparent valid values in CSV',()=>{const r=rows();r[1].quality=true;assert.ok(chart.csv(r,0,Infinity).split('\n')[2].endsWith(',,,,,true'));});
test('empty data remains empty, not a healthy default',()=>{assert.deepEqual(chart.prepare([]),{data:[[],[],[],[],[]],indices:[]});assert.equal(chart.csv([],0,1).trim().split('\n').length,1);});

// One selected-skill UI acceptance entry, not another application runtime.
require('./test_workbench.cjs');

require('./test_time_view.cjs');
