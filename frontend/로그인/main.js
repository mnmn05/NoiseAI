const FALLBACK_OPTIONS = {
  age_group: ["10대", "20대", "30대", "40대", "50대 이상"],
  gender: ["여성", "남성", "무관"],
  category: ["카페", "주점", "음식점"],
  mood: ["차분한", "활기찬", "아늑한", "고급스러운"],
  noise_strategy: ["안정형", "활기형"],
};
const sel = {};
const $ = id => document.getElementById(id);
const emailOk = v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

function buildChips(options) {
  document.querySelectorAll(".chips").forEach(box => {
    const key = box.dataset.key;
    box.innerHTML = "";
    (options[key] || []).forEach(label => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = label;
      b.setAttribute("aria-pressed", "false");
      b.onclick = () => {
        sel[key] = label;
        box.querySelectorAll(".chip").forEach(c => {
          const on = c === b; c.classList.toggle("on", on); c.setAttribute("aria-pressed", on);
        });
      };
      box.appendChild(b);
    });
  });
}
function show(mode) {
  const login = mode === "login";
  $("login").classList.toggle("hidden", !login);
  $("signup").classList.toggle("hidden", login);
  $("tabLogin").classList.toggle("on", login);
  $("tabSignup").classList.toggle("on", !login);
  $("desc").textContent = login ? "점주 계정으로 로그인하세요." : "매장 정보를 입력하고 점주로 가입하세요.";
  $("msg").style.display = "none";
}
$("tabLogin").onclick = () => show("login");
$("tabSignup").onclick = () => show("signup");

function notify(t, isErr) {
  const m = $("msg");
  m.textContent = t; m.style.display = "block";
  m.style.color = isErr ? "#c0392b" : "";
}
function busy(btn, on, label) { btn.disabled = on; btn.textContent = on ? "처리 중…" : label; }
async function loginAndGo(email, pw) {
  await NoiseAPI.login(email, pw);
  location.href = NoiseAPI.DASHBOARD_PAGE;
}

$("loginBtn").onclick = async () => {
  const e = $("lEmail").value.trim(), p = $("lPw").value;
  $("lEmailErr").textContent = emailOk(e) ? "" : "올바른 이메일을 입력해주세요.";
  $("lPwErr").textContent = p ? "" : "비밀번호를 입력해주세요.";
  if (!emailOk(e) || !p) return;
  busy($("loginBtn"), true, "로그인");
  try { await loginAndGo(e, p); }
  catch (err) { notify(err.message, true); }
  finally { busy($("loginBtn"), false, "로그인"); }
};

$("signupBtn").onclick = async () => {
  const e = $("sEmail").value.trim(), p = $("sPw").value;
  const seats = Number($("sSeats").value);
  const pwOk = p.length >= 8 && /[A-Za-z]/.test(p) && /\d/.test(p);
  const seatsOk = Number.isInteger(seats) && seats >= 0 && seats <= 1000;
  const missing = ["age_group", "gender", "category", "mood", "noise_strategy"].filter(k => !sel[k]);
  $("sEmailErr").textContent = emailOk(e) ? "" : "올바른 이메일을 입력해주세요.";
  $("sPwErr").textContent = pwOk ? "" : "비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다.";
  $("sSeatsErr").textContent = seatsOk ? "" : "좌석 수는 0~1000 사이 정수로 입력해주세요.";
  $("sSelErr").textContent = missing.length ? "모든 항목을 선택해주세요." : "";
  if (!emailOk(e) || !pwOk || !seatsOk || missing.length) return;
  busy($("signupBtn"), true, "회원가입");
  try {
    await NoiseAPI.signup({
      email: e, password: p,
      store_name: $("sStore").value.trim() || null,
      total_seats: seats,
      age_group: sel.age_group, gender: sel.gender, category: sel.category,
      mood: sel.mood, noise_strategy: sel.noise_strategy,
    });
    notify("가입 완료! 로그인하는 중…");
    await loginAndGo(e, p);
  } catch (err) {
    notify(err.message, true);
  } finally {
    busy($("signupBtn"), false, "회원가입");
  }
};

[["lEmail", "loginBtn"], ["lPw", "loginBtn"]].forEach(([inp, btn]) =>
  $(inp).addEventListener("keydown", ev => { if (ev.key === "Enter") $(btn).click(); }));

buildChips(FALLBACK_OPTIONS);
NoiseAPI.options()
  .then(opts => buildChips(Object.assign({}, FALLBACK_OPTIONS, opts)))
  .catch(err => notify(err.message + " (선택지는 기본값으로 표시합니다)", true));