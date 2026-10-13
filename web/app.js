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
async function resolveJob(value,valid,onProgress){
  while(value.job_id){
    await new Promise(resolve=>setTimeout(resolve,500));if(!valid())return null;
    const job=await api('/api/jobs/'+value.job_id);
    if(!valid())return null;
    if(job.message&&onProgress)onProgress(job.message);
    if(job.status==='ERROR')throw new Error(job.message);if(job.status==='DONE')return job.result;
  }return value;
}
function clearTrip(){selection++;$('trip').hidden=true;$('legs').replaceChildren();$('trip-summary').replaceChildren();$('detail-status').textContent='';window.ReviewMap.clear();}
function invalidate(){
  generation++;clearTrip();analysis=null;analysisId=null;nminus=null;nminusPending=null;
  $('scenario').value='base';$('results').hidden=true;
  $('deadline-results').hidden=true;$('deadline-choices').replaceChildren();
  $('parameters').textContent=`Gång ${form.elements.walk_speed_kmh.value} km/h · högst ${form.elements.max_walk_minutes.value} min gång totalt · ny basanalys högst 120 min · högst ${form.elements.max_rides.value} trafikben · boarding >60 s · reservhorisont 120 min efter besked`;
  syncPicker();
  status('Indata ändrade – kör analysen för att granska den nya resan.');
}
form.addEventListener('input',invalidate);
function fill(request){for(const[key,value]of Object.entries(request)){const input=form.elements.namedItem(key);if(input)input.value=value;}syncPicker();}
function syncPicker(){
  window.ReviewMap.setPickerPoints(['from','to'].map(endpoint=>({endpoint,lat:parseFloat(form.elements.namedItem(endpoint+'_lat').value),lon:parseFloat(form.elements.namedItem(endpoint+'_lon').value)})));
}
function read(){const request=Object.fromEntries(new FormData(form));delete request.analysis_mode;delete request.deadline;for(const key of ['from_lat','from_lon','to_lat','to_lon','window_minutes','max_rides','walk_speed_kmh','max_walk_minutes'])request[key]=Number(request[key]);request.max_time_minutes=120;return request;}
form.elements.analysis_mode.addEventListener('change',()=>{$('deadline-label').hidden=form.elements.analysis_mode.value!=='deadline';});
$('open-picker').addEventListener('click',()=>window.ReviewMap.pick((endpoint,lat,lon)=>{
  form.elements.namedItem(endpoint+'_lat').value=lat.toFixed(6);form.elements.namedItem(endpoint+'_lon').value=lon.toFixed(6);
  form.elements.namedItem(endpoint+'_name').value=endpoint==='from'?'A':'B';
  invalidate();$('pick-status').textContent=`${endpoint==='from'?'A':'B'}: ${lat.toFixed(6)}, ${lon.toFixed(6)}. Kör analysen med de nya punkterna.`;
}));
async function run(request,presetId){
  invalidate();const token=generation;status('Läser analys…');
  try{
    let value=presetId?await api('/api/results/'+presetId):await api('/api/analyze',request);
    value=await resolveJob(value,()=>token===generation,message=>status(message));if(token!==generation||!value)return;
    if(value.status!=='OK')throw new Error(value.status+': '+(value.message||'Analysen kunde inte verifieras. Se den lokala körloggen.'));
    analysis=value.report;analysisId=value.analysis_id;render();
    status('Verifierad basanalys · '+analysis.minute_observations.length+' startminuter'+(analysis.metrics.route_coverage===0?' · Ingen resa inom analysens gränser för restid, gång och trafikben.':''));
    selectMinute(analysis.departure_jumps[0]?.before_index??0);
    if(form.elements.analysis_mode.value==='deadline')runDeadline(token);
  }catch(error){if(token===generation)status(error.message,true);}
}
form.addEventListener('submit',event=>{event.preventDefault();run(read());});
function metric(parent,label,value){const node=text('div','',parent,'metric');text('span',label,node);text('strong',value,node);}
function render(){
  const params=analysis.metadata.parameters,m=analysis.metrics;$('results').hidden=false;
  $('relation').textContent=`${params.origin.name} → ${params.destination.name} · ${analysis.metadata.date}`;
  $('parameters').textContent=`Gång ${params.walk_speed_kmh} km/h · högst ${params.max_walk_seconds/60} min gång totalt · basresa högst ${params.max_time_seconds/60} min · högst ${params.max_rides} trafikben · boarding >${params.board_slack_seconds} s · reservhorisont 120 min efter besked`;
  $('scenario').replaceChildren();
  for(const[value,label]of [['base','Basfall'],['combined','Samlat N−1: värsta enskilda bortfall'],...Array.from({length:params.max_rides},(_,i)=>[String(i+1),`Ben ${i+1} uteblir`])]){
    const node=text('option',label,$('scenario'));node.value=value;
  }
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
  $('nminus-metrics').replaceChildren();
  if(key==='combined'){
    const s=nminus.combined.summary;$('nminus-heading').textContent='Samlat N−1 över varje startminut';
    for(const p of ['T50','T90','T99'])metric($('nminus-metrics'),p,typeof s.percentiles_seconds[p]==='number'?duration(s.percentiles_seconds[p]):'Ej nåbar');
    metric($('nminus-metrics'),'Alla bortfall har reserv',(s.all_failures_covered_share*100).toFixed(1)+' %');
    metric($('nminus-metrics'),'Ej nåbara minuter',s.unreachable_count);
    metric($('nminus-metrics'),'Utan trafikben',s.no_transit_leg_count);
    $('nminus-population').textContent='Största totalrestiden bland separata bortfall av den valda basresans trafikben. Ej nåbart räknas som +∞ i kvantilerna. Ren gång använder basrestiden. Basresan optimeras inte för robusthet.';return;
  }
  const s=nminus.summaries[key];$('nminus-heading').textContent=`Ben ${key} uteblir${s.conditional?' · kvantiler villkorade på nåbarhet':''}`;
  for(const p of ['T50','T90','T99'])metric($('nminus-metrics'),p+' total',duration(s.total_percentiles_seconds[p]));
  for(const p of ['P50','P90'])metric($('nminus-metrics'),p+' extra',duration(s.extra_percentiles_seconds[p]));
  metric($('nminus-metrics'),'Max extra',duration(s.maximum_extra_seconds));
  metric($('nminus-metrics'),'Täckning',s.coverage===null?'Ej tillämpligt':(s.coverage*100).toFixed(1)+' %');metric($('nminus-metrics'),'Ej nåbara',s.unreachable_count);
  $('nminus-population').textContent=`${s.applicable_count} tillämpliga · ${s.not_applicable_count} ej tillämpliga · ${s.reachable_count} nåbara. Kvantiler över nåbara, tillämpliga scenarier; varje minut har lika vikt.`;
}
function svgNode(tag,attrs,parent){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,value);parent.append(node);return node;}
function drawCurve(){
  const svg=$('curve');svg.replaceChildren();const rows=analysis.minute_observations,key=scenario(),scenarios=nminus&&key!=='base'?(key==='combined'?nminus.combined.minute_observations:nminus.scenarios[key]):null;
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
      const data=await ensureNMinus();if(!data||token!==selection||gen!==generation||key!==scenario())return;
      if(key==='combined'){
        const row=data.combined.minute_observations[index];
        if(row.status==='NO_TRANSIT_LEGS'){
          $('detail-status').textContent='Utan trafikben: inget turbortfall; samlat mått är basrestiden.';
          const base=data.base_itineraries[index];showBase({segments:base,duration_seconds:row.total_seconds,walking_seconds:row.total_seconds,waiting_seconds:0,transfers:0},index);return;
        }
        if(row.status==='BASE_UNREACHABLE')throw new Error('Basresan är ej nåbar; samlat N−1 är ej nåbart.');
        showScenario(data.scenarios[String(row.worst_leg)][index],index);return;
      }
      showScenario(data.scenarios[key][index],index);return;
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
  const connections=window.ReviewMap.connections(leg);
  if(connections.length){
    text('small',`Gångvägen är streckad i resans färg. Endast de korta anslutningarna är orange: ${connections.map(c=>c.label+' '+Math.round(c.meters)+' m').join(', ')}. Fysisk framkomlighet där är inte verifierad.`,node);
    const button=text('button','Visa orange anslutningar',node);
    button.type='button';button.setAttribute('aria-label',`Visa anslutningar: ${leg.start_stop_name} → ${leg.end_stop_name}`);
    button.addEventListener('click',()=>window.ReviewMap.focusConnections(leg));
  }
}}
function showBase(option,index){
  const obs=analysis.minute_observations[index];$('trip-title').textContent='Basresa · '+clock(obs.start);
  const summary=text('div','',$('trip-summary'),'summary');
  for(const value of [`Totalt ${duration(option.duration_seconds)}`,`Gång ${duration(option.walking_seconds)}`,`Väntan ${duration(option.waiting_seconds)}`,`${option.transfers} byten`,`Ankomst ${clock(option.segments.at(-1).arrival)}`])text('strong',value,summary);
  if(option.segments.every(leg=>leg.mode==='WALK'))text('p','Utan trafikben – inget turbortfall. Samlat N−1 använder basrestiden.',$('trip-summary'));
  legList(option.segments,$('legs'),'Basresa');$('trip').hidden=false;
  window.ReviewMap.render({base:option.segments,completed:[],reserve:[],origin:analysis.metadata.parameters.origin,destination:analysis.metadata.parameters.destination});
}
function showScenario(row,index){
  const start=analysis.minute_observations[index].start,base=nminus.base_itineraries[index]||[];
  $('trip-title').textContent=`N−1 ben ${row.leg_number||scenario()} · start ${clock(start)}`;
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
async function runDeadline(token){
  const id=analysisId;$('deadline-results').hidden=false;$('deadline-status').textContent='Prövar deadline för alla startminuter och enskilda bortfall…';
  try{
    let value=await api('/api/deadline',{analysis_id:id,deadline:form.elements.deadline.value});
    value=await resolveJob(value,()=>token===generation);if(!value||token!==generation||id!==analysisId)return;
    if(value.status!=='OK')throw new Error(value.message||value.status);
    $('deadline-choices').replaceChildren();$('deadline-status').textContent=`Deadline ${clock(value.deadline)} · ${value.start_minutes_checked} exakta startminuter prövade.`;
    for(const[key,label]of [['baseline','Basfall'],['all_single_failures','Varje enskilt turbortfall']]){
      const choice=value[key];if(!choice){text('p',label+': ingen startminut inom intervallet klarar kravet.',$('deadline-choices'));continue;}
      const button=text('button',`${label}: senaste start ${clock(choice.start)}, ankomst ${clock(choice.arrival)}`,$('deadline-choices'));
      button.addEventListener('click',async()=>{
        $('scenario').value=key==='baseline'?'base':'combined';$('minute').value=choice.index;await scenarioChanged();
      });
    }
  }catch(error){if(token===generation)$('deadline-status').textContent=error.message;}
}
api('/api/presets').then(value=>{
  const p=value.parameters;$('parameters').textContent=`Gång ${p.walk_speed_kmh} km/h · högst ${p.max_walk_seconds/60} min gång totalt · basresa högst ${p.max_time_seconds/60} min · högst ${p.max_rides} trafikben · boarding >${p.board_slack_seconds} s · slutmarginal ${p.egress_slack_seconds} s`;
  if(value.coverage){const format=v=>v.slice(0,4)+'-'+v.slice(4,6)+'-'+v.slice(6);$('coverage').textContent=`Fryst tidtabell: ${format(value.coverage.first)}–${format(value.coverage.last)}. OSM: lon 12.95–13.30, lat 55.60–55.80. Börja med 1–5 minuter; högst 120 minuter per anrop.`;}
  for(const preset of value.presets){const button=text('button',preset.label,$('presets'));button.addEventListener('click',()=>{fill(preset.request);run(preset.request,preset.id);});}
  if(value.presets.length&&generation===0){
    fill({...value.presets[0].request,walk_speed_kmh:p.walk_speed_kmh,max_walk_minutes:p.max_walk_seconds/60});
    if(value.presets[0].id)run(value.presets[0].request,value.presets[0].id);
    else status('Ange punkter eller välj ett förval och klicka Analysera. Börja med ett litet intervall.');
  }else if(generation===0)status('Ange koordinater och kör analys.');
}).catch(error=>status(error.message,true));
