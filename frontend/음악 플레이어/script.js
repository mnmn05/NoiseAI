const $=id=>document.getElementById(id);
const T=[
{title:'새벽 산책',artist:'생성 음악 · 72 BPM',hue:170,spec:{bpm:72,root:57,scale:[0,3,5,7,10],lead:'triangle',pad:'sine',prog:[0,3,2,4],density:.55,drums:0,seed:11}},
{title:'네온 드라이브',artist:'생성 음악 · 110 BPM',hue:300,spec:{bpm:110,root:50,scale:[0,2,3,5,7,8,10],lead:'sawtooth',pad:'triangle',prog:[0,5,3,4],density:.75,drums:2,seed:23}},
{title:'비 오는 창가',artist:'생성 음악 · 60 BPM',hue:215,spec:{bpm:60,root:52,scale:[0,2,4,5,7,9,11],lead:'sine',pad:'sine',prog:[0,4,5,3],density:.4,drums:0,seed:5}},
{title:'오후의 카페',artist:'생성 음악 · 92 BPM',hue:35,spec:{bpm:92,root:60,scale:[0,2,4,7,9],lead:'triangle',pad:'sine',prog:[0,2,3,1],density:.65,drums:1,seed:42}}
];
let ac,gain,an,src=null,cur=0,buf=null,dur=0,t0=0,off=0,playing=false,shuf=false,rep=false;

function render(sp){
  const sr=22050,beat=60/sp.bpm,bars=Math.ceil(32/(beat*4)),len=bars*beat*4;
  const oc=new OfflineAudioContext(2,Math.ceil(len*sr),sr);
  const m=oc.createGain();m.gain.setValueAtTime(0,0);m.gain.linearRampToValueAtTime(.6,.3);m.gain.setValueAtTime(.6,len-.6);m.gain.linearRampToValueAtTime(0,len);m.connect(oc.destination);
  let s=sp.seed;const rnd=()=>(s=s*16807%2147483647)/2147483647;
  const f=x=>440*2**((x-69)/12),n=sp.scale.length;
  const deg=d=>sp.root+sp.scale[((d%n)+n)%n]+12*Math.floor(d/n);
  const note=(t,x,l,type,v,pan,sus)=>{const o=oc.createOscillator(),g=oc.createGain(),p=oc.createStereoPanner();
    o.type=type;o.frequency.value=f(x);p.pan.value=pan||0;
    g.gain.setValueAtTime(0,t);
    if(sus){g.gain.linearRampToValueAtTime(v,t+.4);g.gain.setValueAtTime(v,t+l-.4);g.gain.linearRampToValueAtTime(0,t+l)}
    else{g.gain.linearRampToValueAtTime(v,t+.02);g.gain.exponentialRampToValueAtTime(.001,t+l)}
    o.connect(g);g.connect(p);p.connect(m);o.start(t);o.stop(t+l+.05)};
  const nb=oc.createBuffer(1,sr/10,sr),nd=nb.getChannelData(0);for(let i=0;i<nd.length;i++)nd[i]=rnd()*2-1;
  for(let b=0;b<bars;b++){
    const t0=b*beat*4,d=sp.prog[b%4];
    [0,2,4].forEach(k=>note(t0,deg(d+k),beat*4,sp.pad,.05,k-2?0:0,true));
    [0,2].forEach(i=>note(t0+i*beat,deg(d)-12,beat*1.8,'sine',.28));
    for(let i=0;i<8;i++){if(rnd()<sp.density){const idx=d+[0,2,4,5,7][Math.floor(rnd()*5)];
      note(t0+i*beat/2,deg(idx)+12,beat*.9,sp.lead,sp.lead==='sawtooth'?.04:.09,rnd()*1.2-.6)}}
    if(sp.drums){
      for(let i=0;i<8;i++){const t=t0+i*beat/2,h=oc.createBufferSource(),hf=oc.createBiquadFilter(),hg=oc.createGain();
        h.buffer=nb;hf.type='highpass';hf.frequency.value=7000;hg.gain.setValueAtTime(.05,t);hg.gain.exponentialRampToValueAtTime(.001,t+.06);
        h.connect(hf);hf.connect(hg);hg.connect(m);h.start(t);}
      if(sp.drums>1)for(let i=0;i<4;i++){const t=t0+i*beat,o=oc.createOscillator(),g=oc.createGain();
        o.frequency.setValueAtTime(130,t);o.frequency.exponentialRampToValueAtTime(40,t+.15);
        g.gain.setValueAtTime(.5,t);g.gain.exponentialRampToValueAtTime(.001,t+.25);o.connect(g);g.connect(m);o.start(t);o.stop(t+.3)}
    }
  }
  return oc.startRendering();
}

const fmt=x=>{x=Math.max(0,x|0);return Math.floor(x/60)+':'+String(x%60).padStart(2,'0')};
const pos=()=>playing?Math.min(ac.currentTime-t0,dur):off;
function setMsg(t){$('msg').textContent=t}
function ensureAC(){
  if(!ac){ac=new(window.AudioContext||window.webkitAudioContext)();gain=ac.createGain();an=ac.createAnalyser();an.fftSize=128;
    gain.gain.value=$('vol').value/100;an.connect(gain);gain.connect(ac.destination)}
  if(ac.state==='suspended')ac.resume();
}
function ui(){
  const t=T[cur];$('title').textContent=t.title;$('artist').textContent=t.artist;
  $('disc').style.setProperty('--h',t.hue);$('disc').classList.toggle('on',playing);
  $('play').setAttribute('aria-label',playing?'일시정지':'재생');
  $('pi').innerHTML=playing?'<path d="M6 4h4v16H6zM14 4h4v16h-4z"/>':'<path d="M7 4v16l13-8z"/>';
  $('list').querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-current',i===cur));
}
function list(){
  $('list').innerHTML='';
  T.forEach((t,i)=>{const li=document.createElement('li'),b=document.createElement('button');
    b.innerHTML='<span>'+t.title.replace(/</g,'&lt;')+'<small>'+t.artist.replace(/</g,'&lt;')+'</small></span><span class="d">'+(t.buf?fmt(t.buf.duration):'')+'</span>';
    b.onclick=()=>{ensureAC();load(i,true)};li.appendChild(b);$('list').appendChild(li)});
  ui();
}
function halt(){const s=src;src=null;if(s){s.onended=null;try{s.stop()}catch(e){}}}
function play(){
  if(!buf)return;ensureAC();if(off>=dur-.05)off=0;halt();
  const s=ac.createBufferSource();s.buffer=buf;s.connect(an);
  s.onended=()=>{if(s!==src)return;src=null;playing=false;off=0;go(1,true)};
  s.start(0,off);src=s;t0=ac.currentTime-off;playing=true;ui();
}
function pause(){if(!playing)return;off=pos();halt();playing=false;ui()}
async function load(i,auto){
  halt();playing=false;off=0;cur=i;buf=null;dur=0;ui();$('dur').textContent='0:00';$('seek').value=0;
  const t=T[i];
  if(!t.buf){setMsg('곡을 준비하는 중이에요…');try{t.buf=await render(t.spec)}catch(e){setMsg('이 곡을 만들지 못했어요.');return}}
  if(cur!==i)return;
  buf=t.buf;dur=buf.duration;$('dur').textContent=fmt(dur);setMsg('');list();
  if(auto)play();
}
function go(d,auto){
  if(auto&&rep){load(cur,true);return}
  let n;if(shuf&&T.length>1){do{n=Math.floor(Math.random()*T.length)}while(n===cur)}else n=(cur+d+T.length)%T.length;
  load(n,playing||auto);
}
$('play').onclick=()=>{ensureAC();playing?pause():play()};
$('next').onclick=()=>{ensureAC();go(1,false)};
$('prev').onclick=()=>{ensureAC();if(pos()>3&&buf){off=0;playing?play():ui()}else go(-1,false)};
$('shuf').onclick=e=>{shuf=!shuf;e.currentTarget.setAttribute('aria-pressed',shuf)};
$('rep').onclick=e=>{rep=!rep;e.currentTarget.setAttribute('aria-pressed',rep)};
$('seek').oninput=e=>{if(!buf)return;off=e.target.value/1000*dur;if(playing)play()};
$('vol').oninput=e=>{if(gain)gain.gain.value=e.target.value/100};
$('file').onchange=async e=>{
  ensureAC();let ok=0;
  for(const f of e.target.files){
    try{const b=await ac.decodeAudioData(await f.arrayBuffer());
      T.push({title:f.name.replace(/\.[^.]+$/,''),artist:'내 파일',hue:Math.floor(Math.random()*360),buf:b});ok++}
    catch(err){setMsg('“'+f.name+'” 파일은 재생할 수 없어요. mp3, wav, m4a, ogg 파일을 사용해 주세요.')}
  }
  if(ok){list();setMsg(ok+'곡을 추가했어요.')}
  e.target.value='';
};
document.addEventListener('keydown',e=>{if(e.code==='Space'&&e.target===document.body){e.preventDefault();$('play').click()}});

const cv=$('viz'),cx=cv.getContext('2d');
function frame(){
  const css=getComputedStyle(document.documentElement),col=css.getPropertyValue('--accent').trim()||'#1f6b57';
  cx.clearRect(0,0,cv.width,cv.height);cx.fillStyle=col;
  const N=40,w=cv.width/N,data=new Uint8Array(an?an.frequencyBinCount:64);
  if(an&&playing)an.getByteFrequencyData(data);
  for(let i=0;i<N;i++){const h=Math.max(4,data[i]/255*cv.height*.95);cx.globalAlpha=playing?1:.35;
    cx.fillRect(i*w+3,cv.height-h,w-6,h)}
  if(buf){const p=pos();$('cur').textContent=fmt(p);$('seek').value=Math.round(p/dur*1000)}
  requestAnimationFrame(frame);
}
list();load(0,false);frame();
