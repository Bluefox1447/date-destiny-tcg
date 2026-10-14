// ตัวช่วยกลางที่ใช้ร่วมกันทุกหน้า
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function toast(msg,kind){
  const box=document.getElementById('flash'); if(!box) return;
  const d=document.createElement('div'); d.className=kind||''; d.textContent=msg; box.appendChild(d);
  setTimeout(()=>d.remove(),4200);
}
setTimeout(()=>document.querySelectorAll('#flash div').forEach(d=>d.remove()),5000);

const TYPE_LABEL={entity:'Entity',partners:'Partners',ship:'Ship',server:'Server'};
const COLOR_HEX={red:'#d4505a',blue:'#4b8de0',green:'#3fb27d',yellow:'#e2b832',purple:'#9a62d0',black:'#55565f',white:'#e9ebef',none:'#8a8d93'};

/** วาดการ์ดด้วย HTML/CSS (ใช้ภาพที่ Admin อัปโหลดถ้ามี) */
function cardHTML(c,o={}){
  if(!c) return '';
  if(c.image){   // Admin อัปโหลดภาพการ์ดสำเร็จรูป → แสดงภาพนั้นเป็นตัวการ์ดเลย
    const cls=['card','img','t-'+c.type,o.mini?'mini':'',o.big?'big':'',o.cls||''].join(' ');
    return `<div class="${cls}" ${o.attrs||''} title="${esc(c.name)}" style="background-image:url('${esc(c.image)}')">${o.ctr?`<span class="ctr">${o.ctr>0?'+':''}${o.ctr}</span>`:''}${o.dmg?`<span class="dmg">−${o.dmg}</span>`:''}</div>`;
  }
  const stats=c.type==='entity'
    ? `<span title="พลังโจมตี">ATK ${c.atk}</span><span title="คริ">CRT ${c.crit}</span><span title="ป้องกัน">DEF ${c.def}</span>`
    : c.type==='ship'
    ? `<span title="Link โจมตี">L1 ${c.link_atk}</span><span title="Link คริ">L2 ${c.link_crit}</span><span title="Link ป้องกัน">L3 ${c.link_def}</span>` : '';
  const art=c.image?` has" style="background-image:url('${esc(c.image)}')`:'';
  const cls=['card','c-'+c.color,'t-'+c.type,o.mini?'mini':'',o.big?'big':'',o.cls||''].join(' ');
  return `<div class="${cls}" ${o.attrs||''} title="${esc(c.name)}">
    ${o.ctr?`<span class="ctr">${o.ctr>0?'+':''}${o.ctr}</span>`:''}${o.dmg?`<span class="dmg">−${o.dmg}</span>`:''}
    <div class="cc-top"><span class="cc-cost">${c.cost}</span><span class="cc-name">${esc(c.name)}</span></div>
    <div class="cc-art${art}"></div>
    <div class="cc-type"><span>${TYPE_LABEL[c.type]||c.type}</span><span>${esc(c.server)}</span></div>
    <div class="cc-effect">${esc(c.effect)||'&nbsp;'}</div>
    <div class="cc-stats">${stats}</div></div>`;
}
