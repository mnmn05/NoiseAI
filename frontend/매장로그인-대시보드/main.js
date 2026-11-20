var KEY = "maejanglog-noise-v1";
var tab = "dash", fCat = "전체", fStore = "전체";

function seed() {
  var cats = { "카페": 60, "음식점": 70, "주점": 80, "헬스장": 75, "독서실": 45 };
  var stores = [
    { id: 1, name: "모닝브루 본점", cat: "카페" },
    { id: 2, name: "골목식당", cat: "음식점" },
    { id: 3, name: "달빛포차", cat: "주점" },
    { id: 4, name: "스퀘어핏", cat: "헬스장" },
    { id: 5, name: "집중의 방", cat: "독서실" }
  ];
  var base = { 1: 58, 2: 69, 3: 82, 4: 74, 5: 41 }, recs = [], s = 7, id = 1;
  function rnd() { s = (s * 9301 + 49297) % 233280; return s / 233280; }
  for (var d = 6; d >= 0; d--) {
    stores.forEach(function (st) {
      var t = new Date(); t.setDate(t.getDate() - d); t.setHours(14, 0, 0, 0);
      recs.push({ id: id++, sid: st.id, db: Math.round((base[st.id] + (rnd() * 8 - 3)) * 10) / 10, t: t.toISOString() });
    });
  }
  return { cats: cats, stores: stores, recs: recs, nid: 6, rid: id };
}
var S;
try { S = JSON.parse(localStorage.getItem(KEY)); } catch (e) { S = null; }
if (!S || !S.stores) S = seed();
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} }

function esc(v) { return String(v).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
function avg(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : null; }
function f1(n) { return n == null ? "-" : n.toFixed(1); }
function fmt(t) { return new Date(t).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
function store(id) { return S.stores.filter(function (s) { return s.id === id; })[0]; }
function recsOf(sid) { return S.recs.filter(function (r) { return r.sid === sid; }); }
function status(db, cat) {
  if (db == null) return '<span class="tag">기록 없음</span>';
  var l = S.cats[cat];
  if (db > l) return '<span class="tag bad">기준 초과</span>';
  if (db > l - 5) return '<span class="tag warn">주의</span>';
  return '<span class="tag ok">양호</span>';
}
function color(db, cat) { var l = S.cats[cat]; return db > l ? "var(--bad)" : db > l - 5 ? "var(--warn)" : "var(--ok)"; }

function trend() {
  var days = [], i;
  for (i = 6; i >= 0; i--) { var d = new Date(); d.setDate(d.getDate() - i); days.push(d.toDateString()); }
  var vals = days.map(function (ds) { return avg(S.recs.filter(function (r) { return new Date(r.t).toDateString() === ds; }).map(function (r) { return r.db; })); });
  var pts = [], W = 560, H = 160, lo = 30, hi = 100;
  vals.forEach(function (v, i) { if (v != null) pts.push([30 + i * (W - 50) / 6, H - 24 - (v - lo) / (hi - lo) * (H - 40), v, i]); });
  var g = [40, 60, 80, 100].map(function (y) { var py = H - 24 - (y - lo) / (hi - lo) * (H - 40); return '<line x1="30" x2="' + (W - 20) + '" y1="' + py + '" y2="' + py + '" stroke="var(--bd)"/><text x="4" y="' + (py + 4) + '" font-size="10" fill="var(--mu)">' + y + '</text>'; }).join("");
  var xl = days.map(function (ds, i) { var d = new Date(ds); return '<text x="' + (30 + i * (W - 50) / 6) + '" y="' + (H - 6) + '" font-size="10" fill="var(--mu)" text-anchor="middle">' + (d.getMonth() + 1) + "/" + d.getDate() + "</text>"; }).join("");
  var line = pts.map(function (p) { return p[0] + "," + p[1]; }).join(" ");
  var dots = pts.map(function (p) { return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="4" fill="var(--ac)"/><text x="' + p[0] + '" y="' + (p[1] - 9) + '" font-size="10" fill="var(--tx)" text-anchor="middle">' + p[2].toFixed(0) + "</text>"; }).join("");
  return '<svg viewBox="0 0 ' + W + " " + H + '">' + g + xl + '<polyline points="' + line + '" fill="none" stroke="var(--ac)" stroke-width="2"/>' + dots + "</svg>";
}

function vDash() {
  var all = S.recs.map(function (r) { return r.db; });
  var today = S.recs.filter(function (r) { return new Date(r.t).toDateString() === new Date().toDateString(); }).map(function (r) { return r.db; });
  var over = S.stores.filter(function (s) { var a = avg(recsOf(s.id).map(function (r) { return r.db; })); return a != null && a > S.cats[s.cat]; }).length;
  var catRows = Object.keys(S.cats).map(function (c) {
    var a = avg(S.recs.filter(function (r) { var s = store(r.sid); return s && s.cat === c; }).map(function (r) { return r.db; }));
    var lim = S.cats[c];
    return '<div class="row"><span class="n">' + esc(c) + '</span><div class="bar"><i style="width:' + (a == null ? 0 : Math.min(100, a)) + "%;background:" + (a == null ? "var(--bd)" : color(a, c)) + '"></i><b style="left:' + lim + '%"></b></div><span class="v">' + f1(a) + " dB</span></div>";
  }).join("");
  var recent = S.recs.slice().sort(function (a, b) { return new Date(b.t) - new Date(a.t); }).slice(0, 6).map(function (r) {
    var s = store(r.sid) || { name: "(삭제됨)", cat: "" };
    return "<tr><td>" + esc(s.name) + "</td><td>" + r.db + " dB</td><td class=\"mu\">" + fmt(r.t) + "</td></tr>";
  }).join("");
  return '<div class="grid k">' +
    '<div class="card"><h2>전체 매장</h2><div class="big">' + S.stores.length + '</div></div>' +
    '<div class="card"><h2>전체 평균 소음</h2><div class="big">' + f1(avg(all)) + '<span class="mu"> dB</span></div></div>' +
    '<div class="card"><h2>오늘 평균</h2><div class="big">' + f1(avg(today)) + '<span class="mu"> dB</span></div></div>' +
    '<div class="card"><h2>기준 초과 매장</h2><div class="big ' + (over ? "bad" : "ok") + '">' + over + "</div></div></div>" +
    '<div class="grid two"><div class="card"><h2>카테고리별 평균 (세로선 = 기준)</h2>' + catRows + "</div>" +
    '<div class="card"><h2>최근 7일 평균 추이 (dB)</h2>' + trend() + "</div></div>" +
    '<div class="card"><h2>최근 기록</h2><div class="tw"><table><tbody>' + (recent || '<tr><td class="empty">기록이 없습니다</td></tr>') + "</tbody></table></div></div>";
}

function chips(list, cur, act) {
  return '<div class="chips">' + ["전체"].concat(list).map(function (c) { return '<button class="chip ' + (c === cur ? "on" : "") + '" data-act="' + act + '" data-v="' + esc(c) + '">' + esc(c) + "</button>"; }).join("") + "</div>";
}

function vStores() {
  var catOpts = Object.keys(S.cats).map(function (c) { return "<option>" + esc(c) + "</option>"; }).join("");
  var list = S.stores.filter(function (s) { return fCat === "전체" || s.cat === fCat; });
  var rows = list.map(function (s) {
    var rs = recsOf(s.id), a = avg(rs.map(function (r) { return r.db; })), last = rs.slice().sort(function (x, y) { return new Date(y.t) - new Date(x.t); })[0];
    return "<tr><td><b>" + esc(s.name) + "</b></td><td>" + esc(s.cat) + '</td><td>' + f1(a) + " dB</td><td>" + (last ? last.db + " dB" : "-") + "</td><td>" + status(a, s.cat) + '</td><td><button class="x" data-act="delStore" data-v="' + s.id + '" title="삭제">✕</button></td></tr>';
  }).join("");
  return '<div class="card"><h2>매장 추가</h2><form data-form="store"><label>매장명<input name="name" required maxlength="30"></label><label>카테고리<select name="cat">' + catOpts + '</select></label><button class="btn">추가</button></form></div>' +
    '<div class="card"><h2>카테고리 추가</h2><form data-form="cat"><label>이름<input name="name" required maxlength="12"></label><label>권장 기준 (dB)<input name="lim" type="number" min="20" max="120" value="65" required></label><button class="btn">추가</button></form></div>' +
    "";
}

function vLog() {
  var now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  var opts = S.stores.map(function (s) { return '<option value="' + s.id + '">' + esc(s.name) + " (" + esc(s.cat) + ")</option>"; }).join("");
  var names = S.stores.map(function (s) { return s.name; });
  var rows = S.recs.filter(function (r) { var s = store(r.sid); return s && (fStore === "전체" || s.name === fStore); })
    .sort(function (a, b) { return new Date(b.t) - new Date(a.t); }).slice(0, 40).map(function (r) {
      var s = store(r.sid);
      return "<tr><td>" + fmt(r.t) + "</td><td>" + esc(s.name) + "</td><td>" + esc(s.cat) + '</td><td style="color:' + color(r.db, s.cat) + '"><b>' + r.db + ' dB</b></td><td><button class="x" data-act="delRec" data-v="' + r.id + '" title="삭제">✕</button></td></tr>';
    }).join("");
  return "" +
    '<div class="card"><h2>기록 내역 (최근 40건)</h2>' + chips(names, fStore, "fStore") + '<div class="tw"><table><thead><tr><th>시각</th><th>매장</th><th>카테고리</th><th>평균 소음</th><th></th></tr></thead><tbody>' + (rows || '<tr><td colspan="5" class="empty">기록이 없습니다</td></tr>') + "</tbody></table></div></div>";
}

var OWN = "maejanglog-owners-v1", SES = "maejanglog-session-v1", authTab = "login";
var owners = [], me = null;
try { owners = JSON.parse(localStorage.getItem(OWN)) || []; me = JSON.parse(localStorage.getItem(SES)); } catch (e) { owners = []; me = null; }
function digits(s) { return String(s).replace(/\D/g, ""); }
function showErr(m) { var el = document.getElementById("err"); if (el) el.textContent = m; }
function setMe(o) { me = o; try { localStorage.setItem(SES, JSON.stringify(o)); } catch (e) {} tab = "dash"; render(); }
async function hash(pw, salt) { var b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(salt + pw)); return Array.from(new Uint8Array(b)).map(function (x) { return x.toString(16).padStart(2, "0"); }).join(""); }
async function doLogin(d) {
  var em = d.get("email").trim().toLowerCase();
  var o = owners.filter(function (x) { return x.email === em; })[0];
  if (!o || !o.salt || (await hash(d.get("pw"), o.salt)) !== o.hash) { showErr("이메일 또는 비밀번호가 올바르지 않습니다."); return; }
  setMe({ email: o.email, age: o.age, gender: o.gender, type: o.type, mood: o.mood });
}
async function doSignup(d) {
  var em = d.get("email").trim().toLowerCase();
  if (owners.some(function (x) { return x.email === em; })) { showErr("이미 가입된 이메일입니다."); return; }
  if (d.get("pw") !== d.get("pw2")) { showErr("비밀번호가 일치하지 않습니다."); return; }
  var salt = Math.random().toString(36).slice(2), hs = await hash(d.get("pw"), salt);
  var o = { email: em, salt: salt, hash: hs, age: d.get("age"), gender: d.get("gender"), type: d.get("type"), mood: d.get("mood") };
  owners.push(o);
  try { localStorage.setItem(OWN, JSON.stringify(owners)); } catch (e) {}
  setMe(o);
}
function grp(title, name, list) {
  return '<div class="grp"><span>' + title + '</span><div class="opts">' + list.map(function (v) { return '<label class="opt"><input type="radio" name="' + name + '" value="' + v + '" required><span>' + v + "</span></label>"; }).join("") + "</div></div>";
}
function authView() {
  document.getElementById("nav").innerHTML = "";
  document.getElementById("who").innerHTML = "";
  var lg = authTab === "login";
  var tabs = '<div class="chips"><button class="chip ' + (lg ? "on" : "") + '" data-act="authTab" data-v="login">로그인</button><button class="chip ' + (lg ? "" : "on") + '" data-act="authTab" data-v="signup">점주 회원가입</button></div>';
  var form = lg
    ? '<form data-form="login" class="col"><label>이메일<input name="email" type="email" required autocomplete="email"></label><label>비밀번호<div class="pw"><input name="pw" type="password" required autocomplete="current-password"><button type="button" class="lnk" data-act="pw">보기</button></div></label><button class="btn">로그인</button></form>'
    : '<form data-form="signup" class="col"><label>이메일<input name="email" type="email" required autocomplete="email"></label><label>비밀번호 (8자 이상)<div class="pw"><input name="pw" type="password" minlength="8" required autocomplete="new-password"><button type="button" class="lnk" data-act="pw">보기</button></div></label><label>비밀번호 확인<input name="pw2" type="password" required autocomplete="new-password"></label>' +
      grp("타겟 연령대", "age", ["10대", "20대", "30대 이상"]) + grp("타겟 성비", "gender", ["여성 위주", "남성 위주", "무관"]) + grp("매장 업종", "type", ["카페", "주점", "레스토랑"]) + grp("분위기", "mood", ["감성", "신나는", "차분한"]) +
      '<button class="btn">가입하기</button></form>';
  document.getElementById("app").innerHTML = '<div class="split"><div class="brand"><div style="font-size:40px">🔉</div><h2>매장로그</h2><p>매장의 소음을 기록하고<br>카테고리별로 한눈에 관리하세요.</p></div><div class="side"><h2>' + (lg ? "다시 오셨네요" : "점주 회원가입") + '</h2><p class="mu">' + (lg ? "이메일과 비밀번호로 로그인하세요." : "매장 정보를 입력하고 시작하세요.") + "</p>" + form + '<div id="err" class="bad mu" style="margin-top:10px"></div><p class="mu" style="margin-top:14px">' + (lg ? '계정이 없나요? <button type="button" class="lnk" data-act="authTab" data-v="signup">회원가입</button>' : '이미 계정이 있나요? <button type="button" class="lnk" data-act="authTab" data-v="login">로그인</button>') + "</p></div></div>";
}
function render() {
  if (!me) { authView(); return; }
  document.getElementById("who").innerHTML = esc(me.email) + " · " + esc(me.type) + " · " + esc(me.mood) + ' <button class="chip" data-act="logout">로그아웃</button>';
  document.getElementById("nav").innerHTML = [["dash", "대시보드"], ["stores", "매장 관리"], ["log", "소음 기록"]].map(function (t) { return '<button class="' + (tab === t[0] ? "on" : "") + '" data-act="tab" data-v="' + t[0] + '">' + t[1] + "</button>"; }).join("");
  document.getElementById("app").innerHTML = tab === "dash" ? vDash() : tab === "stores" ? vStores() : vLog();
}

document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-act]"); if (!b) return;
  var a = b.dataset.act, v = b.dataset.v;
  if (a === "pw") { var pi = b.parentNode.querySelector("input"); pi.type = pi.type === "password" ? "text" : "password"; return; }
  if (a === "authTab") authTab = v;
  else if (a === "logout") { me = null; authTab = "login"; try { localStorage.removeItem(SES); } catch (e) {} }
  else if (a === "tab") tab = v;
  else if (a === "fCat") fCat = v;
  else if (a === "fStore") fStore = v;
  else if (a === "delStore") { if (!confirm("매장과 해당 기록을 모두 삭제할까요?")) return; var id = +v; S.stores = S.stores.filter(function (s) { return s.id !== id; }); S.recs = S.recs.filter(function (r) { return r.sid !== id; }); fStore = "전체"; save(); }
  else if (a === "delRec") { S.recs = S.recs.filter(function (r) { return r.id !== +v; }); save(); }
  render();
});

document.addEventListener("submit", function (e) {
  e.preventDefault();
  var f = e.target, k = f.dataset.form, d = new FormData(f);
  if (k === "login") { doLogin(d); return; }
  if (k === "signup") { doSignup(d); return; }
  if (k === "store") S.stores.push({ id: S.nid++, name: d.get("name").trim(), cat: d.get("cat") });
  if (k === "cat") { var n = d.get("name").trim(); if (n && !(n in S.cats)) S.cats[n] = +d.get("lim"); }
  if (k === "rec") S.recs.push({ id: S.rid++, sid: +d.get("sid"), db: +d.get("db"), t: new Date(d.get("t")).toISOString() });
  save(); render();
});

render();
