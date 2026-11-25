(function () {
  "use strict";
  var DEPLOY_API = "https://noiseai.onrender.com";
  var LOCAL_API = "http://localhost:8000";
  var K_BASE = "noiseai-api-base", K_TOKEN = "noiseai-token", K_USER = "noiseai-user";
  var LOGIN_PAGE = "../로그인/index.html";
  var DASHBOARD_PAGE = "../매장로그인-대시보드/index.html";

  function store(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) { return null; }
    return null;
  }
  // /app/ 으로 열면 같은 서버, 파일·localhost 면 8000번, 그 외엔 배포 서버
  function base() {
    var saved = store(K_BASE);
    if (saved !== null && saved !== undefined) return saved;
    if (location.pathname.indexOf("/app/") === 0) return "";
    if (location.protocol === "file:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return LOCAL_API;
    return DEPLOY_API;
  }
  function absUrl(u) {
    if (!u) return u;
    return /^https?:\/\//.test(u) ? u : base() + (u.charAt(0) === "/" ? u : "/" + u);
  }
  function errorText(status, body) {
    var d = body && body.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) {
      return d.map(function (e) {
        var field = (e.loc || []).filter(function (x) { return x !== "body" && x !== "query"; }).join(".");
        return (field ? field + ": " : "") + String(e.msg || "").replace(/^Value error, /, "");
      }).join(" / ");
    }
    if (d && d.message) return d.message;
    if (status === 0) return "서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요 (" + (base() || location.origin) + ")";
    return "요청이 실패했습니다 (" + status + ")";
  }
  function session() {
    var u = null;
    try { u = JSON.parse(store(K_USER) || "null"); } catch (e) { u = null; }
    return { token: store(K_TOKEN), user: u };
  }
  function userId() { var u = session().user; return u ? u.id : null; }
  function logout(goLogin) {
    store(K_TOKEN, null); store(K_USER, null);
    if (goLogin) location.href = LOGIN_PAGE;
  }
  async function request(method, path, opts) {
    opts = opts || {};
    var headers = {}, body;
    var tok = store(K_TOKEN);
    if (tok) headers.Authorization = "Bearer " + tok;
    if (opts.form) body = opts.form;
    else if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
    var res;
    try { res = await fetch(base() + path, { method: method, headers: headers, body: body }); }
    catch (e) { var ne = new Error(errorText(0)); ne.status = 0; throw ne; }
    var data = null, text = await res.text();
    if (text) { try { data = JSON.parse(text); } catch (e) { data = text; } }
    if (!res.ok) {
      if (res.status === 401 && tok && !opts.noAuthRedirect) logout(true);
      var err = new Error(errorText(res.status, data)); err.status = res.status; err.body = data; throw err;
    }
    return data;
  }
  function qs(params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      if (params[k] !== undefined && params[k] !== null && params[k] !== "") parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }
  function needUser() {
    var id = userId();
    if (id == null) { var e = new Error("로그인이 필요합니다"); e.status = 401; throw e; }
    return id;
  }

  window.NoiseAPI = {
    base: base, absUrl: absUrl, session: session, userId: userId, logout: logout, request: request,
    setBase: function (u) { store(K_BASE, u === null ? null : String(u).replace(/\/+$/, "")); return base(); },
    LOGIN_PAGE: LOGIN_PAGE, DASHBOARD_PAGE: DASHBOARD_PAGE,
    requireLogin: function () {
      var s = session();
      if (!s.token || !s.user) { location.href = LOGIN_PAGE; return null; }
      return s.user;
    },
    // 회원/로그인
    options: function () { return request("GET", "/api/options"); },
    signup: function (data) { return request("POST", "/api/users", { json: data }); },
    login: async function (email, password) {
      var r = await request("POST", "/api/auth/login", { json: { email: email, password: password }, noAuthRedirect: true });
      store(K_TOKEN, r.access_token);
      var me = await request("GET", "/api/auth/me");
      store(K_USER, JSON.stringify({ id: me.user_id, email: me.email, store_name: me.store_name }));
      return me;
    },
    getUser: function () { return request("GET", "/api/users/" + needUser()); },
    updateStore: function (data) { return request("PATCH", "/api/users/" + needUser() + "/store", { json: data }); },
    // 소음
    status: function () { return request("GET", "/api/status"); },
    sendNoise: async function (db) {
      db = Math.round(Math.min(140, Math.max(0, db)) * 10) / 10;
      var id = needUser();
      var r = await Promise.all([
        request("POST", "/api/status-log", { json: { user_id: id, noise_db: db } }),
        request("POST", "/api/update-noise", { json: { noise_db: db } }),
      ]);
      return r[0];
    },
    statusLog: function (limit) { return request("GET", "/api/status-log" + qs({ user_id: needUser(), limit: limit || 60 })); },
    report: function (date) { return request("GET", "/api/report" + qs({ user_id: needUser(), date: date })); },
    // 음악
    bgmPlaylist: function () { return request("GET", "/api/bgm/playlist" + qs({ user_id: userId() })); },
    generateTrack: function (noiseDb) {
      return request("POST", "/api/tracks/generate", { json: { user_id: needUser(), noise_db: noiseDb == null ? null : noiseDb } });
    },
    nextTrack: async function () {
      try { return await request("GET", "/api/tracks/next" + qs({ user_id: needUser() })); }
      catch (e) { if (e.status === 404) return null; throw e; }
    },
    markPlayed: function (trackId) { return request("POST", "/api/tracks/" + trackId + "/played"); },
    // 매출
    uploadSales: function (file) {
      var f = new FormData(); f.append("file", file);
      return request("POST", "/api/sales/upload" + qs({ user_id: needUser() }), { form: f });
    },
  };
})();