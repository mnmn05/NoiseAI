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
  if(!buf)return;ensureAC();if(off>=dur-.05)off=0;halt();const fresh=off<.05;
  const s=ac.createBufferSource();s.buffer=buf;s.connect(an);
  s.onended=()=>{if(s!==src)return;src=null;playing=false;off=0;advance()};
  s.start(0,off);src=s;t0=ac.currentTime-off;playing=true;ui();
  if(fresh)onTrackStart(T[cur]);
}

function pause(){if(!playing)return;off=pos();halt();playing=false;ui()}
async function load(i,auto){
  halt();playing=false;off=0;cur=i;buf=null;dur=0;ui();$('dur').textContent='0:00';$('seek').value=0;
  const t=T[i];
  if(!t.buf){setMsg('곡을 준비하는 중이에요…');try{t.buf=t.url?await fetchBuf(t.url):await render(t.spec)}catch(e){setMsg('이 곡을 불러오지 못했어요. '+(e.message||''));return}}
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
$('vol').oninput=e=>{if(gain){gain.gain.cancelScheduledValues(0);gain.gain.value=e.target.value/100}if($('autovol').checked){$('autovol').checked=false;volInfo('직접 조절 중 (자동 볼륨 꺼짐)')}};

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

const API=window.NoiseAPI, srv=API&&API.session().token?API.session().user:null;
function srvMsg(t,bad){const el=$('srv');if(!el)return;el.textContent=t;el.style.color=bad?'#c0392b':''}
function volInfo(t){$('volinfo').textContent=t}
async function fetchBuf(url){
  const r=await fetch(url);
  if(!r.ok)throw new Error('음원 응답 '+r.status);
  const ab=await r.arrayBuffer();
  return await new OfflineAudioContext(2,1,44100).decodeAudioData(ab);
}
// 곡 시작 = 다음 AI 곡 생성 요청 (서버가 중복 요청은 막아 줌)
async function onTrackStart(t){
  if(!srv)return;
  if(t&&t.aiId){API.markPlayed(t.aiId).catch(()=>{})}
  try{
    const g=await API.generateTrack(null);
    srvMsg(g.already_generating?'다음 AI 곡을 만드는 중이에요':'다음 AI 곡 생성을 요청했어요 (#'+g.id+')');
  }catch(e){srvMsg('AI 곡 생성 요청 실패: '+e.message,true)}
}
// 곡이 끝나면: 완성된 AI 곡이 있으면 그걸, 없으면 다음 기본곡
let advancing=false;
async function advance(){
  if(advancing)return;advancing=true;
  try{
    if(srv&&!rep){
      let nt=null;
      try{nt=await API.nextTrack()}catch(e){srvMsg('AI 곡 확인 실패: '+e.message,true)}
      if(nt&&nt.audio_url&&!T.some(x=>x.aiId===nt.id)){
        T.splice(cur+1,0,{title:'AI 생성곡 #'+nt.id,artist:(nt.prompt||'').slice(0,60),hue:(nt.id*47)%360,url:API.absUrl(nt.audio_url),aiId:nt.id});
        list();await load(cur+1,true);return;
      }
    }
    go(1,true);
  }finally{advancing=false}
}
async function loadBgm(){
  try{
    const r=await API.bgmPlaylist();
    const ok=(r.tracks||[]).filter(x=>x.available);
    if(!ok.length){srvMsg('서버에 기본 BGM 파일이 없어서 내장 생성음악으로 시작해요');return false}
    T.splice(0,T.length,...ok.map((x,i)=>({title:x.title,artist:'기본 BGM · '+x.tags.slice(0,3).join(', '),hue:(i*67+20)%360,url:API.absUrl(x.url)})));
    srvMsg('기본 BGM '+ok.length+'곡 → 이후 AI 생성곡이 이어서 재생돼요');
    return true;
  }catch(e){srvMsg('기본 BGM 목록을 못 받았어요: '+e.message,true);return false}
}
// 3초마다 서버 볼륨 반영 (상한 넘지 않게, 1초 동안 부드럽게)
async function pollVolume(){
  try{
    const s=await API.status();
    const target=Math.min(s.current_volume,s.max_volume==null?100:s.max_volume);
    if($('autovol').checked){
      $('vol').value=target;
      if(gain&&ac){const g=gain.gain,t=ac.currentTime;g.cancelScheduledValues(t);g.setValueAtTime(g.value,t);g.linearRampToValueAtTime(target/100,t+1)}
      volInfo('자동 '+target+' (혼잡도 '+({quiet:'한산',normal:'보통',busy:'혼잡'}[s.crowd_level]||s.crowd_level)+', 상한 '+s.max_volume+')');
    }
  }catch(e){volInfo('서버 볼륨을 못 받았어요: '+e.message)}
}

  // ================================================================ 자동 소음 측정 (T4)
// 실시간 소음 측정기와 같은 계산식(RMS -> dB, 보정값 90)으로 마이크를 읽고 3초 평균을 서버로 보낸다.
// 브라우저는 사용자가 화면을 한 번 누르기 전까지 오디오를 멈춰 두므로, 첫 터치(재생 버튼 등)에 측정이 시작된다.
const MIC={ac:null,an:null,buf:null,stream:null,starting:false,smooth:null,sum:0,n:0,warm:0,last:0,sending:false,sent:0};
const MIC_OFFSET=90,MIC_MIN=20,MIC_MAX=110,MIC_SEND_MS=3000;
function nState(t,bad){const el=$('nstate');el.textContent=t;el.style.color=bad?'#c0392b':''}
async function startMic(){
  if(MIC.stream||MIC.starting)return;
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){nState('이 브라우저는 마이크를 지원하지 않아요 (HTTPS 주소로 여세요)',true);return}
  MIC.starting=true;nState('마이크 권한을 허용해 주세요');
  try{
    // echoCancellation: 스피커로 나가는 이 플레이어 음악이 다시 마이크로 잡히는 것을 줄인다
    MIC.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:false}});
  }catch(e){
    MIC.starting=false;
    nState(e&&e.name==='NotAllowedError'?'마이크 권한이 거부됐어요. 주소창의 사이트 설정에서 허용해 주세요':'마이크를 사용할 수 없어요',true);
    return;
  }
  MIC.ac=new(window.AudioContext||window.webkitAudioContext)();
  const s=MIC.ac.createMediaStreamSource(MIC.stream);
  MIC.an=MIC.ac.createAnalyser();MIC.an.fftSize=2048;s.connect(MIC.an);
  MIC.buf=new Float32Array(MIC.an.fftSize);
  MIC.smooth=null;MIC.sum=0;MIC.n=0;MIC.warm=0;MIC.last=performance.now();MIC.starting=false;
  if(MIC.ac.state==='suspended')MIC.ac.resume().catch(()=>{});
  nState(MIC.ac.state==='running'?'측정 중':'화면을 한 번 누르면 측정을 시작해요');
  setInterval(micTick,100);   // 화면이 가려져도 계속 돈다 (requestAnimationFrame 은 멈춤)
}
function micTick(){
  if(!MIC.an||MIC.ac.state!=='running')return;
  MIC.an.getFloatTimeDomainData(MIC.buf);
  let s=0;for(let i=0;i<MIC.buf.length;i++)s+=MIC.buf[i]*MIC.buf[i];
  const rms=Math.sqrt(s/MIC.buf.length);
  const db=Math.min(MIC_MAX,Math.max(MIC_MIN,rms>1e-7?20*Math.log10(rms)+MIC_OFFSET:MIC_MIN));
  if(MIC.smooth===null)MIC.smooth=db;
  MIC.smooth+=(db-MIC.smooth)*(db>MIC.smooth?.98:.39);   // 올라갈 땐 빠르게, 내려갈 땐 천천히
  $('ndb').textContent=Math.round(MIC.smooth);
  if(++MIC.warm>10){MIC.sum+=MIC.smooth;MIC.n++}          // 처음 1초는 마이크 안정화 구간이라 버림
  const now=performance.now();
  if(now-MIC.last>=MIC_SEND_MS){MIC.last=now;micFlush()}
}
async function micFlush(){
  if(!srv||MIC.sending||!MIC.n)return;
  const avg=MIC.sum/MIC.n;MIC.sum=0;MIC.n=0;MIC.sending=true;
  try{await API.sendNoise(avg);MIC.sent++;nState('측정 중 · 3초마다 서버로 전송 ('+MIC.sent+'회)')}
  catch(e){nState('소음 전송 실패: '+e.message,true)}
  finally{MIC.sending=false}
}
// 첫 터치/키 입력에서 멈춰 있던 오디오를 깨운다
['pointerdown','keydown'].forEach(ev=>document.addEventListener(ev,()=>{
  if(!srv)return;
  if(!MIC.stream){startMic();return}
  if(MIC.ac&&MIC.ac.state==='suspended')MIC.ac.resume().then(()=>nState('측정 중')).catch(()=>{});
},true));

function topBar(){
  const el=$('top');
  if(srv){
    el.innerHTML='<span>'+String(srv.store_name||srv.email).replace(/</g,'&lt;')+'</span><a href="'+API.DASHBOARD_PAGE+'">대시보드</a><button type="button" id="logout">로그아웃</button>';
    $('logout').onclick=()=>API.logout(true);
  }else if(API){
    el.innerHTML='<a href="'+API.LOGIN_PAGE+'">로그인</a>';
  }
}

(async()=>{
  topBar();
  if(srv){startMic();await loadBgm();pollVolume();setInterval(pollVolume,3000)}
  else{srvMsg('로그인하면 매장 맞춤 AI 음악과 자동 볼륨이 켜져요');$('autovol').checked=false;$('autovol').disabled=true;volInfo('로그인 필요')}

  list();load(0,false);frame();
})();
