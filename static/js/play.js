(()=>{
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const CODE=document.body.dataset.room, MYID=+document.body.dataset.uid;
let ACT=MYID, lastTurn=null, atkSel=null, bonusA=0, bonusD=0, combatOn=false;      // ACT = ฝั่งที่กำลังควบคุม (ห้องทดสอบสลับได้)
const socket=io();
const SLEEVE={me:'',opp:''};
let S=null, mode=null, seated=false, autoPay=true, flipLabels=true, dragIid=null, dragCid=null, dragZone=null, lastRoll=null, prevTurn;
const DICE_TURNS=[3,5,7,9], LINK_MAX=3;
const ZN={hp:'Firewall (HP)',partners:'Partners',attack:'Attack',protect:'Protect',server:'Server',delect:'Delect',deck:'Deck',hand:'มือ'};

/* ---------------- Socket ---------------- */
socket.on('connect',()=>socket.emit('join',{code:CODE}));
socket.on('need_deck',()=>{$('#deckpick').style.display='grid'});
$('#joinBtn').onclick=()=>{$('#deckpick').style.display='none';socket.emit('join',{code:CODE,deck_id:$('#deckSel').value})};
$('#specBtn').onclick=()=>{$('#deckpick').style.display='none';socket.emit('join',{code:CODE,spectate:true})};
socket.on('state',s=>{
  S=s;
  const tn=S.state?S.state.turn:null; if(window.sfx&&prevTurn!==undefined&&tn&&tn!==prevTurn&&tn===MYID&&!S.solo) sfx('turn'); prevTurn=tn;
  const rl=S.state&&S.state.roll, rkey=rl?`${rl.id}-${rl.ts}`:'';      // ลูกเต๋า D4: เล่นอนิเมชันเมื่อมีการทอยใหม่
  if(lastRoll===null) lastRoll=rkey; else if(rkey&&rkey!==lastRoll){lastRoll=rkey;showDice(rl);} else if(!rkey) lastRoll=rkey;
  if(S.solo&&S.state){   // ห้องทดสอบ: สลับไปควบคุมฝั่งที่ถึงเทิร์นให้อัตโนมัติ
    if(S.state.turn!=null&&S.state.turn!==lastTurn) ACT=S.state.turn;
    lastTurn=S.state.turn;
  }
  render();
});
socket.on('err',d=>toast(d.m,'err'));
socket.on('peek',d=>openList('เด็คของคุณ (บนสุดก่อน)',d.cards,'deck'));
const act=(type,x={})=>{ if(window.sfx){ if(type==='attack') sfx('hit'); else if(['move','link','unlink','generate','tap','flip'].includes(type)) sfx('click'); }
  socket.emit('act',{code:CODE,type,...x,...(ACT!==MYID?{as:ACT}:{})});
};

/* ---------------- Helpers ---------------- */
function sides(){
  const ps=S.players; seated=!!ps.find(p=>p.uid===MYID);
  const me=ps.find(p=>p.uid===(S.solo?ACT:MYID))||(seated?ps.find(p=>p.uid===MYID):null);
  const a=me||ps[0]||null, b=ps.find(p=>p!==a)||null; return {me:a,opp:b};
}
const pst=P=>S.state&&P?S.state.p[P.uid]:null;
const nameOf=uid=>(S.players.find(p=>p.uid===uid)||{}).name||'?';

function cardEl(c,zn,side,mini=true){
  const mine=side==='me'&&seated;
  const back=c.h||(!c.up&&(zn==='hp'||zn==='deck'));
  const base=`data-iid="${c.iid}" data-zone="${zn}" data-side="${side}"${mine?' draggable="true"':''}`;
  if(back){const sl=SLEEVE[side]; return `<div class="card ${mini?'mini':''} back ${sl?'img':''} ${c.tap?'tap':''}" ${base}${sl?` style="background-image:url('${esc(sl)}')"`:''}>${sl?'':'<i>DD</i>'}</div>`;}
  const cd=S.cards[c.cid]; if(!cd) return '';
  return cardHTML(cd,{mini,cls:(c.tap?'tap ':'')+(!c.up&&zn!=='hand'?'dn':''),attrs:base+` data-cid="${c.cid}"`,ctr:c.ctr,dmg:c.dmg,lnk:(c.links||[]).length,mod:c.mod});
}

/* ---------------- Track (แถบเลข Code 1-10 ตามเสื่อ) ---------------- */
function area(side,n){
  if(n===1) return side==='me'?'1/1/3/2':'1/6/3/7';
  if(n===10) return side==='me'?'1/6/3/7':'1/1/3/2';
  if(side==='me'){const c=(n%2===0?n/2:(n-1)/2)+1, r=n%2===0?1:2; return `${r}/${c}/${r+1}/${c+1}`;}
  const c=(n%2===1?(11-n)/2:(10-n)/2)+1, r=n%2===1?1:2; return `${r}/${c}/${r+1}/${c+1}`;
}
function initTrack(){
  [['me','#trkMe'],['opp','#trkOpp']].forEach(([s,sel])=>{
    $(sel).innerHTML=[...Array(10)].map((_,i)=>`<button class="n" data-n="${i+1}" style="grid-area:${area(s,i+1)}">${i+1}</button>`).join('');
  });
  $('.track').insertAdjacentHTML('beforeend','<span class="cdnum me" id="cdMe"></span><span class="cdnum opp" id="cdOpp"></span>');
  $('#trkMe').addEventListener('click',e=>{const b=e.target.closest('.n'); if(!b||!seated||!S.state) return;
    const n=+b.dataset.n, cur=pst(sides().me).code; act('code',{set:n===cur?n-1:n});});
}
function updTrack(sel,badge,code){
  $$('.n',$(sel)).forEach(b=>{const n=+b.dataset.n; b.classList.toggle('on',n<=code); b.classList.toggle('cur',n===code);});
  $(badge).textContent=`CODE ${code}/10`;
}

/* ---------------- Render ---------------- */
function fillZone(el,side,zn,arr){
  const n=zn==='deck'?(arr||0):(arr||[]).length, zc=$('.zc',el);
  el.classList.toggle('has',n>0);
  if(zn==='deck'||zn==='hp'||zn==='delect'){
    if(!n){zc.innerHTML='';return;}
    const top=zn==='deck'?{iid:0,h:1}:zn==='hp'?arr[0]:arr[n-1];
    zc.innerHTML=`<div class="stack" data-stack="${zn}" data-side="${side}">${cardEl(top,zn,side).replace(' draggable="true"',zn==='deck'?'':' draggable="true"')}<span class="cnt">${n}</span></div>`;
  }else zc.innerHTML=(arr||[]).map(c=>cardEl(c,zn,side)).join('');
}
function render(){
  const {me,opp}=sides(), st=S.state, mp=pst(me), op=pst(opp);
  SLEEVE.me=me?me.sleeve||'':''; SLEEVE.opp=opp?opp.sleeve||'':'';
  [['me',mp],['opp',op]].forEach(([side,p])=>{
    $$(`.half.${side} .zone, .band .zone[data-side="${side}"]`).forEach(el=>{const zn=el.dataset.zone; fillZone(el,side,zn,p?p.z[zn]:(zn==='deck'?0:[]));});
  });
  updTrack('#trkMe','#cdMe',mp?mp.code:0); updTrack('#trkOpp','#cdOpp',op?op.code:0);
  [['me',mp],['opp',op]].forEach(([sd,P])=>{const sm=$(`.half.${sd} .z-protect .lbl small`); if(sm&&P) sm.textContent=`(MAX 3 Entity) · ${P.protect_atk===false?'โจมตีไม่ได้':'โจมตีได้'}`;});
  plate('#mePlate',me,mp); plate('#oppPlate',opp,op);
  $('#hand').innerHTML=mp?mp.z.hand.map(c=>cardEl(c,'hand','me',false)).join(''):'';
  $('#oppHand').innerHTML=op?op.z.hand.map(c=>cardEl(c,'hand','opp')).join(''):'';
  panel();
  $('#log').innerHTML=S.log.map(l=>{const t=new Date(l.t*1000).toTimeString().slice(0,5);
    return `<div class="${l.k}"><time>${t}</time>${l.k==='chat'?`<b>${esc(l.who)}:</b> ${esc(l.text)}`:`${esc(l.who)} ${esc(l.text)}`}</div>`}).join('');
  $('#log').scrollTop=1e9;
  markCombat();
  banner();
}
function plate(sel,P,p){
  const el=$(sel);
  if(!P){el.innerHTML='<span class="mut">รอผู้เล่น…</span>';return;}
  const st=S.state, turn=st&&st.turn===P.uid;
  el.innerHTML=`<span class="dot ${P.online?'on':''}" style="width:10px;height:10px;border-radius:50%;display:inline-block"></span><b>${esc(P.name)}</b>${P.uid===ACT?'<span class="mut">(คุณควบคุม)</span>':''}
   ${turn?'<span class="turnmark">กำลังเล่น</span>':''}
   ${p?`<span class="mut mono" style="font-size:.8rem">HP ${p.z.hp.length} · Deck ${p.z.deck} · มือ ${p.z.hand.length} · Code ${p.code}</span>`:''}`;
}
function banner(){
  $('#banner')?.remove(); const st=S.state; if(!st||st.winner==null) return;
  const d=document.createElement('div'); d.className='banner'; d.id='banner';
  d.innerHTML=`<div><h1>${!S.solo&&st.winner===MYID?'คุณชนะ!':esc(nameOf(st.winner))+' ชนะ'}</h1><p class="mut">เกมจบแล้ว</p>
   ${S.host===MYID?'<button class="btn pri" data-do="reset">เล่นใหม่ (รีเซ็ต)</button>':'<p class="mut">รอเจ้าของห้องกดเล่นใหม่</p>'}</div>`;
  document.body.appendChild(d);
}

/* ---------------- Side panel ---------------- */
function panel(){
  combatOn=false;
  const el=$('#panel'), st=S.state, {opp}=sides();
  if(!seated){el.innerHTML=`<h3>โหมดผู้ชม</h3><p class="mut">คุณกำลังดูเกมในห้อง ${esc(S.name)}</p>`;return;}
  let h=`<h3>${esc(S.name)} <span class="mono mut">${S.code}</span></h3>`;
  if(!opp){
    el.innerHTML=h+`<p style="margin:0 0 6px">รอผู้เล่นคนที่สอง… ส่งลิงก์นี้ให้เพื่อน (หรือบอกรหัสห้อง <b class="mono">${esc(S.code)}</b>)</p><div class="mono mut" style="font-size:.8rem;word-break:break-all;margin-bottom:8px">${esc(shareUrl())}</div><button class="btn sm pri" data-do="copylink">คัดลอกลิงก์ห้อง</button>`;return;}
  const mp=st.p[ACT], op=st.p[opp.uid];
  h+= st.phase==='setup'? setupHTML(mp,op,opp,st) : gameHTML(st,opp);
  if(S.solo) h=soloHTML(st)+h;
  h+=toolsHTML(st);
  el.innerHTML=h;
}
const shareUrl=()=>(document.body.dataset.public||location.origin)+location.pathname;
function copyLink(){
  const url=shareUrl();
  const done=()=>toast('คัดลอกลิงก์ห้องแล้ว ส่งให้เพื่อนได้เลย','ok');
  if(navigator.clipboard&&window.isSecureContext) navigator.clipboard.writeText(url).then(done,()=>prompt('คัดลอกลิงก์นี้ส่งให้เพื่อน',url));
  else prompt('คัดลอกลิงก์นี้ส่งให้เพื่อน',url);
}
function soloHTML(st){
  const other=S.players.find(p=>p.uid!==ACT);
  return `<div class="soloBox" style="border:2px dashed var(--sig);border-radius:14px;padding:8px 10px;margin-bottom:10px">
    <b style="color:var(--sig)">โหมดทดสอบคนเดียว</b>
    <div class="mut" style="font-size:.85rem">กำลังควบคุม: <b>${esc(nameOf(ACT))}</b> (ฝั่งล่าง) · เห็นการ์ดทั้งสองฝั่ง</div>
    <div class="btns"><button class="btn sm" data-do="swap">สลับไปควบคุม ${esc(other?other.name:'')}</button>
    ${st.phase==='setup'?'<button class="btn sm pri" data-do="solo_setup">Setup อัตโนมัติทั้งสองฝั่ง</button>':''}</div></div>`;
}
function setupHTML(mp,op,opp,st){
  const su=mp.setup, B=(d,t,dis,x='')=>`<button class="btn sm ${dis?'':'pri'}" data-do="${d}" ${dis?'disabled':''} ${x}>${t}</button>`;
  const row=(done,txt,btn)=>`<div class="s ${done?'done':''}"><span>${txt}</span>${btn||''}</div>`;
  return `<p class="mut" style="margin:0 0 4px">ขั้นตอนเตรียมเกม</p><div class="steps">
   ${row(!!st.first, st.first?`1. ผู้เริ่มเล่น: <b>${esc(nameOf(st.first))}</b>`:'1. หาผู้เริ่มเล่น',
      st.first?'':`<span class="btns">${B('first','สุ่ม',false,'data-who="random"')}${B('first','ฉัน',false,'data-who="me"')}${B('first','เขา',false,'data-who="opp"')}</span>`)}
   ${row(su.placed,'2. วาง Partners 4 ใบลง Partners Zone แล้วสับเด็ค',su.placed?'':B('place','วาง',false))}
   ${row(su.drew,'3. จั่ว 4 ใบขึ้นมือ',su.drew?'':B('setup_draw','จั่ว',!su.placed))}
   ${row(su.mull,'   เปลี่ยนมือได้ 1 ครั้ง',su.mull||su.hp?'':B('mulligan','เปลี่ยน',!su.drew))}
   ${row(su.hp,'4. วางการ์ด 8 ใบลง HP (คว่ำ)',su.hp?'':B('setup_hp','วาง HP',!su.drew))}
   ${row(su.ready,'5. พร้อมเริ่มเกม',su.ready?'':B('ready','พร้อม',!(su.placed&&su.drew&&su.hp&&st.first)))}
  </div><p class="mut" style="font-size:.85rem;margin:0">คู่ต่อสู้: ${op.setup.ready?'พร้อมแล้ว':'กำลังเตรียม…'}</p>`;
}
function gameHTML(st,opp){
  const mine=st.turn===ACT, PH=[['generate','Generate'],['combat','Combat'],['end','End']];
  let h=`<div class="row" style="margin-bottom:8px"><b class="mono">TURN ${(st.p[st.turn]||{}).turns||st.turn_no}</b><span class="turnmark">${mine?'เทิร์นของคุณ':'เทิร์นของ '+esc(nameOf(st.turn))}</span></div>
   <div class="phases">${PH.map(([k,l])=>`<span class="${st.phase===k?'on':''}">${l}</span>`).join('')}</div>`;
  if(!mine) return h+'<p class="mut">รอฝ่ายตรงข้ามเล่น… (คุณยังย้ายการ์ดของตัวเองได้)</p>';
  if(st.phase==='generate'){
    const own=st.p[ACT].turns, dice=DICE_TURNS.includes(own);
    h+=`<p style="margin:0 0 6px">Generate: จั่วการ์ด 1 ใบ และรับ 2 Code ทันที${dice?` <b style="color:var(--sig)">+ ทอยลูกเต๋า D4 เป็นโค้ดโบนัส (เทิร์นที่ ${own})</b>`:''}</p>
      <button class="btn pri sm" data-do="generate">Generate${dice?' + ทอย D4':''}</button>`;
  }
  if(st.phase==='combat'){
    const used=st.acts.length>=st.combat_no, A=[['summon','Summon'],['combat','Combat'],['move','Move']];
    h+=`<p style="margin:0 0 6px">Combat Phase ${st.combat_no}/2 — เลือกได้ 1 อย่างต่อเฟส</p>
     <div class="btns">${A.map(([k,l])=>`<button class="btn sm ${st.acts.includes(k)?'on':''}" data-do="ca" data-n="${k}" ${used&&!st.acts.includes(k)?'disabled':''}>${l}</button>`).join('')}</div>
     <div class="mut" style="font-size:.82rem">ใช้แล้ว: ${st.acts.length?st.acts.join(', '):'-'} · Summon จ่ายค่าคอสการ์ด · Move จ่าย 1 Code/ใบ</div>
     <div class="btns"><button class="btn sm" data-do="add_combat" ${st.combat_no>=2?'disabled':''}>+ Combat Phase</button><button class="btn sm" data-do="undo_act">ย้อนแอคชัน</button></div>`;
  }
  if(st.phase==='combat'&&st.acts.includes('combat')) h+=combatHTML(st,opp);
  return h+`<div class="btns"><button class="btn pri" data-do="end_turn">จบเทิร์น (End Phase)</button></div>`;
}
const NEU=['entity','partners'];
const cinfo=c=>(c&&!c.h&&S.cards[c.cid])||null;
const eff=c=>{const d=cinfo(c)||{}; let atk=d.atk||0,crit=d.crit||0,def=d.def||0;
  (c.links||[]).forEach(l=>{const li=S.cards[l.cid]||{}; atk+=li.link_atk||0; crit+=li.link_crit||0; def+=li.link_def||0;});
  const m=c.mod||{}; atk+=m.atk||0; crit+=m.crit||0; def+=m.def||0;
  return {atk:Math.max(0,atk),crit:Math.max(0,crit),def};};
const myField=st=>{const z=st.p[ACT].z; return z.attack.map(c=>[c,'A']).concat(st.p[ACT].protect_atk===false?[]:z.protect.map(c=>[c,'P'])).filter(([c])=>cinfo(c)&&NEU.includes(cinfo(c).type));};
function calcHit(A,T){
  const counter=S.rules?S.rules.counter:true, ae=eff(A), te=eff(T);
  const atk=ae.atk+bonusA, full=te.def+bonusD, rem=full-(T.dmg||0), after=rem-atk, kill=after<=0;
  const aRem=ae.def-(A.dmg||0), back=counter?te.atk:0, aAfter=aRem-back, aDie=counter&&aAfter<=0;
  return {counter,atk,full,rem,after,kill,back,aAfter,aDie,te,ae};
}
const hitText=(an,dn,k)=>`${an} โจมตี ${dn}: DEF ${k.rem} − ${k.atk} → ${k.kill?'ถูกทำลาย':'เหลือ '+k.after}${k.counter?` · สวนกลับ ${k.back} → ${k.aDie?'ผู้โจมตีถูกทำลาย':'ผู้โจมตีเหลือ '+k.aAfter}`:''}`;
function combatHTML(st,opp){
  const op=st.p[opp.uid], used=new Set(st.attacked||[]);
  const field=myField(st);
  combatOn=true;
  if(!field.length) return `<div class="combat"><b>ศึก (Combat)</b><p class="mut" style="margin:4px 0 0">ยังไม่มี Neurous บนสนามที่โจมตีได้ — ใช้ Summon ลงสนามก่อนในเฟสถัดไป</p></div>`;
  if(!field.some(([c])=>c.iid===atkSel)) atkSel=(field.find(([c])=>!used.has(c.iid))||field[0])[0].iid;
  const [A]=field.find(([c])=>c.iid===atkSel), ae=eff(A), spent=used.has(A.iid);
  const row=(t,zl)=>{
    const d=cinfo(t);
    if(!d) return `<div class="tg"><span class="nm">การ์ดคว่ำ (${zl})</span><button class="btn sm" data-do="atk" data-t="${t.iid}" ${spent?'disabled':''}>โจมตี</button></div>`;
    if(!NEU.includes(d.type)) return '';
    const k=calcHit(A,t);
    return `<div class="tg"><span class="nm">${esc(d.name)} <small>${zl}${(t.links||[]).length?` · Link ${(t.links||[]).length}`:''}</small></span><b>ATK ${k.te.atk} / DEF ${k.rem}${t.dmg?` <small>(${k.full}−${t.dmg})</small>`:''}</b>
      <button class="btn sm ${k.kill?'pri':''}" data-do="atk" data-t="${t.iid}" ${spent?'disabled':''}>โจมตี</button>
      <div class="calc"><span class="${k.kill?'ok':'no'}">DEF ${k.rem} − ${k.atk} → ${k.kill?'ถูกทำลาย':'เหลือ '+k.after}</span>
      ${k.counter?`<span class="${k.aDie?'bad':'mut'}">สวนกลับ ${k.back} → ${k.aDie?'ผู้โจมตีถูกทำลาย':'ผู้โจมตีเหลือ DEF '+k.aAfter}</span>`:''}</div></div>`;
  };
  const prot=op.z.protect, atkz=op.z.attack;
  const rows=prot.map(t=>row(t,'Protect')).join('')+atkz.map(t=>row(t,'Attack')).join('');
  const dmg=Math.max(1,ae.crit);
  const player=prot.length
    ? `<div class="tg"><span class="nm">ผู้เล่น ${esc(opp.name)}</span><b>HP ${op.z.hp.length}</b><button class="btn sm" disabled>โจมตีผู้เล่น</button>
        <div class="calc"><span class="mut">ต้องทำให้ Protect Zone ของฝั่งตรงข้ามว่างก่อน</span></div></div>`
    : `<div class="tg"><span class="nm">ผู้เล่น ${esc(opp.name)}</span><b>HP ${op.z.hp.length}</b>
        <button class="btn sm pri" data-do="atk" data-t="player" ${spent?'disabled':''}>โจมตีผู้เล่นโดยตรง</button>
        <div class="calc"><span class="ok">Protect Zone ว่าง → CRIT ${ae.crit} ลด HP −${dmg}</span></div></div>`;
  const chips=field.map(([c,zl])=>{const d=cinfo(c); return `<button class="chip ${c.iid===atkSel?'on':''} ${used.has(c.iid)?'used':''}" data-do="selatk" data-i="${c.iid}">${esc(d.name)} <b>ATK ${eff(c).atk}</b> <small>${zl==='A'?'Attack':'Protect'}</small>${used.has(c.iid)?' ✓':''}</button>`}).join('');
  return `<div class="combat"><b>ศึก (Combat)</b>
    <div class="mut" style="font-size:.8rem;margin:2px 0 6px">1) เลือกผู้โจมตี (Neurous ใบไหนก็ได้บนสนามเรา) — หรือคลิกการ์ดบนสนามเลย<br>2) เลือกเป้าหมาย: การ์ดใบไหนก็ได้บนสนามฝั่งตรงข้าม หรือผู้เล่นเมื่อ Protect Zone ว่าง (คลิกการ์ดที่กรอบแดงบนสนามเพื่อโจมตี)</div>
    <div class="chips">${chips}</div>
    <div class="btns">${protBtn(st)}</div>
    <div class="row" style="gap:6px;margin:8px 0;font-size:.85rem">ATK <b>${ae.atk}</b>${(A.links||[]).length?` <small class="mut">(รวม Link ${(A.links||[]).length})</small>`:''} + <input type="number" id="bA" value="${bonusA}" style="width:58px;padding:2px 6px"> เอฟเฟค · DEF เป้าหมาย + <input type="number" id="bD" value="${bonusD}" style="width:58px;padding:2px 6px"></div>
    ${spent?'<div class="mut" style="font-size:.85rem">ใบนี้โจมตีไปแล้วในเฟสนี้ — เลือกใบอื่น</div>':''}
    <div class="tgs">${rows}${player}</div>
    <div class="mut" style="font-size:.76rem;margin-top:6px">แบบ Hearthstone: ดาเมจ = ATK ของผู้โจมตี ลด DEF ของเป้าหมายแบบสะสม${S.rules&&S.rules.counter?' เป้าหมายสวนกลับด้วย ATK ของตัวเอง':''} · DEF เหลือ 0 = ถูกทำลาย ลง Delect · โจมตีตรง = ลด HP เท่าค่า CRIT (อย่างน้อย 1)</div></div>`;
}
function markCombat(){
  $$('.sel,.tgt').forEach(e=>e.classList.remove('sel','tgt'));
  if(!combatOn||!S.state) return;
  const el=$(`.half.me .card[data-iid="${atkSel}"]`); if(el) el.classList.add('sel');
  const {opp}=sides(), op=pst(opp); if(!op) return;
  $$('.half.opp .z-protect .card, .half.opp .z-attack .card').forEach(e=>e.classList.add('tgt'));
  if(!op.z.protect.length){const z=$('.half.opp .z-hp'); if(z) z.classList.add('tgt');}
}
function boardAttack(target){
  const st=S.state, {opp}=sides(), op=pst(opp);
  const f=myField(st).find(([c])=>c.iid===atkSel); if(!f) return toast('เลือกผู้โจมตีก่อน','err');
  const [A]=f, a=cinfo(A);
  if(st.attacked&&st.attacked.includes(A.iid)) return toast('ใบนี้โจมตีไปแล้วในเฟสนี้ เลือกใบอื่น','err');
  let text;
  if(target==='player') text=`${a.name} โจมตี ${opp.name} โดยตรง → HP −${Math.max(1,eff(A).crit)}`;
  else{const T=[...op.z.protect,...op.z.attack].find(c=>c.iid===target), d=cinfo(T);
    text=d?hitText(a.name,d.name,calcHit(A,T)):`${a.name} โจมตีการ์ดคว่ำ`;}
  if(confirm(text+'\n\nยืนยันโจมตี?')) act('attack',{iid:atkSel,target,atk_bonus:bonusA,def_bonus:bonusD});
}
function protBtn(st){const on=st.p[ACT].protect_atk!==false;
  return `<button class="btn sm ${on?'on':''}" data-do="protatk" title="เปิด/ปิด ให้ Neurous ใน Protect Zone ของเราโจมตีได้">Protect โจมตี${on?'ได้':'ไม่ได้'}</button>`;}
function toolsHTML(st){
  const play=st.phase!=='setup', mine=st.turn===ACT;
  return `<hr style="border:0;border-top:2px solid #6b6d72;margin:12px 0"><h3>เครื่องมือ Manual</h3>
   <div class="btns"><button class="btn sm" data-do="draw" data-n="1">จั่ว 1</button><button class="btn sm" data-do="shuffle">สับเด็ค</button>
   <button class="btn sm" data-do="peek" data-n="0">ค้นเด็ค</button><button class="btn sm" data-do="hp_hit" ${play?'':'disabled'}>HP −1</button></div>
   <div class="btns">${protBtn(st)}</div>
   <div class="btns"><button class="btn sm" data-do="code" data-d="-1">Code −1</button><button class="btn sm" data-do="code" data-d="1">Code +1</button></div>
   ${play&&mine?`<div class="btns"><span class="mut" style="font-size:.8rem">ข้ามไปเฟส:</span>${['generate','combat'].map(p=>`<button class="btn sm" data-do="phase" data-to="${p}">${p}</button>`).join('')}</div>`:''}
   <label class="row" style="font-size:.88rem"><input type="checkbox" id="optPay" ${autoPay?'checked':''}> หักค่าคอส/Code อัตโนมัติตอน Summon/Move</label>
   <label class="row" style="font-size:.88rem"><input type="checkbox" id="optFlip" ${flipLabels?'checked':''}> หมุนป้ายฝั่งตรงข้ามแบบเสื่อจริง</label>
   <div class="btns" style="margin-top:8px"><button class="btn sm" data-do="fullscreen" title="กด F ก็ได้">⛶ เต็มจอ</button><button class="btn sm dng" data-do="concede" ${play?'':'disabled'}>ยอมแพ้</button>${S.host===MYID?'<button class="btn sm" data-do="reset">รีเซ็ตเกม</button>':''}</div>`;
}
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-do]'); if(!b) return; const k=b.dataset.do;
  if(['place','setup_draw','mulligan','setup_hp','ready','shuffle','end_turn','add_combat','undo_act','hp_hit'].includes(k)) act(k);
  else if(k==='first') act('first',{who:b.dataset.who});
  else if(k==='generate') act('generate');
  else if(k==='fullscreen') toggleFS();
  else if(k==='protatk') act('protect_atk',{on:!(S.state&&S.state.p[ACT].protect_atk!==false)});
  else if(k==='draw') act('draw',{n:+b.dataset.n||1});
  else if(k==='peek') act('peek',{n:+b.dataset.n||0});
  else if(k==='ca') act('combat_act',{name:b.dataset.n});
  else if(k==='phase') act('phase',{to:b.dataset.to});
  else if(k==='code') act('code',{delta:+b.dataset.d});
  else if(k==='concede'){if(confirm('ยืนยันยอมแพ้?')) act('concede');}
  else if(k==='reset'){if(confirm('รีเซ็ตเกมและเริ่ม Setup ใหม่?')) act('reset');}
  else if(k==='selatk'){atkSel=+b.dataset.i;panel();markCombat();}
  else if(k==='atk') act('attack',{iid:atkSel,target:b.dataset.t==='player'?'player':+b.dataset.t,atk_bonus:bonusA,def_bonus:bonusD});
  else if(k==='swap'){const o=S.players.find(p=>p.uid!==ACT); if(o){ACT=o.uid;render();}}
  else if(k==='solo_setup') act('solo_setup');
  else if(k==='copylink') copyLink();
});
document.addEventListener('change',e=>{
  if(e.target.id==='bA'){bonusA=+e.target.value||0;panel();markCombat();}
  if(e.target.id==='bD'){bonusD=+e.target.value||0;panel();markCombat();}
  if(e.target.id==='optPay') autoPay=e.target.checked;
  if(e.target.id==='optFlip'){flipLabels=e.target.checked;$('#mat').classList.toggle('upright',!flipLabels);}
});
$('#chatf').addEventListener('submit',e=>{e.preventDefault();const i=$('#chat');if(i.value.trim())act('chat',{text:i.value});i.value='';});

/* ---------------- เมนูคลิกขวา/คลิกการ์ด ---------------- */
function closeCtx(){$('#ctx')?.remove();}
function showCtx(x,y,html,cb){
  closeCtx(); const d=document.createElement('div'); d.className='ctx'; d.id='ctx'; d.innerHTML=html;
  d.addEventListener('click',ev=>{const b=ev.target.closest('button'); if(b){cb(b);if(!b.dataset.keep)closeCtx();}});
  document.body.appendChild(d); const r=d.getBoundingClientRect();
  d.style.left=Math.max(6,Math.min(x,innerWidth-r.width-8))+'px'; d.style.top=Math.max(6,Math.min(y,innerHeight-r.height-8))+'px';
}
document.addEventListener('click',e=>{if(!e.target.closest('#ctx'))closeCtx();},true);
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){closeCtx();closeModal();closeZoom();mode=null;}
  else if((e.key==='f'||e.key==='F')&&!e.ctrlKey&&!e.metaKey&&!e.target.matches('input,textarea,select')) toggleFS();
});

function cardMenu(e,iid,zn){
  const inst=findInst(iid);
  const cid=inst?inst.cid:((document.querySelector(`.card[data-iid="${iid}"]`)||{dataset:{}}).dataset.cid);
  const cd=cid&&S.cards[cid];
  const D=[['hand','ขึ้นมือ'],['attack','Attack Zone'],['protect','Protect Zone'],['partners','Partners Zone'],['server','Server Zone'],['aura','Aura Zone'],['delect','Delect Zone'],['hp','HP (คว่ำ)']];
  let h=cd?`<button data-m="zoom">🔍 ดูการ์ดขยาย</button>`:'';
  if(['attack','protect','partners','server','aura'].includes(zn))
    h+=`<button data-m="tap">หมุน / ตั้งการ์ด (Tap)</button><button data-m="flip">พลิกหน้า / คว่ำ</button>`;
  if(['attack','protect'].includes(zn)&&cd&&NEU.includes(cd.type))
    h+=`<h4>ปรับค่าพลัง (บัพ / เดบัพ)</h4>
        <div class="g"><button data-keep="1" data-m="mod" data-s="atk" data-d="1">โจมตี +</button><button data-keep="1" data-m="mod" data-s="atk" data-d="-1">โจมตี −</button>
        <button data-keep="1" data-m="mod" data-s="crit" data-d="1">คริ +</button><button data-keep="1" data-m="mod" data-s="crit" data-d="-1">คริ −</button>
        <button data-keep="1" data-m="mod" data-s="def" data-d="1">ป้องกัน +</button><button data-keep="1" data-m="mod" data-s="def" data-d="-1">ป้องกัน −</button>
        <button data-keep="1" data-m="dmg" data-d="1">ดาเมจ +1</button><button data-keep="1" data-m="dmg" data-d="-1">ดาเมจ −1</button></div>
        <button data-keep="1" data-m="modclear">ล้างบัพทั้งหมด</button>`;
  if(zn==='hand') h+=`<button data-m="flip">เปิดเผย / ซ่อนจากฝ่ายตรงข้าม</button>`;
  if(cd&&cd.type==='ship'&&['hand','server','partners','attack','protect'].includes(zn)&&S.state){
    const tg=myField(S.state);
    h+=`<h4>Link กับ Neurous (ฟรี · ได้ไม่เกิน ${LINK_MAX} ใบต่อ Neurous)</h4>`+(tg.length?tg.map(([t])=>{const n=(t.links||[]).length;
      return `<button data-m="link" data-t="${t.iid}" ${n>=LINK_MAX?'disabled':''}>${esc(cinfo(t).name)} (${n}/${LINK_MAX})</button>`}).join(''):'<div class="mut" style="padding:2px 10px;font-size:.85rem">ยังไม่มี Neurous บนสนาม</div>');
  }
  if(inst&&(inst.links||[]).length&&['attack','protect'].includes(zn))
    h+=`<h4>ถอด Link</h4>`+inst.links.map(l=>`<div class="g"><button data-m="unlink" data-s="${l.iid}" data-to="delect">${esc((S.cards[l.cid]||{}).name)} → Delect</button><button data-m="unlink" data-s="${l.iid}" data-to="hand">→ มือ</button></div>`).join('');
  h+=`<h4>ย้ายไปที่</h4><div class="g">${D.filter(d=>d[0]!==zn).map(d=>`<button data-m="mv" data-to="${d[0]}">${d[1]}</button>`).join('')}
      <button data-m="mv" data-to="deck" data-pos="top">เด็ค (บนสุด)</button><button data-m="mv" data-to="deck" data-pos="bottom">เด็ค (ล่างสุด)</button></div>`;
  showCtx(e.clientX,e.clientY,h,b=>{
    const m=b.dataset.m;
    if(m==='zoom') return zoomCard(cid,iid);
    if(m==='mv') act('move',{iid,to:b.dataset.to,pos:b.dataset.pos,pay:autoPay});
    else if(m==='tap') act('tap',{iid}); else if(m==='flip') act('flip',{iid});
    else if(m==='mod') return act('mod',{iid,stat:b.dataset.s,delta:+b.dataset.d});
    else if(m==='modclear') return act('mod',{iid,stat:'clear'});
    else if(m==='dmg') return act('dmg',{iid,delta:+b.dataset.d});
    else if(m==='link') act('link',{iid,target:+b.dataset.t});
    else if(m==='unlink') act('unlink',{iid:+b.dataset.s,target:iid,to:b.dataset.to});
    closeModal();
  });
}
function stackMenu(e,stk){
  const zn=stk.dataset.stack, side=stk.dataset.side, mine=side==='me'&&seated, st=S.state;
  const {me,opp}=sides(), P=side==='me'?me:opp, p=pst(P);
  if(combatOn&&side==='opp'&&zn==='hp'){
    if(p.z.protect&&pst(sides().opp).z.protect.length) return toast('ต้องทำให้ Protect Zone ของฝั่งตรงข้ามว่างก่อน','err');
    return boardAttack('player');
  }
  if(zn==='delect') return openList(`Delect Zone ของ ${P.name}`,p.z.delect.slice().reverse(),'delect',side);
  if(!mine) return toast('ข้อมูลนี้ถูกซ่อนไว้');
  if(zn==='hp') return showCtx(e.clientX,e.clientY,`<button data-k="view">ดูการ์ดใน HP</button><button data-k="hit">HP −1 (ลงกอง Delect)</button>`,
    b=>b.dataset.k==='view'?openList('Firewall Zone (HP) ของคุณ',p.z.hp,'hp','me'):act('hp_hit'));
  showCtx(e.clientX,e.clientY,`<button data-k="d1">จั่ว 1 ใบ</button><button data-k="d2">จั่ว 2 ใบ</button><button data-k="sh">สับเด็ค</button>
    <button data-k="p3">ดูบนสุด 3 ใบ</button><button data-k="p5">ดูบนสุด 5 ใบ</button><button data-k="all">ค้นทั้งเด็ค</button>`,
    b=>({d1:()=>act('draw',{n:1}),d2:()=>act('draw',{n:2}),sh:()=>act('shuffle'),p3:()=>act('peek',{n:3}),p5:()=>act('peek',{n:5}),all:()=>act('peek',{n:0})})[b.dataset.k]());
}
function openList(title,items,zone,side='me'){
  $('#mtitle').textContent=`${title} (${items.length})`;
  $('#mlist').innerHTML=items.length?items.map(c=>cardEl({...c,up:true,tap:false,ctr:0},zone,side,false)).join(''):'<p class="mut">ว่าง</p>';
  $('#modal').classList.remove('hide');
}
function closeModal(){$('#modal').classList.add('hide');}
$('#mclose').onclick=closeModal;
$('#modal').addEventListener('click',e=>{if(e.target.id==='modal')closeModal();});

document.addEventListener('click',e=>{
  const stk=e.target.closest('.stack'); if(stk){stackMenu(e,stk);return;}
  const el=e.target.closest('.card[data-iid]'); if(!el) return;
  inspect(el);
  if(combatOn&&el.dataset.side==='opp'&&(el.dataset.zone==='attack'||el.dataset.zone==='protect')){boardAttack(+el.dataset.iid);return;}
  if(el.dataset.side!=='me'||!seated) return;
  const iid=+el.dataset.iid, zn=el.dataset.zone;
  if(mode==='discard'&&zn==='hand'){mode=null;act('generate',{iid});return;}
  if(combatOn&&(zn==='attack'||zn==='protect')){   // ระหว่าง Combat: คลิกการ์ดเราเพื่อเลือกผู้โจมตี (คลิกขวาเปิดเมนูปกติ)
    const d=S.cards[el.dataset.cid]; if(d&&NEU.includes(d.type)){atkSel=iid;panel();markCombat();return;}
  }
  cardMenu(e,iid,zn);
});
document.addEventListener('contextmenu',e=>{const el=e.target.closest('.card[data-iid][data-side="me"]'); if(el&&seated){e.preventDefault();cardMenu(e,+el.dataset.iid,el.dataset.zone);}});

/* ---------------- ดูรายละเอียดการ์ด ---------------- */
const instIndex=()=>{const m={}; if(!S||!S.state) return m;
  for(const uid in S.state.p){const z=S.state.p[uid].z; for(const zn in z){const arr=z[zn]; if(!Array.isArray(arr)) continue;
    arr.forEach(c=>{m[c.iid]=c; (c.links||[]).forEach(l=>{m[l.iid]=l;});});}}
  return m;};
const findInst=iid=>instIndex()[iid]||null;
function detailHTML(cd,inst){
  const neu=NEU.includes(cd.type), e=inst&&neu?eff(inst):null, sg=n=>(n>=0?'+':'')+n;
  let stats='';
  if(neu) stats=`<div class="isr"><span>ATK <b>${e?e.atk:cd.atk}</b></span><span>CRIT <b>${e?e.crit:cd.crit}</b></span><span>DEF <b>${e?e.def-(inst.dmg||0):cd.def}</b>${inst&&inst.dmg?` <small>/ ${e.def}</small>`:''}</span></div>`;
  else if(cd.type==='ship') stats=`<div class="isr"><span>Link ATK <b>${sg(cd.link_atk)}</b></span><span>CRIT <b>${sg(cd.link_crit)}</b></span><span>DEF <b>${sg(cd.link_def)}</b></span></div>`;
  const lk=inst&&(inst.links||[]).length?`<div class="islk"><b>Link ${inst.links.length}/${LINK_MAX}</b>${inst.links.map(l=>{const li=S.cards[l.cid]||{};
    return `<div>${esc(li.name)} <small>ATK ${sg(li.link_atk||0)} · CRIT ${sg(li.link_crit||0)} · DEF ${sg(li.link_def||0)}</small></div>`}).join('')}</div>`:'';
  const m=(inst&&inst.mod)||{}, buff=(m.atk||m.crit||m.def)?`<div class="imeta">บัพ/เดบัพ: ATK ${sg(m.atk||0)} · CRIT ${sg(m.crit||0)} · DEF ${sg(m.def||0)}</div>`:'';
  return `<div class="iname">${esc(cd.name)}</div><div class="imeta">${TYPE_LABEL[cd.type]||cd.type} · Cost ${cd.cost}${cd.server?' · '+esc(cd.server):''}</div>${stats}${buff}${lk}
    <div class="ieff">${esc(cd.effect)||'<span class="mut">ไม่มีเอฟเฟค</span>'}</div>`;
}
function inspect(el){
  const box=$('#inspect'), cd=el.dataset.cid&&S&&S.cards[el.dataset.cid];
  if(!cd){box.innerHTML=`<div class="card back ${SLEEVE[el.dataset.side]?'img':''}" ${SLEEVE[el.dataset.side]?`style="background-image:url('${esc(SLEEVE[el.dataset.side])}')"`:''}>${SLEEVE[el.dataset.side]?'':'<i>DD</i>'}</div><p class="mut">การ์ดที่ถูกซ่อน</p>`;return;}
  const iid=+el.dataset.iid||0, inst=iid?findInst(iid):null;
  box.innerHTML=cardHTML(cd,{attrs:`data-zoom="${cd.id}" data-ziid="${iid}"`})+`<div class="itext">${detailHTML(cd,inst)}<div class="ihint">คลิกที่การ์ดเพื่อดูขยาย</div></div>`;
}
function zoomCard(cid,iid){
  const cd=S&&S.cards[cid]; if(!cd) return;
  $('#zcard').innerHTML=cardHTML(cd,{big:true}); $('#ztext').innerHTML=detailHTML(cd,iid?findInst(+iid):null);
  $('#zoom').classList.remove('hide');
}
const closeZoom=()=>$('#zoom').classList.add('hide');
$('#zclose').onclick=closeZoom;
$('#zoom').addEventListener('click',e=>{if(e.target.id==='zoom')closeZoom();});
document.addEventListener('click',e=>{const z=e.target.closest('#inspect .card[data-zoom]'); if(z) zoomCard(+z.dataset.zoom,z.dataset.ziid);});
document.addEventListener('dblclick',e=>{const el=e.target.closest('.card[data-iid][data-cid]'); if(el){closeCtx();zoomCard(+el.dataset.cid,+el.dataset.iid);}});

/* ---------- ลูกเต๋า D4 ---------- */
function showDice(r){
  $('#dice')?.remove();
  const el=document.createElement('div'); el.id='dice'; el.className='dice-ov';
  el.innerHTML=`<div class="d4wrap"><div class="d4"><span class="d4n">4</span></div><div class="d4cap">${esc(nameOf(r.uid))} ทอยลูกเต๋า D4…</div></div>`;
  document.body.appendChild(el); if(window.sfx) sfx('dice');
  const n=$('.d4n',el), cap=$('.d4cap',el), die=$('.d4',el);
  const iv=setInterval(()=>{n.textContent=1+Math.floor(Math.random()*4);},70);
  setTimeout(()=>{clearInterval(iv); n.textContent=r.v; die.classList.add('land'); if(window.sfx) sfx('land'); cap.innerHTML=`<b>${r.v}</b> → โบนัส +${r.v} Code`;},1300);
  setTimeout(()=>{el.classList.add('out'); setTimeout(()=>el.remove(),500);},3300);
}

/* ---------- เต็มจอ + แท็บเครื่องมือด้านซ้าย ---------- */
function toggleFS(){
  if(document.fullscreenElement){document.exitFullscreen();return;}
  const b=document.body, de=document.documentElement;
  if(de.requestFullscreen) de.requestFullscreen().catch(()=>b.classList.toggle('fs')); else b.classList.toggle('fs');
}
document.addEventListener('fullscreenchange',()=>{
  document.body.classList.toggle('fs',!!document.fullscreenElement);
  if(!document.fullscreenElement) document.body.classList.remove('drawer-open');
});
$('#fsBtn').onclick=toggleFS;
$('#drawerTab').onclick=()=>document.body.classList.toggle('drawer-open');
document.addEventListener('mouseover',e=>{const el=e.target.closest('.card[data-iid]'); if(el&&S) inspect(el);});

/* ---------------- ลากวางการ์ด ---------------- */
const mineZone=z=>z&&seated&&(z.id==='hand'||z.closest('.half.me')||z.dataset.side==='me');
document.addEventListener('dragstart',e=>{const c=e.target.closest('.card[draggable="true"]'); if(!c) return;
  dragIid=+c.dataset.iid; dragCid=c.dataset.cid; dragZone=c.dataset.zone; e.dataTransfer.setData('text/plain',String(dragIid)); e.dataTransfer.effectAllowed='move';});
document.addEventListener('dragover',e=>{const z=e.target.closest('.zone,#hand'); if(mineZone(z)){e.preventDefault();z.classList.add('over');}});
document.addEventListener('dragleave',e=>{e.target.closest?.('.zone,#hand')?.classList.remove('over');});
document.addEventListener('drop',e=>{
  const tc=e.target.closest('.card[data-iid]');          // ลากการ์ด Ship ไปวางบน Neurous = Link
  if(tc&&seated&&tc.dataset.side==='me'&&['attack','protect'].includes(tc.dataset.zone)&&dragIid!=null&&+tc.dataset.iid!==dragIid
     &&S.cards[dragCid]&&S.cards[dragCid].type==='ship'&&dragZone!=='aura'){
    e.preventDefault(); $$('.over').forEach(x=>x.classList.remove('over'));
    act('link',{iid:dragIid,target:+tc.dataset.iid}); dragIid=null; return;
  }
  const z=e.target.closest('.zone,#hand'); if(!mineZone(z)) return; e.preventDefault();
  $$('.over').forEach(x=>x.classList.remove('over'));
  if(dragIid!=null) act('move',{iid:dragIid,to:z.dataset.zone,pay:autoPay}); dragIid=null;
});
document.addEventListener('dragend',()=>$$('.over').forEach(x=>x.classList.remove('over')));

initTrack();
})();
