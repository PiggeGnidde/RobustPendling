'use strict';
// Geometry/markers remain local and usable if either CDN or tile server fails.
window.ReviewMap=(()=>{
  const colors={base:'#277e97',completed:'#18754d',reserve:'#9a47b5'};
  let map=null,group=null,tiles=null,bounds=null,last=null,svgView=null,tileAdded=false,tileFailed=false;
  const $=id=>document.getElementById(id);
  const lines=leg=>leg.geometry.type==='LineString'?[leg.geometry.coordinates]:leg.geometry.coordinates;
  function connections(leg){
    const ls=lines(leg),lengths=leg.geometry_connectors_m||{},result=[];
    if(lengths.start>1)result.push({coordinates:ls[0].slice(0,2),label:'start',meters:lengths.start});
    if(lengths.end>1)result.push({coordinates:ls.at(-1).slice(-2),label:'mål',meters:lengths.end});
    for(const coordinates of leg.geometry.approximate_connections||[]){
      const [a,b]=coordinates,meters=Math.hypot((a[0]-b[0])*111320*Math.cos((a[1]+b[1])*Math.PI/360),(a[1]-b[1])*111320);
      if(meters>1)result.push({coordinates,label:'intern',meters});
    }return result;
  }
  function tooltip(value){const node=document.createElement('span');node.textContent=value;return node;}
  function marker(point,label,color,radius=5){
    return L.circleMarker([point[1],point[0]],{radius,color,weight:2,fillColor:'white',fillOpacity:1}).bindTooltip(tooltip(label)).addTo(group);
  }
  function drawLeaflet(data){
    $('map').hidden=false;$('map-fallback').hidden=true;
    if(!map){
      map=L.map('map',{attributionControl:true});group=L.featureGroup().addTo(map);
      const tileUrl=new URLSearchParams(location.search).has('tile-error')?'/missing-tiles/{z}/{x}/{y}.png':'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      tiles=L.tileLayer(tileUrl,{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',keepBuffer:0,updateWhenIdle:true});
      let errors=0,loaded=0;
      tiles.on('tileerror',()=>{errors++;tileFailed=true;$('map-status').textContent='Bakgrundskartan kunde inte laddas helt. Rutter och markörer fungerar ändå.';});
      tiles.on('tileload',()=>{loaded++;if(!errors)$('map-status').textContent='OpenStreetMap · rutter och markörer från den lokala analysen';});
      tiles.on('load',()=>{if(!loaded||errors)$('map-status').textContent='Bakgrundskartan kunde inte laddas helt. Rutter och markörer fungerar ändå.';});
      // No prefetch/offline scraping: add tile layer only when map is in view.
      const observer=new IntersectionObserver(entries=>{
        if(entries.some(e=>e.isIntersecting)){
          // Preserve user zoom and connection focus when scrolling back here.
          map.invalidateSize();
          if(!tileAdded){tiles.addTo(map);tileAdded=true;}
        }
      });observer.observe($('map'));
    }
    group.clearLayers();$('map-status').textContent=tileFailed?'Bakgrundskartan kunde inte laddas helt. Rutter och markörer fungerar ändå.':tileAdded?'OpenStreetMap · lokala rutter och markörer':'Bakgrundskartan laddas när kartan visas.';
    const overlays=[];
    for(const phase of ['base','completed','reserve']){
      let rides=0;
      for(const leg of data[phase]||[]){
        const walking=leg.mode==='WALK',color=colors[phase];
        for(const coords of lines(leg)){
          const width=walking?3:leg.mode==='RAIL'?7:5;
          const path=L.polyline(coords.map(p=>[p[1],p[0]]),{color,weight:phase==='base'&&data.notification?width+4:width,dashArray:walking?'6 5':null,opacity:phase==='base'&&data.notification?0.5:0.9});
          path.bindTooltip(tooltip(`${phase} · ${leg.mode} ${leg.line||''} · ${leg.start_stop_name} → ${leg.end_stop_name}`)).addTo(group);
        }
        const ls=lines(leg);
        for(const connection of connections(leg))overlays.push({...connection,phase});
        marker(ls[0][0],leg.start_stop_name||'Start',color);marker(ls.at(-1).at(-1),leg.end_stop_name||'Mål',color);
        if(!walking&&++rides>1)marker(ls[0][0],'Byte: '+leg.start_stop_name,color,8);
      }
    }
    marker([data.origin.lon,data.origin.lat],'START: '+data.origin.name,'#17313e',9).bindTooltip(tooltip('START'),{permanent:true,direction:'bottom'});
    marker([data.destination.lon,data.destination.lat],'MÅL: '+data.destination.name,'#17313e',9).bindTooltip(tooltip('MÅL'),{permanent:true,direction:'bottom'});
    if(data.notification){
      const notification=data.notification;
      const stop=marker(notification.coordinates,'UTEBLIVEN TUR · besked '+notification.time.slice(11,19)+' · '+notification.stop_name,'#bf2f24',13);
      stop.setStyle({weight:4,fillColor:'#fff0eb'});
      stop.bindTooltip(tooltip('BESKED: '+notification.stop_name),{permanent:true,direction:'top'});
    }
    // Draw after all routes/markers so short connections are not overpainted.
    for(const connection of overlays){
      const coords=connection.coordinates;
      const label=`Approximativ anslutning · ${connection.label} · ${Math.round(connection.meters)} m`;
      L.polyline(coords.map(p=>[p[1],p[0]]),{color:'#e18118',weight:5,dashArray:'5 4'}).bindTooltip(tooltip(label)).addTo(group).bringToFront();
      const a=coords[0],b=coords.at(-1);
      marker([(a[0]+b[0])/2,(a[1]+b[1])/2],label,'#e18118',4).bringToFront();
    }
    bounds=group.getBounds();map.invalidateSize();map.fitBounds(bounds,{padding:[28,28],maxZoom:16});
  }
  function node(tag,attrs,parent){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n;}
  function drawFallback(data,focusPoints=null){
    $('map').hidden=true;$('map-fallback').hidden=false;
    $('map-status').textContent='Kartbiblioteket kunde inte laddas. Lokal reservkarta visar rutter och markörer utan bakgrund.';
    const svg=$('map-fallback');svg.replaceChildren();
    const segments=['base','completed','reserve'].flatMap(phase=>(data[phase]||[]).map(leg=>({phase,leg})));
    const points=focusPoints||segments.flatMap(({leg})=>lines(leg).flat()).concat([[data.origin.lon,data.origin.lat],[data.destination.lon,data.destination.lat]]);
    const lat=points.reduce((a,p)=>a+p[1],0)/points.length,c=Math.cos(lat*Math.PI/180);
    const west=Math.min(...points.map(p=>p[0]*c)),east=Math.max(...points.map(p=>p[0]*c)),south=Math.min(...points.map(p=>p[1])),north=Math.max(...points.map(p=>p[1]));
    const scale=Math.min(570/Math.max(east-west,.001),350/Math.max(north-south,.001));
    const project=p=>[350+(p[0]*c-(west+east)/2)*scale,240-(p[1]-(north+south)/2)*scale];
    const group=node('g',{},svg);svgView={group,x:0,y:0,scale:1};
    function path(coords,color,dash,weight){node('polyline',{points:coords.map(p=>project(p).join(',')).join(' '),fill:'none',stroke:color,'stroke-dasharray':dash,'stroke-width':weight},group);}
    function mark(p,label,color,radius){const[x,y]=project(p);node('circle',{cx:x,cy:y,r:radius,fill:'white',stroke:color,'stroke-width':2},group);node('text',{x:x+8,y:y-8},group).textContent=label;}
    for(const{phase,leg}of segments){
      const ls=lines(leg);for(const coords of ls)path(coords,colors[phase],leg.mode==='WALK'?'6 5':'',leg.mode==='RAIL'?6:4);
      mark(ls[0][0],leg.start_stop_name||'',colors[phase],4);mark(ls.at(-1).at(-1),leg.end_stop_name||'',colors[phase],4);
    }
    mark([data.origin.lon,data.origin.lat],'START','#17313e',8);mark([data.destination.lon,data.destination.lat],'MÅL','#17313e',8);
    if(data.notification)mark(data.notification.coordinates,'BESKED · '+data.notification.stop_name,'#bf2f24',12);
    for(const{leg}of segments)for(const connection of connections(leg)){
      path(connection.coordinates,'#e18118','5 4',5);
      const a=connection.coordinates[0],b=connection.coordinates.at(-1);
      mark([(a[0]+b[0])/2,(a[1]+b[1])/2],'','#e18118',4);
    }
  }
  function render(data){
    last=data;
    if(window.L&&$('leaflet-css').sheet&&!new URLSearchParams(location.search).has('offline-map'))drawLeaflet(data);
    else drawFallback(data);
  }
  function clear(){last=null;if(group)group.clearLayers();$('map-fallback').replaceChildren();}
  function transform(){if(svgView)svgView.group.setAttribute('transform',`translate(${svgView.x} ${svgView.y}) scale(${svgView.scale})`);}
  let drag=null;
  let picker=null,pickMarkers=[];
  let pickerPoints=[];
  function setPickerPoints(points){
    pickerPoints=points;
    if(!picker)return;
    for(const p of points){
      if(pickMarkers[p.endpoint])picker.removeLayer(pickMarkers[p.endpoint]);
      delete pickMarkers[p.endpoint];
      if(!Number.isFinite(p.lat)||!Number.isFinite(p.lon)||p.lat< -90||p.lat>90||p.lon< -180||p.lon>180)continue;
      pickMarkers[p.endpoint]=L.circleMarker([p.lat,p.lon],{radius:8,color:p.endpoint==='from'?colors.base:colors.reserve,weight:3,fillColor:'white',fillOpacity:1}).bindTooltip(tooltip(p.endpoint==='from'?'A':'B'),{permanent:true}).addTo(picker);
    }
  }
  document.addEventListener('DOMContentLoaded',()=>{
    const svg=$('map-fallback');
    svg.addEventListener('wheel',event=>{if(!svgView)return;event.preventDefault();svgView.scale=Math.max(.5,Math.min(6,svgView.scale*(event.deltaY<0?1.15:.87)));transform();},{passive:false});
    svg.addEventListener('pointerdown',event=>{drag=[event.clientX,event.clientY];svg.setPointerCapture(event.pointerId);});
    svg.addEventListener('pointermove',event=>{if(drag&&svgView){const ratio=700/svg.clientWidth;svgView.x+=(event.clientX-drag[0])*ratio;svgView.y+=(event.clientY-drag[1])*ratio;drag=[event.clientX,event.clientY];transform();}});
    svg.addEventListener('pointerup',()=>drag=null);
  });
  window.addEventListener('load',()=>{if(last)render(last);});
  return {render,clear,setPickerPoints,connections,focusConnections(leg){
    const points=connections(leg).flatMap(c=>c.coordinates);
    if(!points.length)return;
    if(map&&!$('map').hidden){
      map.fitBounds(L.latLngBounds(points.map(p=>[p[1],p[0]])),{padding:[55,55],maxZoom:19});
      $('map').scrollIntoView({block:'center'});
    }else if(svgView&&last){drawFallback(last,points);$('map-fallback').scrollIntoView({block:'center'});}
  },pick(callback){
    if(!window.L){$('pick-status').textContent='Kartbiblioteket är otillgängligt. Ange koordinaterna i fälten.';return;}
    $('pick-map').hidden=false;
    if(!picker){
      picker=L.map('pick-map').setView([55.69,13.13],11);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,keepBuffer:0,updateWhenIdle:true,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>{$('pick-status').textContent='Bakgrundskartan kunde inte laddas. Kartklick och koordinater fungerar ändå.';}).addTo(picker);
      L.rectangle([[55.60,12.95],[55.80,13.30]],{color:'#277e97',fill:false,weight:2}).addTo(picker);
      picker.on('click',event=>{
        const endpoint=$('pick-endpoint').value;
        if(pickMarkers[endpoint])picker.removeLayer(pickMarkers[endpoint]);
        pickMarkers[endpoint]=L.circleMarker(event.latlng,{radius:8,color:endpoint==='from'?colors.base:colors.reserve,weight:3,fillColor:'white',fillOpacity:1}).bindTooltip(tooltip(endpoint==='from'?'A':'B'),{permanent:true}).addTo(picker);
        callback(endpoint,event.latlng.lat,event.latlng.lng);
      });
    }picker.invalidateSize();setPickerPoints(pickerPoints);
    $('pick-status').textContent='Välj A eller B och klicka. Rektangeln visar tillgängligt OSM-område.';
  },reset(){if(map&&bounds)map.fitBounds(bounds,{padding:[28,28],maxZoom:16});if(svgView&&last)drawFallback(last);}};
})();
