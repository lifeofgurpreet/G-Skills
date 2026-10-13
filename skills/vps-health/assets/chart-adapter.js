/* G-Skills observation-preserving adapter. No fetches, interpolation or policy writes. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();else root.VpsCharts=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const fields=['value','execution','pressure','cfs'];
  const pct=v=>finite(v)?(100*v).toFixed(1)+'%':'Unmeasured';
  function prepare(history){
    const data=[[],[],[],[],[]],indices=[];let prior=null;
    for(let i=0;i<history.length;i++){
      const p=history[i];if(!p||!finite(p.t)||prior&&p.t<=prior.t)throw new Error('Non-increasing chart time');
      const cut=fields.map(k=>Boolean(p.breaks?p.breaks[k]:p.break_before));
      if(prior&&cut.some(Boolean)){
        data[0].push(prior.t+(p.t-prior.t)/2);indices.push(-1);
        // uPlot null = explicit gap; undefined = alignment-only, not a sample.
        fields.forEach((k,j)=>data[j+1].push(cut[j]?null:undefined));
      }
      data[0].push(p.t);indices.push(i);
      fields.forEach((k,j)=>{const v=p[k];if(v!==undefined&&v!==null&&(!finite(v)||v<0||v>1.02))throw new Error('Invalid chart ratio');data[j+1].push(p.quality?null:(finite(v)?v:null));});
      prior=p;
    }
    return {data,indices};
  }
  function csv(history,start,end){
    const lines=['observed_utc,accounted_ratio,executing_ratio,cpu_pressure_ratio,throttled_periods_ratio,accounting_unknown'];
    for(const p of history){if(p.t<start||p.t>end)continue;lines.push([new Date(p.t*1000).toISOString(),...fields.map(k=>p.quality||!finite(p[k])?'':String(p[k])),String(Boolean(p.quality))].join(','));}
    return lines.join('\n')+'\n';
  }
  function mount(targets,callbacks={}){
    if(typeof uPlot!=='function')throw new Error('Bundled chart engine unavailable');
    let ready=false,updating=false,bundle=prepare([]),history=[],windowBounds=null,full=[0,1],node='';
    const colors={ink:'#27312a',execution:'#687ea0',pressure:'#887254',cfs:'#625a76',grid:'#e6e7e2',text:'#626760'};
    const sync='vps-'+Math.random().toString(36).slice(2);
    function cursor(plot){if(!ready||updating)return;const index=plot.cursor.idx;if(index!==null&&index!==undefined&&bundle.indices[index]>=0)callbacks.inspect?.(bundle.indices[index]);else if(index!==null&&index!==undefined)callbacks.gap?.(bundle.data[0][index]);}
    const axis={stroke:colors.text,font:'10px ui-monospace, monospace',grid:{stroke:colors.grid,width:1},ticks:{show:false},gap:8};
    const yAxis={...axis,size:39,values:(u,splits)=>splits.map(v=>Math.round(v*100)+'%')};
    function changed(plot,key){if(!ready||updating||key!=='x')return;const {min,max}=plot.scales.x;if(!finite(min)||!finite(max)||max<=min)return;if(windowBounds&&Math.abs(min-windowBounds[0])<.001&&Math.abs(max-windowBounds[1])<.001)return;const start=Math.max(full[0],min),end=Math.min(full[1],max);if(end<=start)return;setWindow(start,end);callbacks.window?.(windowBounds);}
    function options(target,height,context=false){
      return {width:Math.max(240,Math.round(target.clientWidth)),height,pxAlign:0,legend:{show:false},padding:[12,12,0,0],
        scales:{x:{time:true},y:{auto:false,range:[0,1.05]}},tzDate:ts=>uPlot.tzDate(new Date(ts*1000),'UTC'),
        axes:[{...axis,size:30,space:90,grid:{show:false},values:(u,values)=>values.map(t=>{const d=new Date(t*1000);return u.scales.x.max-u.scales.x.min>86400?d.toISOString().slice(5,10):d.toISOString().slice(11,16);})},yAxis],
        cursor:{drag:{x:true,y:false,setScale:true},sync:{key:sync,scales:['x',null]},points:{size:6}},select:{show:true},
        series:[{},...(context?[
          {label:'CPU pressure',stroke:colors.pressure,width:1.6,dash:[4,3],spanGaps:false,points:{show:false}},
          {label:'Throttled periods',stroke:colors.cfs,width:1.6,dash:[2,3],spanGaps:false,points:{show:false}}
        ]:[
          {label:'Accounted time',stroke:colors.ink,width:2,spanGaps:false,points:{show:false}},
          {label:'Recorded execution',stroke:colors.execution,width:1.4,dash:[5,3],spanGaps:false,points:{show:false}},
          {label:'Tolerance reference',stroke:'#b1b6aa',width:1,dash:[3,5],spanGaps:true,points:{show:false}}
        ])],hooks:{setCursor:[cursor],setScale:[changed]}};
    }
    const top=new uPlot(options(targets.top,235),[[],[],[],[]],targets.top);
    const lower=new uPlot(options(targets.lower,126,true),[[],[],[]],targets.lower);const all=[top,lower];ready=true;
    for(const [i,plot] of all.entries()){
      plot.root.setAttribute('role','img');plot.root.dataset.chartEngine='uPlot';plot.root.dataset.chartVersion='1.6.32';
      plot.root.setAttribute('aria-label',i?'Workload pressure and throttled-period history. Use the sample inspector or observation table for exact values.':'Accounting and recorded execution history. Drag to inspect a time range, or use time buttons and keyboard sample controls.');
    }
    function setWindow(start,end){if(!finite(start)||!finite(end)||end<=start)throw new Error('Invalid chart window');windowBounds=[start,end];updating=true;for(const plot of all)plot.setScale('x',{min:start,max:end});updating=false;}
    function update(next,range,policy,id){history=next;bundle=prepare(next);full=range;node=id;const [xs,values,exec,pressure,cfs]=bundle.data;updating=true;top.setData([xs,values,exec,xs.map(()=>policy.acceptable_ratio)],false);lower.setData([xs,pressure,cfs],false);updating=false;setWindow(...(windowBounds||full));return bundle;}
    function inspect(index){const p=history[index];if(!p)return;updating=true;for(const plot of all)plot.setCursor({left:plot.valToPos(p.t,'x'),top:plot.valToPos(p.value||0,'y')},false);updating=false;}
    function size(){for(const [i,plot] of all.entries())plot.setSize({width:Math.max(240,Math.round((i?targets.lower:targets.top).clientWidth)),height:i?126:(innerWidth<650?210:235)});}
    function toggle(field,show){const i=fields.indexOf(field);if(i<0)throw new Error('Unknown chart channel');(i<2?top:lower).setSeries(i<2?i+1:i-1,{show});}
    function destroy(){ready=false;for(const plot of all)plot.destroy();}
    function exportPng(){
      const c=document.createElement('canvas'),width=Math.max(top.ctx.canvas.width,lower.ctx.canvas.width),ratio=devicePixelRatio||1,gap=55*ratio,heading=55*ratio;
      c.width=width;c.height=top.ctx.canvas.height+lower.ctx.canvas.height+gap+heading;
      const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle=colors.ink;ctx.font=`${13*ratio}px sans-serif`;ctx.fillText('VPS Health · '+node,12*ratio,22*ratio);ctx.font=`${9*ratio}px sans-serif`;ctx.fillText('Accounting / recorded execution · display only; not a provider verdict',12*ratio,40*ratio);
      ctx.drawImage(top.ctx.canvas,0,heading);ctx.fillText('CPU pressure / throttled periods · missing remains unknown',12*ratio,heading+top.ctx.canvas.height+30*ratio);ctx.drawImage(lower.ctx.canvas,0,heading+top.ctx.canvas.height+gap);return c.toDataURL('image/png');
    }
    return {update,setWindow,inspect,size,toggle,destroy,exportPng,getWindow:()=>windowBounds,getPrepared:()=>bundle};
  }
  return {prepare,csv,mount,pct,version:'1.6.32'};
});
