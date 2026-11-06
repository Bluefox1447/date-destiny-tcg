(()=>{
const $=s=>document.querySelector(s);
const D=JSON.parse($('#deckdata').textContent), SL=JSON.parse($('#sleeves').textContent);
const NEU=['entity','partners'];
let ALL=[], BY={}, hist=[], redoS=[], sortMode='cost', dirty=false;
const SORTS={cost:'ค่าคอส',color:'สี',type:'ประเภท',name:'ชื่อ'};
const deck={id:D.id,name:D.name,desc:D.desc||'',main:{...D.main},partners:[...D.partners],sleeve:D.sleeve||'',cover:D.cover||null,public:!!D.public};
$('#dname').value=deck.name; $('#ddesc').value=deck.desc; $('#dpub').checked=deck.public;

/* ---------- ประวัติ Undo/Redo ---------- */
const snap=()=>JSON.stringify({main:deck.main,partners:deck.partners});
const push=()=>{hist.push(snap()); if(hist.length>100)hist.shift(); redoS=[]; dirty=true;};
function restore(s){const o=JSON.parse(s); deck.main=o.main; deck.partners=o.partners; render();}
function undo(){ if(!hist.length) return; redoS.push(snap()); restore(hist.pop()); }
function redo(){ if(!redoS.length) return; hist.push(snap()); restore(redoS.pop()); }

const mainCount=()=>Object.values(deck.main).reduce((a,b)=>a+b,0);
const owned=id=>(deck.main[id]||0)+deck.partners.filter(x=>x==id).length;
const CMP={cost:(a,b)=>a.cost-b.cost||a.name.localeCompare(b.name),
  color:(a,b)=>a.color.localeCompare(b.color)||a.cost-b.cost||a.name.localeCompare(b.name),
  type:(a,b)=>a.type.localeCompare(b.type)||a.cost-b.cost||a.name.localeCompare(b.name),
  name:(a,b)=>a.name.localeCompare(b.name)};

/* ---------- วาดรายการเด็ค ---------- */
function dc(c,sec,i){return `<div class="dc" data-id="${c.id}" data-sec="${sec}" data-i="${i??''}" title="คลิกเพื่อเอาออก 1 ใบ">${cardHTML(c,{mini:true})}</div>`;}
function renderCover(){
  const c=deck.cover&&BY[deck.cover], el=$('#cvprev'); if(!el) return;
  el.innerHTML=c?cardHTML(c):'<span class="mut" style="font-size:.8rem">ยังไม่ได้เลือก</span>';
  $('#cvclear').style.display=c?'':'none';
}
function setCover(id){deck.cover=id||null; dirty=true; renderCover(); toast(id?'ตั้งเป็นการ์ดหน้าเด็คแล้ว (อย่าลืมกดบันทึก)':'ล้างการ์ดหน้าเด็คแล้ว','ok');}
function render(){
  renderCover();
  const copies=[]; Object.entries(deck.main).forEach(([id,q])=>{const c=BY[id]; if(c) for(let k=0;k<q;k++) copies.push(c);});
  copies.sort(CMP[sortMode]);
  $('#lm').innerHTML=copies.map(c=>dc(c,'main')).join('');
  const slots=(arr,n,sec)=>arr.map((id,i)=>BY[id]?dc(BY[id],sec,i):'').join('')+'<div class="slot"></div>'.repeat(Math.max(0,n-arr.length));
  $('#lp').innerHTML=slots(deck.partners,4,'partner');
  $('#cp').textContent=deck.partners.length+'/4';
  $('#cm').textContent=mainCount()+'/'+DECK_SIZE;
  const cc={}; copies.forEach(c=>cc[c.color]=(cc[c.color]||0)+1);
  $('#chips').innerHTML=Object.entries(cc).map(([k,n])=>`<span title="${CLABEL[k]||k}"><i style="background:${COLOR_HEX[k]||'#888'}"></i>${n}</span>`).join('');
  const iss=[];
  if(deck.partners.length!==4) iss.push('Partners ยังไม่ครบ 4 ใบ');
  if(mainCount()!==DECK_SIZE) iss.push(`เด็คหลักควรมี ${DECK_SIZE} ใบ`);
  $('#issues').innerHTML=iss.length?iss.map(t=>`<span class="pill warn">${t}</span>`).join(''):'<span class="pill ok">เด็คถูกต้องตามกติกา</span>';
  $('#undo').disabled=!hist.length; $('#redo').disabled=!redoS.length;
  pool();
}

/* ---------- วิกิการ์ดฝั่งขวา ---------- */
function pool(){
  const q=$('#q').value.toLowerCase(),t=$('#ft').value,c=$('#fc').value,o=$('#fo').value;
  const l=ALL.filter(x=>(!t||x.type===t)&&(!c||x.color===c)&&(!q||(x.name+x.effect+x.server+x.code).toLowerCase().includes(q)));
  l.sort((a,b)=>o==='name'?a.name.localeCompare(b.name):o==='code'?a.code.localeCompare(b.code):CMP.cost(a,b));
  $('#pool').innerHTML=l.length?l.map(x=>{const n=owned(x.id);
    return `<div class="pc" data-id="${x.id}">${cardHTML(x,{mini:true})}${n?`<span class="own">${n}</span>`:''}
     <div class="acts"><button data-a="main" title="เพิ่มเข้าเด็คหลัก">+</button>${NEU.includes(x.type)?'<button data-a="partner" title="ใส่ Partners Zone">P</button>':''}</div></div>`}).join('')
    :'<p class="mut">ไม่พบการ์ด</p>';
}
function addMain(id){
  if(owned(id)>=MAX_COPIES) return toast(`ใส่การ์ดชื่อซ้ำได้สูงสุด ${MAX_COPIES} ใบ`,'err');
  push(); deck.main[id]=(deck.main[id]||0)+1; render();
}
function addPartner(id){
  if(deck.partners.length>=4) return toast('Partners Zone มีได้ 4 ใบ','err');
  if(owned(+id)>=MAX_COPIES) return toast(`ใส่การ์ดชื่อซ้ำได้สูงสุด ${MAX_COPIES} ใบ`,'err');
  push(); deck.partners.push(+id); render();
}
$('#pool').addEventListener('click',e=>{
  const t=e.target.closest('.pc'); if(!t) return; const id=+t.dataset.id, c=BY[id], a=e.target.dataset.a;
  if(a==='main') addMain(id);
  else if(a==='partner') addPartner(id);
  else if(!a) {  // คลิกตัวการ์ด: เพิ่มตามประเภท
    if(c.type==='partners'&&deck.partners.length<4) addPartner(id);
    else addMain(id);
  }
});
$('.dbmid').addEventListener('click',e=>{
  const t=e.target.closest('.dc'); if(!t) return; const id=+t.dataset.id; push();
  if(t.dataset.sec==='main'){ deck.main[id]--; if(deck.main[id]<=0) delete deck.main[id]; }
  else deck.partners.splice(+t.dataset.i,1);
  render();
});

/* ---------- ดูรายละเอียดทางซ้าย ---------- */
function showInfo(c){
  $('#inspect').innerHTML=cardHTML(c);
  const r=(k,v)=>`<div class="kv"><b>${k}</b><span>${v}</span></div>`;
  let h=`<h3 style="margin:10px 0 2px">${esc(c.name)}</h3><div class="mono mut" style="margin-bottom:6px">${esc(c.code)} · ${esc(TLABEL[c.type]||c.type)}</div>`+r('ค่าคอส',c.cost)+r('สี',esc(CLABEL[c.color]||c.color));
  if(NEU.includes(c.type)) h+=r('ATK / CRIT / DEF',`${c.atk} / ${c.crit} / ${c.def}`)+(c.server?r('เซิร์ฟเวอร์',esc(c.server)):'');
  if(c.type==='ship') h+=r('Link 1/2/3',`${c.link_atk} / ${c.link_crit} / ${c.link_def}`);
  h+=`<div class="kv"><b>เอฟเฟค</b><span class="eff">${esc(c.effect)||'-'}</span></div>`;
  $('#info').innerHTML=h;
}
document.addEventListener('mouseover',e=>{const t=e.target.closest('.dc,.pc'); if(t&&BY[t.dataset.id]) showInfo(BY[t.dataset.id]);});

/* ---------- ปุ่มบนแถบ ---------- */
function sleeveUI(){
  $('#dsleeve').value=deck.sleeve||'';
  const s=SL.find(x=>x.id==deck.sleeve)||SL.find(x=>x.default), p=$('#slprev');
  p.style.backgroundImage=s&&s.image?`url('${s.image}')`:''; p.classList.toggle('img',!!(s&&s.image));
}
$('#dsleeve').addEventListener('change',e=>{deck.sleeve=e.target.value; sleeveUI();});
$('#undo').onclick=undo; $('#redo').onclick=redo;
$('#cvclear').onclick=()=>setCover(null);
$('#clear').onclick=()=>{ if(!confirm('ล้างการ์ดทั้งหมดในเด็คนี้?')) return; push(); deck.main={}; deck.partners=[]; render(); };
$('#sort').onclick=()=>{const k=Object.keys(SORTS); sortMode=k[(k.indexOf(sortMode)+1)%k.length]; $('#sort').textContent='เรียง: '+SORTS[sortMode]; render();};
document.addEventListener('keydown',e=>{ if(e.target.matches&&e.target.matches('input,textarea,select')) return;
  if((e.ctrlKey||e.metaKey)&&e.key==='z'){e.preventDefault();undo();} if((e.ctrlKey||e.metaKey)&&e.key==='y'){e.preventDefault();redo();} });
['q','ft','fc','fo'].forEach(i=>$('#'+i).addEventListener('input',pool));
async function save(){
  deck.name=$('#dname').value.trim()||'เด็คใหม่'; deck.desc=$('#ddesc').value; deck.public=$('#dpub').checked;
  const r=await fetch('/api/decks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:deck.id,name:deck.name,desc:deck.desc,public:deck.public,main:deck.main,partners:deck.partners,sleeve:deck.sleeve,cover:deck.cover})});
  if(!r.ok){toast('บันทึกไม่สำเร็จ','err');return null}
  const j=await r.json(); deck.id=j.id; history.replaceState(null,'','/decks/'+j.id+'/edit'); toast('บันทึกเด็คแล้ว','ok'); dirty=false; return j;
}
$('#save').onclick=async()=>{const j=await save(); if(j) location.href='/decks?saved=1';};
$('#copy').onclick=async()=>{const j=await save(); if(!j) return; const r=await (await fetch('/api/decks/'+j.id+'/code')).json();
  try{await navigator.clipboard.writeText(r.code);toast('คัดลอกโค้ดเด็คแล้ว','ok')}catch(e){prompt('คัดลอกโค้ดนี้',r.code)}};
window.addEventListener('beforeunload',e=>{ if(dirty){e.preventDefault();e.returnValue='';} });
/* ---------- คลิกขวาที่การ์ด → ขยายการ์ด (แสดงรายละเอียดทั้งหมด) ---------- */
function zoomDetail(c){
  const sg=n=>(n>=0?'+':'')+n;
  const st=NEU.includes(c.type)?`<div class="isr"><span>ATK <b>${c.atk}</b></span><span>CRIT <b>${c.crit}</b></span><span>DEF <b>${c.def}</b></span></div>`
    :c.type==='ship'?`<div class="isr"><span>Link ATK <b>${sg(c.link_atk)}</b></span><span>CRIT <b>${sg(c.link_crit)}</b></span><span>DEF <b>${sg(c.link_def)}</b></span></div>`:'';
  return `<div class="iname">${esc(c.name)}</div>
    <div class="imeta">${esc(c.code||'')} · ${esc(TLABEL[c.type]||c.type)} · สี${esc(CLABEL[c.color]||c.color)} · Cost ${c.cost}${c.server?' · เซิร์ฟเวอร์ '+esc(c.server):''}</div>${st}
    <div class="ieff">${esc(c.effect)||'<span class="mut">ไม่มีเอฟเฟค</span>'}</div>
    <div class="imeta">ในเด็คนี้: ${owned(c.id)} ใบ (สูงสุด ${MAX_COPIES} ใบ)</div>`;
}
function openZoom(id){const c=BY[id]; if(!c) return; $('#zvc').innerHTML=cardHTML(c,{big:true}); $('#zvt').innerHTML=zoomDetail(c); $('#zoomb').classList.remove('hide');}
const closeZoomB=()=>$('#zoomb').classList.add('hide');
$('#zbx').onclick=closeZoomB; $('#zoomb').addEventListener('click',e=>{if(e.target.id==='zoomb') closeZoomB();});
let cmenu=null; const closeMenu=()=>{if(cmenu){cmenu.remove();cmenu=null;}};
document.addEventListener('contextmenu',e=>{
  const t=e.target.closest('.pc,.dc'); closeMenu(); if(!t||!BY[t.dataset.id]) return; e.preventDefault();
  cmenu=document.createElement('div'); cmenu.className='ctx'; cmenu.innerHTML='<button type="button" data-c="zoom">🔍 ขยายการ์ด</button><button type="button" data-c="cover">🖼 ตั้งเป็นการ์ดหน้าเด็ค</button>';
  cmenu.style.left=Math.min(e.clientX,innerWidth-210)+'px'; cmenu.style.top=Math.min(e.clientY,innerHeight-70)+'px';
  cmenu.querySelector('[data-c="zoom"]').onclick=()=>{closeMenu(); openZoom(+t.dataset.id);};
  cmenu.querySelector('[data-c="cover"]').onclick=()=>{closeMenu(); setCover(+t.dataset.id);};
  document.body.appendChild(cmenu);
});
document.addEventListener('click',e=>{ if(cmenu&&!e.target.closest('.ctx')) closeMenu(); },true);
document.addEventListener('keydown',e=>{ if(e.key==='Escape'){closeMenu();closeZoomB();} });
fetch('/api/cards').then(r=>r.json()).then(d=>{ALL=d; d.forEach(c=>BY[c.id]=c); sleeveUI(); render();});
})();
