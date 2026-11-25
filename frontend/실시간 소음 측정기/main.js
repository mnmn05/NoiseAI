(function(){
  var MIN=20, MAX=110, SPAN=60, STEP=250, N=SPAN*1000/STEP;
  var $=function(id){return document.getElementById(id)};
  var numEl=$('num'), stateEl=$('state'), needle=$('needle'), cv=$('cv'), msg=$('msg'), btn=$('toggle');
  var ac=null, analyser=null, stream=null, buf=null, raf=0, running=false;
  var offset=90, smooth=null, hist=[], blockMax=0, lastPush=0, stats;
  var SEND_MS=3000, sendSum=0, sendN=0, lastSend=0, sending=false, sentCount=0;
  var syncEl=$('sync'), user=(window.NoiseAPI&&NoiseAPI.session().token)?NoiseAPI.session().user:null;
  function setSync(t,bad){if(!syncEl)return;syncEl.textContent=t;syncEl.style.color=bad?'var(--bad)':'';}
  if(user) setSync((user.store_name||user.email)+' 매장으로 전송 준비됨 · 측정을 시작하세요');
  async function flush(){
    if(!user||sending||!sendN) return;
    var avg=sendSum/sendN; sendSum=0; sendN=0; sending=true;
    try{ await NoiseAPI.sendNoise(avg); sentCount++; setSync('서버 전송 중 · 마지막 '+avg.toFixed(1)+' dB · '+sentCount+'회 전송'); }
    catch(e){ setSync('전송 실패: '+e.message, true); }
    finally{ sending=false; }
  }

  function resetStats(){stats={min:Infinity,max:-Infinity,sum:0,n:0,warm:0};hist=[];['smin','savg','smax'].forEach(function(i){$(i).textContent='--'});draw();}
  resetStats();

  function level(db){
    if(db<40) return {t:'조용함',d:'도서관 수준',c:'var(--ok)'};
    if(db<60) return {t:'보통',d:'일상적인 소리',c:'var(--ok)'};
    if(db<75) return {t:'다소 시끄러움',d:'대화가 또렷하게 들리는 수준',c:'var(--warn)'};
    if(db<85) return {t:'시끄러움',d:'번화가 수준',c:'var(--bad)'};
    return {t:'매우 시끄러움',d:'오래 있으면 청력에 해로움',c:'var(--hot)'};
  }
  function colorFor(db){return level(db).c}

  function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v.replace(/var\((.*)\)/,'$1')).trim()}

  function draw(){
    var dpr=window.devicePixelRatio||1, w=cv.clientWidth, h=cv.clientHeight;
    if(cv.width!==Math.round(w*dpr)||cv.height!==Math.round(h*dpr)){cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr);}
    var g=cv.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0); g.clearRect(0,0,w,h);
    var line=css('--line'), muted=css('--muted');
    g.font='11px "Noto Sans KR",sans-serif'; g.textBaseline='middle';
    [40,60,80,100].forEach(function(v){
      var y=h-(v-MIN)/(MAX-MIN)*h;
      g.strokeStyle=line; g.lineWidth=1; g.beginPath(); g.moveTo(0,y); g.lineTo(w,y); g.stroke();
      g.fillStyle=muted; g.fillText(v,4,y-7);
    });
    var bw=w/N;
    for(var i=0;i<hist.length;i++){
      var v=hist[i], x=w-(hist.length-i)*bw, bh=Math.max(2,(v-MIN)/(MAX-MIN)*h);
      g.fillStyle=css(colorFor(v)); g.fillRect(x,h-bh,Math.max(1,bw-1),bh);
    }
  }

  function show(db){
    var lv=level(db);
    document.documentElement.style.setProperty('--lvl',lv.c.replace(/var\((.*)\)/,'var($1)'));
    numEl.firstChild.nodeValue=Math.round(db);
    stateEl.innerHTML=lv.t+'<span>'+lv.d+'</span>';
    needle.style.left='calc('+((db-MIN)/(MAX-MIN)*100)+'% - 2px)';
  }

  function loop(ts){
    if(!running) return;
    analyser.getFloatTimeDomainData(buf);
    var s=0; for(var i=0;i<buf.length;i++) s+=buf[i]*buf[i];
    var rms=Math.sqrt(s/buf.length);
    var db=rms>1e-7 ? 20*Math.log10(rms)+offset : MIN;
    db=Math.min(MAX,Math.max(MIN,db));
    if(smooth===null) smooth=db;
    smooth+=(db-smooth)*(db>smooth?0.5:0.08);
    show(smooth);
    blockMax=Math.max(blockMax,smooth);
    if(stats.warm>4){sendSum+=smooth;sendN++;}
    if(ts-lastSend>=SEND_MS){lastSend=ts;flush();}

    if(ts-lastPush>=STEP){
      lastPush=ts; hist.push(blockMax); if(hist.length>N) hist.shift();
      if(++stats.warm>4){
        stats.min=Math.min(stats.min,blockMax); stats.max=Math.max(stats.max,blockMax);
        stats.sum+=blockMax; stats.n++;
        $('smin').textContent=Math.round(stats.min); $('smax').textContent=Math.round(stats.max);
        $('savg').textContent=Math.round(stats.sum/stats.n);
      }
      blockMax=0; draw();
    }
    raf=requestAnimationFrame(loop);
  }

  async function start(){
    msg.textContent='';
    if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
      msg.textContent='이 브라우저는 마이크 입력을 지원하지 않습니다. 최신 Chrome, Safari, Edge에서 열어 주세요.'; return;
    }
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    }catch(e){
      msg.textContent=(e&&e.name==='NotAllowedError')
        ? '마이크 권한이 거부되었습니다. 주소창의 사이트 설정에서 마이크를 허용한 뒤 다시 시도해 주세요.'
        : '마이크를 사용할 수 없습니다. 연결된 마이크가 있는지 확인해 주세요.';
      return;
    }
    ac=new (window.AudioContext||window.webkitAudioContext)();
    await ac.resume();
    var src=ac.createMediaStreamSource(stream);
    analyser=ac.createAnalyser(); analyser.fftSize=2048; src.connect(analyser);
    buf=new Float32Array(analyser.fftSize);
    smooth=null; blockMax=0; lastPush=0; sendSum=0; sendN=0; lastSend=performance.now(); running=true;
    btn.textContent='측정 중지';
    raf=requestAnimationFrame(loop);
  }
  function stop(){
    running=false; cancelAnimationFrame(raf);
    if(stream) stream.getTracks().forEach(function(t){t.stop()});
    if(ac) ac.close();
    stream=null; ac=null;
    btn.textContent='측정 시작';
    stateEl.textContent='측정이 중지되었습니다';
    sendSum=0; sendN=0; if(user) setSync('측정 중지 · 전송 멈춤 ('+sentCount+'회 전송)');
  }

  btn.addEventListener('click',function(){running?stop():start()});
  $('reset').addEventListener('click',resetStats);
  $('off').addEventListener('input',function(e){offset=+e.target.value;$('offv').textContent=offset;});
  window.addEventListener('resize',draw);
  if(window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
  document.addEventListener('visibilitychange',function(){if(document.hidden&&running)stop();});
})();
