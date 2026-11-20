const OPTIONS={
  age:["10대","20대","30대 이상"],
  gender:["여성 위주","남성 위주","무관"],
  type:["카페","주점","레스토랑"],
  mood:["감성","신나는","차분한"]
};
const sel={};
const $=id=>document.getElementById(id);
const emailOk=v=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

document.querySelectorAll(".chips").forEach(box=>{
  const key=box.dataset.key;
  OPTIONS[key].forEach(label=>{
    const b=document.createElement("button");
    b.type="button";b.className="chip";b.textContent=label;
    b.setAttribute("aria-pressed","false");
    b.onclick=()=>{
      sel[key]=label;
      box.querySelectorAll(".chip").forEach(c=>{
        const on=c===b;c.classList.toggle("on",on);c.setAttribute("aria-pressed",on);
      });
    };
    box.appendChild(b);
  });
});

function show(mode){
  const login=mode==="login";
  $("login").classList.toggle("hidden",!login);
  $("signup").classList.toggle("hidden",login);
  $("tabLogin").classList.toggle("on",login);
  $("tabSignup").classList.toggle("on",!login);
  $("desc").textContent=login?"점주 계정으로 로그인하세요.":"매장 정보를 입력하고 점주로 가입하세요.";
  $("msg").style.display="none";
}
$("tabLogin").onclick=()=>show("login");
$("tabSignup").onclick=()=>show("signup");

function notify(t){const m=$("msg");m.textContent=t;m.style.display="block"}

$("loginBtn").onclick=()=>{
  const e=$("lEmail").value.trim(),p=$("lPw").value;
  $("lEmailErr").textContent=emailOk(e)?"":"올바른 이메일을 입력해주세요.";
  $("lPwErr").textContent=p?"":"비밀번호를 입력해주세요.";
  if(!emailOk(e)||!p)return;
};

$("signupBtn").onclick=()=>{
  const e=$("sEmail").value.trim(),p=$("sPw").value;
  const pwOk=p.length>=8&&/[A-Za-z]/.test(p)&&/\d/.test(p);
  const missing=Object.keys(OPTIONS).filter(k=>!sel[k]);
  $("sEmailErr").textContent=emailOk(e)?"":"올바른 이메일을 입력해주세요.";
  $("sPwErr").textContent=pwOk?"":"비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다.";
  $("sSelErr").textContent=missing.length?"모든 항목을 선택해주세요.":"";
  if(!emailOk(e)||!pwOk||missing.length)return;
  notify(`가입 완료! ${sel.type} · ${sel.mood} · ${sel.age} · ${sel.gender}`);
};
