(()=>{
function activityLevel(rate){return Number.isFinite(rate)&&rate>0?Math.min(1,Math.log1p(rate)/Math.log(101)):0;}
function freshness(age){return Number.isFinite(age)?Math.max(0,Math.min(1,(45-age)/25)):0;}
if(typeof module!=='undefined')module.exports={activityLevel,freshness};
if(typeof window==='undefined')return;
const data=JSON.parse(document.getElementById('brain-data').textContent);
const canvas=document.getElementById('brain-canvas'),ctx=canvas.getContext('2d');
const $=id=>document.getElementById(id),colors={taste:'#bfe586',feeding:'#f3c177',steering:'#86cbdd',relay:'#748c80'};
let mode='anatomy',yaw=.2,pitch=-.35,zoom=1,w=800,h=470,points=[],selected=null,lastTrial=null,intervention='normal',drag=null,moved=false;
let telemetry=null, disconnected=false, displayCloud=[],displayRegions=[],displayNodes=new Map(),lastFrame=0,infoFrame=0;
const nodes=new Map(data.nodes.map(n=>[n.id,n]));
function activeNodes(){return data.nodes.filter(n=>mode==='anatomy'?n.position:mode==='steering'?n.group==='steering':n.group!=='steering');}
function project(p){const x=p[0]*Math.cos(yaw)+p[2]*Math.sin(yaw),z=-p[0]*Math.sin(yaw)+p[2]*Math.cos(yaw);return [w/2+x*Math.min(w,h)*.43*zoom,h/2+(p[1]*Math.cos(pitch)-z*Math.sin(pitch))*Math.min(w,h)*.43*zoom];}
function activity(n){return telemetry?.rates_by_id?.[n.id]??null;}
function glow(x,y,r,strength,color='#54ffd0'){
 if(strength<=0)return;
 const gradient=ctx.createRadialGradient(x,y,0,x,y,r);
 gradient.addColorStop(0,color);gradient.addColorStop(1,'transparent');
 ctx.globalCompositeOperation='lighter';ctx.globalAlpha=strength;ctx.fillStyle=gradient;
 ctx.fillRect(x-r,y-r,r*2,r*2);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
}
function age(){return telemetry?Math.max(0,Date.now()/1000-telemetry.at):Infinity;}
function fade(){return disconnected?0:freshness(age());}
function dot(x,y,r,color,alpha=1){ctx.globalAlpha=alpha;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.globalAlpha=1;}
function draw(){ctx.clearRect(0,0,w,h);points=[];const visible=activeNodes(),pos=new Map();
if(mode==='anatomy'){
 for(let i=0;i<(data.regions||[]).length;i++){
  const strength=displayRegions[i]||0;if(!strength)continue;
  const [x,y]=project(data.regions[i].position);
  glow(x,y,Math.min(w,h)*.085*zoom,strength*.65);
 }
 for(let i=0;i<data.cloud.length;i++){
  const [x,y]=project(data.cloud[i]),level=displayCloud[i]||0;
  dot(x,y,1.05+level*1.8,level>0?'#62ffd8':'#507665',.22+level*.78);
  if(level>.1)glow(x,y,3+level*7,level*.45);
 }
 for(const n of visible)pos.set(n.id,project(n.position));
 ctx.fillStyle='#94aa9e';ctx.font='12px system-ui';ctx.fillText('LIVE ACTIVITY · '+data.somas_available.toLocaleString()+' MAPPED CELLS · '+(data.regions||[]).length+' SPATIAL REGIONS',20,24);
}else{
 const columns=mode==='feeding'?['taste','relay','feeding']:['PFL3','DNa03','DNa02'];
 columns.forEach((group,col)=>{const groupNodes=visible.filter(n=>mode==='feeding'?n.group===group:n.type===group);groupNodes.forEach((n,i)=>pos.set(n.id,[45+(w-90)*col/(columns.length-1),65+(h-110)*(i+.5)/Math.max(groupNodes.length,1)]));ctx.fillStyle='#c6d9cc';ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText(group==='relay'?'Selected intermediates':group==='taste'?'Sweet taste':group==='feeding'?'MN9':group,45+(w-90)*col/(columns.length-1),30);});ctx.textAlign='left';
 for(const e of data.edges){const a=pos.get(e.source),b=pos.get(e.target);if(!a||!b)continue;const focus=selected&&(e.source===selected||e.target===selected);ctx.strokeStyle=e.weight>0?'#7cac8b':'#c18aae';const level=displayNodes.get(e.source)||0;ctx.globalAlpha=focus ? .8 : .025+level*.45;ctx.lineWidth=focus?1.6:Math.min(1.4,.25+Math.log1p(Math.abs(e.weight))*.13);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();if(focus){const dx=b[0]-a[0],dy=b[1]-a[1],angle=Math.atan2(dy,dx),x=b[0]-7*Math.cos(angle),y=b[1]-7*Math.sin(angle);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-6*Math.cos(angle-.45),y-6*Math.sin(angle-.45));ctx.moveTo(x,y);ctx.lineTo(x-6*Math.cos(angle+.45),y-6*Math.sin(angle+.45));ctx.stroke();}}
 ctx.globalAlpha=1;
}
for(const n of visible){const p=pos.get(n.id);if(!p)continue;const level=displayNodes.get(n.id)||0,r=mode==='anatomy'?2.4:4;
if(level>0)glow(...p,8+level*16,level*.7,colors[n.group]);
dot(...p,r+level*2,colors[n.group],.15+level*.85);
if(n.id===selected){ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(...p,r+5,0,Math.PI*2);ctx.stroke();}
points.push({n,x:p[0],y:p[1]});}

}
function describe(){const visible=activeNodes();const menu=$('brain-select');menu.replaceChildren();const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Choose a neuron';menu.append(placeholder);for(const n of visible){const option=document.createElement('option');option.value=n.id;option.textContent=n.label+' · '+n.id;menu.append(option);}$('brain-mode').textContent=mode==='anatomy'?'Live activity map':mode==='feeding'?'Selected feeding subgraph':'PFL3 / descending circuit';$('brain-count').textContent=mode==='anatomy'?'Whole network activity':visible.length+' selected neurons';$('brain-description').textContent=mode==='anatomy'?'Measured activity across all 139,662 model cells with soma coordinates, grouped into spatial bins. 6,000 sampled cells provide the anatomical outline. Brighter means more firing; dark means zero or no recent measurement.':mode==='feeding'?'Real connections among taste cells, 15 strongly connected two-step intermediates, and MN9. Many other paths are omitted. Width reflects signed-contact magnitude.':'Real connections among PFL3, DNa03, and DNa02. Autonomous mode decodes FC2-driven PFL3 activity. DNa02/DNa03 are displayed for research, not used to select cardinal moves.';$('brain-evidence').textContent='Live trial averages · brightness follows measured firing · old activity fades';canvas.setAttribute('aria-label',mode==='anatomy'?'Sampled MaleCNS cell-body map. Drag to rotate, scroll to zoom.':'Selected '+mode+' connectivity diagram. Positions are schematic; lines are actual model connections.');$('brain-help').firstChild.textContent=mode==='anatomy'?'Drag to rotate · scroll to zoom · select a highlighted neuron ':'Select a neuron · arrows show outgoing direction · diagram positions are not anatomy ';updateActivity();}
function updateActivity(){
 $('brain-activity-title').textContent='Measured network activity';
 if(!telemetry){$('brain-activity').textContent='Waiting for a neural trial. No activity is being invented.';return;}
 const seconds=Math.floor(age()),stale=seconds>=45||disconnected;
 $('brain-activity').textContent=telemetry.active_neurons.toLocaleString()+' / '+telemetry.total_neurons.toLocaleString()+' neurons fired · '+telemetry.phase+' · '+telemetry.duration_s+' s simulated · measured '+seconds+' s ago'+(stale?' · stale; display dimmed':seconds>20?' · fading while awaiting a new trial':'');
 if(selected)inspect(selected,false);
}
window.updateBrain=s=>{
 disconnected=s.disconnected===true;
 if(s.brain_activity)telemetry=s.brain_activity;
 intervention=s.intervention||'normal';updateActivity();
};
function animate(now){
 if(now-lastFrame>=50){
  const mix=1-Math.exp(-Math.min(250,now-lastFrame)/170),f=fade();lastFrame=now;
  for(let i=0;i<data.cloud.length;i++){const target=activityLevel(telemetry?.cloud_rates_hz?.[i])*f;displayCloud[i]=(displayCloud[i]||0)+(target-(displayCloud[i]||0))*mix;}
  for(let i=0;i<(data.regions||[]).length;i++){const mean=telemetry?.region_mean_hz?.[i]??0,fraction=telemetry?.region_active_fraction?.[i]??0;const target=Math.min(1,Math.log1p(mean)/Math.log(11)+Math.sqrt(fraction)*.35)*f;displayRegions[i]=(displayRegions[i]||0)+(target-(displayRegions[i]||0))*mix;}
  for(const n of data.nodes){const old=displayNodes.get(n.id)||0;displayNodes.set(n.id,old+(activityLevel(activity(n))*f-old)*mix);}
  draw();if(now-infoFrame>1000){updateActivity();infoFrame=now;}
 }
 requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.view;selected=null;$('brain-detail').textContent='Select a highlighted neuron for annotation and connectivity.';document.querySelectorAll('[data-view]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));describe();draw();}));
$('brain-reset').addEventListener('click',()=>{yaw=.2;pitch=-.35;zoom=1;selected=null;draw();});
canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];moved=false;canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!drag||mode!=='anatomy')return;const dx=e.clientX-drag[0],dy=e.clientY-drag[1];if(Math.abs(dx)+Math.abs(dy)>2)moved=true;yaw+=dx*.006;pitch+=dy*.006;drag=[e.clientX,e.clientY];draw();});
canvas.addEventListener('pointerup',e=>{drag=null;if(moved)return;const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;const pick=points.map(p=>({...p,d:Math.hypot(p.x-x,p.y-y)})).sort((a,b)=>a.d-b.d)[0];if(!pick||pick.d>16)return;inspect(pick.n.id);draw();});
function inspect(id,redraw=true){if(!nodes.has(id))return;selected=id;$('brain-select').value=id;const n=nodes.get(id),out=data.edges.filter(e=>e.source===n.id),rate=activity(n);$('brain-detail').textContent=n.label+' · body '+n.id+' · '+out.length+' displayed outgoing connections'+(rate==null?' · activity unmeasured': ' · measured '+rate.toFixed(1)+' Hz')+(n.position?'':' · no annotated soma position');if(redraw)draw();}
$('brain-select').addEventListener('change',e=>inspect(e.target.value));
canvas.addEventListener('pointercancel',()=>{drag=null;});
canvas.addEventListener('wheel',e=>{if(mode!=='anatomy')return;e.preventDefault();zoom=Math.max(.5,Math.min(4,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
new ResizeObserver(()=>{const r=canvas.getBoundingClientRect();w=r.width;h=r.height;const d=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*d);canvas.height=Math.round(h*d);ctx.setTransform(d,0,0,d,0,0);draw();}).observe(canvas);
describe();draw();
})();
