'use strict';
const $=id=>document.getElementById(id), form=$('inputs');
let generation=0, selection=0, analysis=null, analysisId=null, nminus=null, nminusPending=null;
const duration=v=>typeof v==='number'?`${Math.floor(v/60)}:${String(Math.round(v%60)).padStart(2,'0')}`:'—';
const clock=v=>v?v.slice(11,19):'—';
const scenario=()=>$('scenario').value;
function text(tag,value,parent,cls){
  const node=document.createElement(tag); node.textContent=value;
  if(cls)node.className=cls; parent.append(node); return node;
}
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
async function api(path,data){
  const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});
  const value=await response.json();if(!response.ok)throw new Error(value.message||'Anropsfel');return value;
}
async function resolveJob(value,valid){
  while(value.job_id){
    await new Promise(resolve=>setTimeout(resolve,500));if(!valid())return null;
    const job=await api('/api/jobs/'+value.job_id);
    if(job.status==='ERROR')throw new Error(job.message);if(job.status==='DONE')return job.result;
  }return value;
}
function clearTrip(){selection++;$('trip').hidden=true;$('legs').replaceChildren();$('trip-summary').replaceChildren();$('detail-status').textContent='';window.ReviewMap.clear();}
function invalidate(){
  generation++;clearTrip();analysis=null;analysisId=null;nminus=null;nminusPending=null;
  $('scenario').value='base';$('results').hidden=true;
  status('Indata ändrade – kör analysen för att granska den nya resan.');
}
form.addEventListener('input',invalidate);
function fill(request){for(const[key,value]of Object.entries(request))form.elements.namedItem(key).value=value;}
function read(){const request=Object.fromEntries(new FormData(form));for(const key of ['from_lat','from_lon','to_lat','to_lon','window_minutes'])request[key]=Number(request[key]);return request;}
async function run(request,presetId){
  invalidate();const token=generation;status('Läser analys…');
  try{
    let value=presetId?await api('/api/results/'+presetId):await api('/api/analyze',request);
    value=await resolveJob(value,()=>token===generation);if(token!==generation||!value)return;
    if(value.status!=='OK')throw new Error(value.status+': '+value.message);
    analysis=value.report;analysisId=value.analysis_id;render();
    status('Verifierad basanalys · '+analysis.minute_observations.length+' startminuter');
    selectMinute(analysis.departure_jumps[0]?.before_index??0);
  }catch(error){if(token===generation)status(error.message,true);}
}
form.addEventListener('submit',event=>{event.preventDefault();run(read());});
function metric(parent,label,value){const node=text('div','',parent,'metric');text('span',label,node);text('strong',value,node);}
function render(){
  const params=analysis.metadata.parameters,m=analysis.metrics;$('results').hidden=false;
  $('relation').textContent=`${params.origin.name} → ${params.destination.name} · ${analysis.metadata.date}`;
  $('metrics').replaceChildren();
  for(const p of ['T50','T90','T99'])metric($('metrics'),p+'_schedule',typeof m.percentiles_seconds[p]==='number'?duration(m.percentiles_seconds[p]):'Ej nåbar');
  for(const[label,key]of [['buffer_90','buffer_90'],['buffer_99','buffer_99'],['Full range','full_range']])metric($('metrics'),label,typeof m[key]==='number'?duration(m[key]):'Ej nåbar');
  metric($('metrics'),'Route coverage',(m.route_coverage*100).toFixed(1)+' %');metric($('metrics'),'Ej nåbara minuter',m.unreachable_count);
  $('minute').replaceChildren();analysis.minute_observations.forEach((row,index)=>{
    const node=text('option',clock(row.start)+' · bas '+(row.duration_seconds===null?'Ej nåbar':duration(row.duration_seconds)),$('minute'));node.value=index;
  });
  $('nminus-summary').hidden=true;$('nminus-notice').hidden=true;$('nminus-status').textContent='';drawCurve();$('jumps').replaceChildren();
  for(const jump of analysis.departure_jumps)for(const[label,index]of [['före',jump.before_index],['efter',jump.after_index]]){
    const button=text('button',`Bashopp ${jump.rank} ${label}: ${clock(analysis.minute_observations[index].start)} (+${duration(jump.increase_seconds)})`,$('jumps'),'jump');button.addEventListener('click',()=>selectMinute(index));
  }
  $('combinations').replaceChildren();for(const c of analysis.combinations){
    const node=text('div','',$('combinations'),'combo');text('span',c.rides.map(r=>r.line).join(' → ')||'Gång',node);
    text('strong',`${(c.share_reachable_minutes*100).toFixed(1)} % · ${c.count} minuter · ${c.transfers} byten`,node);
  }
}
async function ensureNMinus(){
  if(nminus)return nminus;if(nminusPending)return nminusPending;
  const gen=generation,id=analysisId;$('nminus-status').textContent='Beräknar separata N−1-scenarier…';
  const pending=(async()=>{
    let value=await api('/api/nminus',{analysis_id:id});value=await resolveJob(value,()=>gen===generation&&id===analysisId);
    if(!value||gen!==generation||id!==analysisId)return null;
    if(value.status!=='OK'||value.analysis_id!==id)throw new Error(value.message||'N−1 kunde inte verifieras.');
    nminus=value;$('nminus-status').textContent='N−1 verifierad · 120 min sökhorisont efter besked';return value;
  })();nminusPending=pending;
  try{return await pending;}finally{if(nminusPending===pending)nminusPending=null;}
}
async function scenarioChanged(){
  if(!analysis)return;clearTrip();const gen=generation,key=scenario();$('nminus-status').classList.remove('error');
  try{
    if(key!=='base')await ensureNMinus();if(gen!==generation||key!==scenario())return;
    renderScenarioSummary();drawCurve();selectMinute(Number($('minute').value));
  }catch(error){if(gen===generation){$('nminus-status').textContent=error.message;$('nminus-status').classList.add('error');}}
}
$('scenario').addEventListener('change',scenarioChanged);
function renderScenarioSummary(){
  const key=scenario(),visible=key!=='base'&&nminus;$('nminus-summary').hidden=!visible;$('nminus-notice').hidden=!visible;if(!visible)return;
  const s=nminus.summaries[key];$('nminus-metrics').replaceChildren();$('nminus-heading').textContent=`Ben ${key} uteblir${s.conditional?' · kvantiler villkorade på nåbarhet':''}`;
  for(const p of ['T50','T90','T99'])metric($('nminus-metrics'),p+' total',duration(s.total_percentiles_seconds[p]));
  for(const p of ['P50','P90'])metric($('nminus-metrics'),p+' extra',duration(s.extra_percentiles_seconds[p]));
  metric($('nminus-metrics'),'Max extra',duration(s.maximum_extra_seconds));
  metric($('nminus-metrics'),'Täckning',s.coverage===null?'Ej tillämpligt':(s.coverage*100).toFixed(1)+' %');metric($('nminus-metrics'),'Ej nåbara',s.unreachable_count);
  $('nminus-population').textContent=`${s.applicable_count} tillämpliga · ${s.not_applicable_count} ej tillämpliga · ${s.reachable_count} nåbara. Kvantiler över nåbara, tillämpliga scenarier; varje minut har lika vikt.`;
}
function svgNode(tag,attrs,parent){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,value);parent.append(node);return node;}
function drawCurve(){
  const svg=$('curve');svg.replaceChildren();const rows=analysis.minute_observations,key=scenario(),scenarios=nminus&&key!=='base'?nminus.scenarios[key]:null;
  const values=rows.map(r=>r.duration_seconds).concat(scenarios?scenarios.map(r=>r.total_seconds??null):[]).filter(v=>typeof v==='number');
  const high=Math.max(300,Math.ceil(Math.max(...values,0)/600)*600),x=i=>65+i*865/Math.max(rows.length-1,1),y=v=>230-v*200/high;
  for(let v=0;v<=high;v+=high>3600?900:600){svgNode('line',{x1:65,x2:930,y1:y(v),y2:y(v),stroke:'#e1e9ec'},svg);svgNode('text',{x:6,y:y(v)+4},svg).textContent=duration(v);}
  svgNode('text',{x:8,y:15},svg).textContent='Total restid (min:s)';const jumps=new Set(analysis.departure_jumps.flatMap(j=>[j.before_index,j.after_index]));
  function series(data,color,isScenario){data.forEach((row,i)=>{
    const value=isScenario?row.total_seconds:row.duration_seconds,previous=i?(isScenario?data[i-1].total_seconds:data[i-1].duration_seconds):null;
    if(typeof value==='number'&&typeof previous==='number')svgNode('line',{x1:x(i-1),y1:y(previous),x2:x(i),y2:y(value),stroke:color,'stroke-width':2},svg);
    const missing=typeof value!=='number';
    const node=svgNode('circle',{cx:x(i),cy:missing?245:y(value),r:5,fill:row.status==='NOT_APPLICABLE'?'white':missing?'#a63b30':!isScenario&&jumps.has(i)?'#c94d37':color,stroke:missing?'#888':color,tabindex:0,'data-minute':i,'data-series':isScenario?'nminus':'base'},svg);
    const label=clock(rows[i].start)+' · '+(row.status==='NOT_APPLICABLE'?'Ej tillämpligt':missing?'Ej nåbar':duration(value));node.setAttribute('aria-label',label);svgNode('title',{},node).textContent=label;
    node.addEventListener('click',()=>selectMinute(i));node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' ')selectMinute(i);});
  });}
  series(rows,'#277e97',false);if(scenarios)series(scenarios,'#9a47b5',true);
  rows.forEach((row,i)=>{if(i%10===0||i===rows.length-1)svgNode('text',{x:x(i)-18,y:264},svg).textContent=clock(row.start).slice(0,5);});
}
$('minute').addEventListener('change',()=>selectMinute(Number($('minute').value)));
async function selectMinute(index){
  if(!analysis)return;clearTrip();const token=selection,gen=generation,id=analysisId,key=scenario();$('minute').value=index;
  $('detail-status').classList.remove('error');$('detail-status').textContent='Hämtar resa '+clock(analysis.minute_observations[index].start)+'…';
  try{
    if(key!=='base'){
      const data=await ensureNMinus();if(!data||token!==selection||gen!==generation||key!==scenario())return;showScenario(data.scenarios[key][index],index);return;
    }
    let result=await api('/api/detail',{analysis_id:id,index});result=await resolveJob(result,()=>token===selection&&gen===generation);
    if(!result||token!==selection||gen!==generation)return;if(result.analysis_id!==id||result.index!==index)throw new Error('Resans identitet matchar inte valet.');
    if(result.status!=='OK')throw new Error(result.message||result.status);if(!result.itinerary.matches_sweep||!result.itinerary.best_r5_option)throw new Error('Resan matchar inte sweepen.');
    $('detail-status').textContent=`${clock(analysis.minute_observations[index].start)} · ${result.source==='saved'?'sparad detaljresa':result.source==='cache'?'cachelagrad detaljresa':'hämtad via motor'} · ${result.itinerary.options.length-1} upptäckta alternativ utöver vald resa`;
    showBase(result.itinerary.best_r5_option,index);
  }catch(error){if(token===selection&&gen===generation){$('detail-status').textContent=error.message;$('detail-status').classList.add('error');}}
}
function legList(segments,parent,phase){for(const leg of segments){
  const node=text('li','',parent);text('small',phase,node,'phase');
  text('strong',`${clock(leg.departure)}–${clock(leg.arrival)} · ${leg.mode==='WALK'?'Gång':leg.mode+' '+leg.line}`,node);
  text('div',`${leg.start_stop_name||'Start'} → ${leg.end_stop_name||'Mål'}`,node);
  if(leg.start_stop||leg.end_stop)text('small',`Hållplats-ID: ${leg.start_stop||'anropspunkt'} → ${leg.end_stop||'anropspunkt'}`,node);
  text('small',`Restid ${duration(leg.travel_seconds)} · väntan ${duration(leg.wait_seconds)}${leg.fixed_slack_seconds?' · slutmarginal '+duration(leg.fixed_slack_seconds):''}`,node);
  if(leg.mode!=='WALK')text('small',`Boarding-/bytesmarginal ${duration(leg.wait_seconds)} · krav >1:00`,node);
  if(leg.geometry_connectors_m&&Object.values(leg.geometry_connectors_m).some(v=>v>1))text('small','Orange anslutning är approximativ; fysisk framkomlighet är inte verifierad.',node);
}}
function showBase(option,index){
  const obs=analysis.minute_observations[index];$('trip-title').textContent='Basresa · '+clock(obs.start);
  const summary=text('div','',$('trip-summary'),'summary');
  for(const value of [`Totalt ${duration(option.duration_seconds)}`,`Gång ${duration(option.walking_seconds)}`,`Väntan ${duration(option.waiting_seconds)}`,`${option.transfers} byten`,`Ankomst ${clock(option.segments.at(-1).arrival)}`])text('strong',value,summary);
  legList(option.segments,$('legs'),'Basresa');$('trip').hidden=false;
  window.ReviewMap.render({base:option.segments,completed:[],reserve:[],origin:analysis.metadata.parameters.origin,destination:analysis.metadata.parameters.destination});
}
function showScenario(row,index){
  const start=analysis.minute_observations[index].start,base=nminus.base_itineraries[index]||[];
  $('trip-title').textContent=`N−1 ben ${scenario()} · start ${clock(start)}`;
  if(row.status==='NOT_APPLICABLE'){
    $('detail-status').textContent='Ej tillämpligt · '+(row.reason==='BASE_UNREACHABLE'?'basresan är ej nåbar':'basresan saknar detta trafikben');
    text('p','Detta är inte ett misslyckat scenario och ingår inte i scenariots kvantiler.',$('trip-summary'));legList(base,$('legs'),'Basresa · inget sådant felscenario');
  }else{
    $('detail-status').textContent=row.status==='REACHABLE'?'Verifierad reservresa från beskedshållplatsen':'Ej nåbar inom 120 min efter besked';
    const summary=text('div','',$('trip-summary'),'summary');
    text('strong',row.status==='REACHABLE'?`Totalt ${duration(row.total_seconds)} · extra ${duration(row.extra_seconds)} · ankomst ${clock(row.reserve.segments.at(-1).arrival)}`:'Ingen användbar reservresa inom sökhorisonten.',summary);
    text('p',`Utebliven linje ${row.failed_leg.line} · besked ${clock(row.notification.time)} vid ${row.notification.stop_name}.`,$('trip-summary'),'failure');
    text('small',`Tur: ${row.failed_instance.trip_id} · feed ${row.failed_instance.feed} · trafikdag ${row.failed_instance.service_date}`,$('trip-summary'));
    text('p',`Genomförd tid ${duration(row.completed.elapsed_seconds)}, gång ${duration(row.completed.walking_seconds)}, ${row.completed.transit_legs} trafikben. Väntan före besked ${duration(row.completed.wait_before_notification_seconds)}.`,$('trip-summary'));
    text('p',`Återstående gångbudget ${duration(row.remaining_parameters.max_walk_seconds)} · ${row.remaining_parameters.max_rides} trafikben · sista möjliga ankomst ${clock(row.search_end)}.`,$('trip-summary'),'muted');
    legList(row.completed.segments,$('legs'),'Genomförd del');text('li',`Besked ${clock(row.notification.time)}: vald tur uteblir. Omplaneringen börjar här.`,$('legs'),'failure');legList(row.reserve.segments,$('legs'),'Reservresa');
  }
  $('trip').hidden=false;
  window.ReviewMap.render({base,completed:row.completed?.segments||[],reserve:row.reserve?.segments||[],notification:row.notification,origin:analysis.metadata.parameters.origin,destination:analysis.metadata.parameters.destination});
}
$('map-reset').addEventListener('click',()=>window.ReviewMap.reset());
api('/api/presets').then(value=>{
  const p=value.parameters;$('parameters').textContent=`Gång ${p.walk_speed_kmh} km/h · högst ${p.max_walk_seconds/60} min gång totalt · basresa högst ${p.max_time_seconds/60} min · högst ${p.max_rides} trafikben · boarding >${p.board_slack_seconds} s · slutmarginal ${p.egress_slack_seconds} s`;
  for(const preset of value.presets){const button=text('button',preset.label,$('presets'));button.addEventListener('click',()=>{fill(preset.request);run(preset.request,preset.id);});}
  if(value.presets.length){fill(value.presets[0].request);run(value.presets[0].request,value.presets[0].id);}else status('Ange koordinater och kör analys.');
}).catch(error=>status(error.message,true));
