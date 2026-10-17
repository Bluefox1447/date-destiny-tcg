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
function badges(o){
  const b=[];
  const m=o.mod||{}, md=[['atk','โจมตี','A'],['crit','คริ','C'],['def','ป้องกัน','D']].filter(([k])=>m[k]).map(([k,n,l])=>`${l}${m[k]>0?'+':''}${m[k]}`);
  if(md.length) b.push(`<span class="mod" title="บัพ/เดบัพ (โจมตี A · คริ C · ป้องกัน D)">${md.join(' ')}</span>`);
  if(o.ctr) b.push(`<span class="ctr" title="ตัวนับ / บัพ">${o.ctr>0?'+':''}${o.ctr}</span>`);
  if(o.dmg) b.push(`<span class="dmg" title="ดาเมจที่ได้รับ">−${o.dmg}</span>`);
  if(o.lnk) b.push(`<span class="lnk" title="Ship ที่ Link อยู่">🔗${o.lnk}/3</span>`);
  return b.length?`<div class="bdg">${b.join('')}</div>`:'';
}
function cardHTML(c,o={}){
  if(!c) return '';
  if(c.image){   // Admin อัปโหลดภาพการ์ดสำเร็จรูป → แสดงภาพนั้นเป็นตัวการ์ดเลย
    const cls=['card','img','t-'+c.type,o.mini?'mini':'',o.big?'big':'',o.cls||''].join(' ');
    // รวม style เป็นอันเดียว (เบราว์เซอร์ใช้ style แรกอันเดียว ถ้าซ้ำรูปการ์ดจะหาย)
    let st=`background-image:url('${esc(c.image)}')`, at=(o.attrs||'').replace(/\stitle="[^"]*"/g,'');
    at=at.replace(/\sstyle="([^"]*)"/g,(m,x)=>{st+=';'+x;return '';});
    return `<div class="${cls}" ${at} title="${esc(c.name)}" style="${st}">${badges(o)}</div>`;
  }
  const stats=c.type==='entity'||c.type==='partners'
    ? `<span title="พลังโจมตี">ATK ${c.atk}</span><span title="คริ">CRT ${c.crit}</span><span title="ป้องกัน">DEF ${c.def}</span>`
    : c.type==='ship'
    ? `<span title="Link โจมตี">L1 ${c.link_atk}</span><span title="Link คริ">L2 ${c.link_crit}</span><span title="Link ป้องกัน">L3 ${c.link_def}</span>` : '';
  const cls=['card','c-'+c.color,'t-'+c.type,o.mini?'mini':'',o.big?'big':'',o.cls||''].join(' ');
  return `<div class="${cls}" ${o.attrs||''} title="${esc(c.name)}">
    ${badges(o)}
    <div class="cc-top"><span class="cc-cost">${c.cost}</span><span class="cc-name">${esc(c.name)}</span></div>
    <div class="cc-art"></div>
    <div class="cc-type"><span>${TYPE_LABEL[c.type]||c.type}</span><span>${esc(c.server)}</span></div>
    <div class="cc-effect">${esc(c.effect)||'&nbsp;'}</div>
    <div class="cc-stats">${stats}</div></div>`;
}
