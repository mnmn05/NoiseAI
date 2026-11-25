var me = NoiseAPI.requireLogin();
var tab = "dash", day = today(), timer = null;
var cache = { status: null, report: null, logs: [], user: null, options: null };
var LEVEL = { quiet: ["한산", "ok"], normal: ["보통", "warn"], busy: ["혼잡", "bad"], unknown: ["정보 없음", ""] };

function today() { var d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); }
function esc(v) { return String(v == null ? "" : v).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
function f1(n) { return n == null ? "-" : Number(n).toFixed(1); }
function won(n) { return n == null ? "-" : Number(n).toLocaleString("ko-KR") + "원"; }
function hh(h) { return h == null ? "-" : h + "시"; }
function fmt(t) { return new Date(t).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function tag(level) { var l = LEVEL[level] || LEVEL.unknown; return '<span class="tag ' + l[1] + '">' + l[0] + "</span>"; }
function errBox(e) { return '<div class="card"><p class="bad">' + esc(e.message || e) + "</p></div>"; }

// 차트: 막대 = 매출, 선 = 시간대 평균 dB
function hourChart(hours) {
  var W = 640, H = 220, L = 34, R = 44, T = 14, B = 24, lo = 30, hi = 100;
  var n = hours.length || 24, step = (W - L - R) / n;
  var maxSales = Math.max.apply(null, hours.map(function (h) { return h.sales_amount || 0; }).concat([1]));
  var y = function (db) { return T + (1 - (db - lo) / (hi - lo)) * (H - T - B); };
  var g = [40, 60, 80, 100].map(function (v) {
    return '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="var(--bd)"/><text x="4" y="' + (y(v) + 4) + '" font-size="10" fill="var(--mu)">' + v + "</text>";
  }).join("");
  var bars = hours.map(function (h, i) {
    if (!h.sales_amount) return "";
    var bh = h.sales_amount / maxSales * (H - T - B);
    return '<rect x="' + (L + i * step + 2) + '" y="' + (H - B - bh) + '" width="' + Math.max(1, step - 4) + '" height="' + bh + '" fill="var(--acs)"><title>' + h.hour + "시 매출 " + won(h.sales_amount) + "</title></rect>";
  }).join("");
  var pts = hours.map(function (h, i) { return h.avg_db == null ? null : [L + i * step + step / 2, y(Math.min(hi, Math.max(lo, h.avg_db))), h]; }).filter(Boolean);
  var line = pts.length > 1 ? '<polyline points="' + pts.map(function (p) { return p[0] + "," + p[1]; }).join(" ") + '" fill="none" stroke="var(--ac)" stroke-width="2"/>' : "";
  var dots = pts.map(function (p) { return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="3.5" fill="var(--ac)"><title>' + p[2].hour + "시 평균 " + f1(p[2].avg_db) + " dB (" + p[2].crowd_label + ")</title></circle>"; }).join("");
  var xl = hours.map(function (h, i) { return i % 3 ? "" : '<text x="' + (L + i * step + step / 2) + '" y="' + (H - 6) + '" font-size="10" fill="var(--mu)" text-anchor="middle">' + h.hour + "</text>"; }).join("");
  var legend = '<text x="' + (W - R + 4) + '" y="' + (T + 8) + '" font-size="10" fill="var(--ac)">— dB</text><text x="' + (W - R + 4) + '" y="' + (T + 22) + '" font-size="10" fill="var(--mu)">▮ 매출</text>';
  return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="시간대별 평균 소음과 매출">' + g + bars + line + dots + xl + legend + "</svg>";
}

function vDash() {
  var s = cache.status, r = cache.report;
  if (!r) return '<div class="card"><p class="mu">불러오는 중…</p></div>';
  var sum = r.summary, ov = r.overall;
  var nowDb = s ? f1(s.noise_level_db) : "-";
  var src = s ? (s.noise_source === "mic" ? "마이크 측정값" : "측정기 꺼짐 · 테스트용 더미값") : "";
  var recent = cache.logs.slice(-8).reverse().map(function (l) {
    return "<tr><td>" + fmt(l.created_at) + "</td><td><b>" + f1(l.noise_db) + " dB</b></td></tr>";
  }).join("");
  return '<div class="grid k">' +
    '<div class="card"><h2>지금 소음</h2><div class="big">' + nowDb + '<span class="mu"> dB</span></div><div class="mu">' + (s ? tag(s.crowd_level) + " " + esc(src) : "") + "</div></div>" +
    '<div class="card"><h2>' + (r.date === today() ? "오늘" : esc(r.date)) + ' 평균</h2><div class="big">' + f1(ov.avg_db) + '<span class="mu"> dB</span></div><div class="mu">측정 ' + ov.samples + "회 · 최고 " + f1(ov.max_db) + " dB</div></div>" +
    '<div class="card"><h2>가장 붐빈 시간</h2><div class="big bad">' + hh(sum.busiest_hour) + '</div><div class="mu">가장 한산: ' + hh(sum.quietest_hour) + "</div></div>" +
    '<div class="card"><h2>매출</h2><div class="big">' + won(ov.total_sales) + '</div><div class="mu">최고 매출 시간 ' + hh(sum.peak_sales_hour) +
    (sum.noise_sales_correlation != null ? " · 소음-매출 상관 " + sum.noise_sales_correlation : "") + "</div></div></div>" +
    '<div class="card"><h2>시간대별 평균 소음 · 매출</h2>' + hourChart(r.hours) +
    (sum.suggestion ? '<p class="mu">💡 ' + esc(sum.suggestion) + "</p>" : '<p class="mu">소음 측정기를 켜 두면 시간대별 기록이 쌓입니다.</p>') + "</div>" +
    '<div class="card"><h2>최근 측정 (3초마다)</h2><div class="tw"><table><tbody>' + (recent || '<tr><td class="empty">아직 기록이 없습니다. <a href="../실시간 소음 측정기/index.html">소음 측정기</a>를 켜 주세요.</td></tr>') + "</tbody></table></div></div>";
}

function vReport() {
  var r = cache.report;
  var picker = '<form data-form="day"><label>날짜<input type="date" name="day" value="' + day + '" max="' + today() + '"></label><button class="btn">조회</button></form>';
  if (!r) return '<div class="card">' + picker + '<p class="mu">불러오는 중…</p></div>';
  var rows = r.hours.filter(function (h) { return h.samples || h.sales_amount != null; }).map(function (h) {
    return "<tr><td>" + h.hour + "시</td><td><b>" + f1(h.avg_db) + "</b></td><td>" + f1(h.max_db) + "</td><td>" + f1(h.min_db) + "</td><td>" + tag(h.crowd_level) + "</td><td>" + won(h.sales_amount) + "</td><td>" + (h.order_count == null ? "-" : h.order_count) + "</td><td>" + h.plays + "</td></tr>";
  }).join("");
  return '<div class="card"><h2>날짜 선택</h2>' + picker + "</div>" +
    '<div class="card"><h2>' + esc(r.date) + ' 시간대별 리포트</h2><div class="tw"><table><thead><tr><th>시간</th><th>평균 dB</th><th>최고</th><th>최저</th><th>혼잡도</th><th>매출</th><th>주문</th><th>재생 곡</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="8" class="empty">이 날짜에는 기록이 없습니다</td></tr>') + "</tbody></table></div></div>" +
    '<div class="card"><h2>POS 매출 CSV 올리기</h2><form data-form="sales"><label>CSV 파일 (시간·매출·주문수 또는 결제일시·결제금액)<input type="file" name="file" accept=".csv,text/csv" required></label><button class="btn">업로드</button></form><p class="mu" id="salesMsg"></p></div>';
}

function opt(name, list, cur) {
  return '<label>' + name[1] + '<select name="' + name[0] + '">' + list.map(function (v) { return "<option" + (v === cur ? " selected" : "") + ">" + esc(v) + "</option>"; }).join("") + "</select></label>";
}
function vSettings() {
  var u = cache.user, o = cache.options;
  if (!u || !o) return '<div class="card"><p class="mu">불러오는 중…</p></div>';
  var pub = u.public_id ? NoiseAPI.base() + "/api/public/status/" + u.public_id : "";
  return '<div class="card"><h2>매장 설정 (음악 생성 프롬프트에 바로 반영됩니다)</h2><form data-form="store">' +
    '<label>매장 이름<input name="store_name" maxlength="100" value="' + esc(u.store_name || "") + '"></label>' +
    '<label>좌석 수<input name="total_seats" type="number" min="0" max="1000" value="' + (u.total_seats || 0) + '"></label>' +
    opt(["category", "업종"], o.category, u.category) + opt(["mood", "분위기"], o.mood, u.mood) +
    opt(["age_group", "타겟 연령대"], o.age_group, u.age_group) + opt(["gender", "타겟 성비"], o.gender, u.gender) +
    opt(["noise_strategy", "소음 대응 방식"], o.noise_strategy, u.noise_strategy_ko) +
    '<button class="btn">저장</button></form><p class="mu" id="storeMsg"></p></div>' +
    (pub ? '<div class="card"><h2>손님용 한산 상태 링크</h2><p class="mu">이 주소를 가게 SNS·지도에 걸어 두면 손님이 지금 붐비는지 볼 수 있습니다.</p><p><a href="' + esc(pub) + '" target="_blank" rel="noopener">' + esc(pub) + "</a></p></div>" : "");
}

function render() {
  if (!me) return;
  document.getElementById("who").innerHTML = esc(me.store_name || me.email) +
    ' <a class="chip" href="../실시간 소음 측정기/index.html">소음 측정기</a> <a class="chip" href="../음악 플레이어/index.html">음악 플레이어</a> <button class="chip" data-act="logout">로그아웃</button>';
  document.getElementById("nav").innerHTML = [["dash", "대시보드"], ["report", "시간대 리포트"], ["settings", "매장 설정"]].map(function (t) {
    return '<button class="' + (tab === t[0] ? "on" : "") + '" data-act="tab" data-v="' + t[0] + '">' + t[1] + "</button>";
  }).join("");
  document.getElementById("app").innerHTML = tab === "dash" ? vDash() : tab === "report" ? vReport() : vSettings();
}

async function loadDash() {
  var res = await Promise.allSettled([NoiseAPI.status(), NoiseAPI.report(tab === "dash" ? today() : day), NoiseAPI.statusLog(20)]);
  if (res[0].status === "fulfilled") cache.status = res[0].value;
  if (res[1].status === "fulfilled") cache.report = res[1].value;
  if (res[2].status === "fulfilled") cache.logs = res[2].value;
  var failed = res.filter(function (x) { return x.status === "rejected"; })[0];
  render();
  if (failed) document.getElementById("app").insertAdjacentHTML("afterbegin", errBox(failed.reason));
}
async function loadSettings() {
  try {
    var r = await Promise.all([NoiseAPI.getUser(), NoiseAPI.options()]);
    cache.user = r[0]; cache.options = r[1];
    render();
  } catch (e) { render(); document.getElementById("app").insertAdjacentHTML("afterbegin", errBox(e)); }
}
function load() {
  clearInterval(timer); timer = null;
  if (tab === "settings") return loadSettings();
  if (tab === "dash") timer = setInterval(loadDash, 5000);
  return loadDash();
}

document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-act]"); if (!b) return;
  var a = b.dataset.act;
  if (a === "logout") { NoiseAPI.logout(true); return; }
  if (a === "tab") { tab = b.dataset.v; cache.report = null; render(); load(); }
});

document.addEventListener("submit", async function (e) {
  e.preventDefault();
  var f = e.target, k = f.dataset.form, d = new FormData(f);
  if (k === "day") { day = d.get("day") || today(); cache.report = null; render(); load(); return; }
  if (k === "store") {
    var msg = document.getElementById("storeMsg");
    try {
      var u = await NoiseAPI.updateStore({
        store_name: d.get("store_name").trim() || null, total_seats: Number(d.get("total_seats")) || 0,
        category: d.get("category"), mood: d.get("mood"), age_group: d.get("age_group"),
        gender: d.get("gender"), noise_strategy: d.get("noise_strategy"),
      });
      cache.user = u;
      me.store_name = u.store_name;
      try { localStorage.setItem("noiseai-user", JSON.stringify({ id: u.id, email: u.email, store_name: u.store_name })); } catch (er) {}
      render();
      document.getElementById("storeMsg").textContent = "저장했습니다. 다음에 만들어지는 곡부터 반영됩니다.";
    } catch (er) { msg.textContent = er.message; msg.className = "bad"; }
    return;
  }
  if (k === "sales") {
    var sm = document.getElementById("salesMsg");
    sm.className = "mu"; sm.textContent = "업로드 중…";
    try {
      var r = await NoiseAPI.uploadSales(d.get("file"));
      sm.textContent = r.hours_saved + "개 시간대 저장 (새로 " + r.inserted + " · 갱신 " + r.updated + ")" + (r.error_count ? " · 건너뛴 행 " + r.error_count + "개" : "");
      cache.report = await NoiseAPI.report(day);
      var keep = sm.textContent;
      render();
      document.getElementById("salesMsg").textContent = keep;
    } catch (er) { sm.className = "bad"; sm.textContent = er.message; }
  }
});

if (me) { render(); load(); }