// เสียงประกอบทั้งเว็บ: เพลงเพลย์ลิสต์ที่ Admin อัปโหลด + เสียงเอฟเฟคสังเคราะห์ (ไม่ต้องใช้ไฟล์)
(()=>{
  const LS=(()=>{try{return window.localStorage}catch(e){return null}})();
  const get=(k,d)=>{try{const v=LS.getItem(k);return v===null?d:v}catch(e){return d}};
  const set=(k,v)=>{try{LS.setItem(k,String(v))}catch(e){}};
  const $=id=>document.getElementById(id);
  const btn=$('sndBtn'), nxt=$('sndNext'), vol=$('sndVol'), nm=$('sndName'); if(!btn) return;
  let on=get('snd_on','1')==='1', volume=Math.min(1,Math.max(0,+get('snd_vol','50')/100)), tracks=[], idx=+get('snd_idx','0')||0, fails=0, ac=null, lastSave=0;
  const audio=new Audio(); audio.preload='none'; audio.volume=volume;
  vol.value=Math.round(volume*100);

  function render(){
    btn.textContent=on?'🔊':'🔇'; btn.classList.toggle('off',!on);
    const t=tracks[idx]; nm.textContent=on&&t?'♪ '+t.title:''; nxt.style.display=tracks.length>1?'':'none';
  }
  function playCurrent(resume){
    if(!on||!tracks.length) return;
    const t=tracks[idx]; if(!audio.src||!audio.src.endsWith(t.url)) audio.src=t.url;
    if(resume&&get('snd_trk','')===String(t.id)){const p=+get('snd_pos','0'); if(p>0&&audio.readyState===0) audio.addEventListener('loadedmetadata',()=>{try{audio.currentTime=p}catch(e){}},{once:true});}
    audio.play().catch(()=>{});
  }
  function next(){
    if(!tracks.length) return; idx=(idx+1)%tracks.length; set('snd_idx',idx); set('snd_pos',0); set('snd_trk',tracks[idx].id);
    audio.src=tracks[idx].url; render(); if(on) audio.play().catch(()=>{});
  }
  audio.addEventListener('ended',()=>{fails=0;next();});
  audio.addEventListener('error',()=>{if(++fails<=tracks.length) setTimeout(next,400);});
  audio.addEventListener('timeupdate',()=>{const n=Date.now(); if(n-lastSave>3000&&tracks[idx]){lastSave=n;set('snd_pos',audio.currentTime.toFixed(1));set('snd_trk',tracks[idx].id);}});

  // ----- เสียงเอฟเฟคสังเคราะห์ด้วย WebAudio -----
  function ctx(){ if(!ac){const C=window.AudioContext||window.webkitAudioContext; if(C) ac=new C();} if(ac&&ac.state==='suspended') ac.resume(); return ac; }
  function tone(f,t0,dur,type,g,f2){
    const c=ctx(); if(!c) return; const o=c.createOscillator(), gn=c.createGain(), t=c.currentTime+t0;
    o.type=type||'sine'; o.frequency.setValueAtTime(f,t); if(f2) o.frequency.exponentialRampToValueAtTime(f2,t+dur);
    gn.gain.setValueAtTime(Math.max(.0002,(g||.2)*volume),t); gn.gain.exponentialRampToValueAtTime(.0001,t+dur);
    o.connect(gn); gn.connect(c.destination); o.start(t); o.stop(t+dur+.03);
  }
  const FX={
    click:()=>tone(720,0,.07,'triangle',.3,480),
    hit:()=>{tone(190,0,.24,'sawtooth',.4,50);tone(95,0,.28,'square',.25,40);},
    turn:()=>{tone(523,0,.14,'sine',.35);tone(784,.15,.24,'sine',.35);},
    dice:()=>{for(let i=0;i<10;i++) tone(420+Math.random()*420,i*.09+i*i*.007,.05,'square',.18);},
    land:()=>{tone(392,0,.12,'triangle',.4);tone(587,.11,.28,'triangle',.4);}
  };
  window.sfx=name=>{ if(on&&FX[name]) try{FX[name]();}catch(e){} };

  btn.addEventListener('click',()=>{on=!on; set('snd_on',on?1:0); if(on){ctx();playCurrent(true);} else audio.pause(); render();});
  nxt.addEventListener('click',()=>{if(!on){on=true;set('snd_on',1);} next(); ctx();});
  vol.addEventListener('input',()=>{volume=vol.value/100; audio.volume=volume; set('snd_vol',vol.value);});
  // เบราว์เซอร์บล็อกเสียงอัตโนมัติ: เริ่มเล่นเมื่อผู้ใช้คลิก/กดครั้งแรกบนหน้า
  const unlock=()=>{ctx(); if(on&&audio.paused) playCurrent(true); document.removeEventListener('pointerdown',unlock); document.removeEventListener('keydown',unlock);};
  document.addEventListener('pointerdown',unlock); document.addEventListener('keydown',unlock);

  fetch('/api/music').then(r=>r.json()).then(l=>{tracks=l||[]; if(idx>=tracks.length) idx=0; render();}).catch(()=>{render();});
  render();
})();
