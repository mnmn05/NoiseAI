import { FormEvent, ReactNode, useState } from "react";

type IconName =
  | "grid"
  | "store"
  | "user"
  | "settings"
  | "bell"
  | "search"
  | "chevron"
  | "more"
  | "users"
  | "volume"
  | "trend"
  | "plus"
  | "edit"
  | "check"
  | "menu"
  | "close"
  | "mail"
  | "phone";

function Icon({ name, className = "size-5" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    store: <><path d="M3 9l2-5h14l2 5" /><path d="M5 13v8h14v-8M9 21v-5h6v5" /><path d="M3 9a3 3 0 006 0 3 3 0 006 0 3 3 0 006 0" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 00.3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.6v.2h-4V21a1.7 1.7 0 00-1-1.6 1.7 1.7 0 00-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 00.3-1.9A1.7 1.7 0 003 14H2.8v-4H3a1.7 1.7 0 001.6-1 1.7 1.7 0 00-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 009 4.6 1.7 1.7 0 0010 3v-.2h4V3a1.7 1.7 0 001 1.6 1.7 1.7 0 001.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 00-.3 1.9 1.7 1.7 0 001.6 1h.2v4H21a1.7 1.7 0 00-1.6 1z" /></>,
    bell: <><path d="M18 8a6 6 0 00-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></>,
    chevron: <path d="M9 18l6-6-6-6" />,
    more: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
    users: <><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="8.5" cy="7" r="4" /><path d="M17 11a4 4 0 010-8M23 21v-2a4 4 0 00-3-3.9" /></>,
    volume: <><path d="M11 5L6 9H2v6h4l5 4V5zM15 9a4 4 0 010 6M18 6a8 8 0 010 12" /></>,
    trend: <><path d="M3 17l6-6 4 4 8-9" /><path d="M15 6h6v6" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L8 18l-4 1 1-4z" /></>,
    check: <path d="M20 6L9 17l-5-5" />,
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    close: <path d="M6 6l12 12M18 6L6 18" />,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></>,
    phone: <path d="M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6A19.8 19.8 0 012.1 4.2 2 2 0 014.1 2h3a2 2 0 012 1.7c.1 1 .4 2 .7 2.8a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.3-1.3a2 2 0 012.1-.5c.9.3 1.8.6 2.8.7A2 2 0 0122 16.9z" />,
  };
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

const stores = [
  { name: "성수 본점", category: "카페 · 베이커리", status: "운영중", gender: 58, noise: 48, updated: "오늘 10:24" },
  { name: "연남 2호점", category: "주점", status: "운영중", gender: 64, noise: 55, updated: "오늘 09:12" },
  { name: "한남 3호점", category: "식당", status: "운영중", gender: 51, noise: 62, updated: "어제 18:40" },
];

function Logo() {
  return <div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-xl bg-indigo-600 text-white shadow-lg shadow-indigo-200"><Icon name="store" className="size-5" /></div><span className="text-lg font-extrabold tracking-tight text-slate-900">매장로그</span></div>;
}

function App() {
  const [page, setPage] = useState<"dashboard" | "stores" | "profile">("dashboard");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("owner@maejanglog.kr");
  const [phone, setPhone] = useState("010-4827-1936");
  const [selectedStore, setSelectedStore] = useState(0);
  const [female, setFemale] = useState(stores[0].gender);
  const [noise, setNoise] = useState(stores[0].noise);

  const navigate = (next: typeof page) => {
    setPage(next);
    setMobileMenu(false);
  };

  const save = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2400);
  };

  const selectStore = (index: number) => {
    setSelectedStore(index);
    setFemale(stores[index].gender);
    setNoise(stores[index].noise);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {notice && <div className="fixed right-5 top-5 z-50 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-xl"><Icon name="check" className="size-4 text-emerald-400" />{notice}</div>}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white p-5 transition-transform lg:translate-x-0 ${mobileMenu ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between"><Logo /><button className="rounded-lg p-2 text-slate-500 lg:hidden" onClick={() => setMobileMenu(false)} aria-label="메뉴 닫기"><Icon name="close" /></button></div>
        <nav className="mt-10 space-y-1">
          <NavItem icon="grid" label="대시보드" active={page === "dashboard"} onClick={() => navigate("dashboard")} />
          <NavItem icon="store" label="매장 관리" active={page === "stores"} onClick={() => navigate("stores")} count="3" />
          <NavItem icon="user" label="개인정보 관리" active={page === "profile"} onClick={() => navigate("profile")} />
        </nav>
        <div className="mt-auto rounded-2xl bg-indigo-50 p-4">
          <div className="mb-2 grid size-8 place-items-center rounded-lg bg-white text-indigo-600"><Icon name="trend" className="size-4" /></div>
          <p className="text-sm font-bold text-slate-900">이번 주 리포트</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">방문 데이터가 지난주보다 12.4% 증가했어요.</p>
          <button className="mt-3 text-xs font-bold text-indigo-600" onClick={() => save("리포트를 준비하고 있어요.")}>자세히 보기</button>
        </div>
        <button className="mt-4 flex items-center gap-3 rounded-xl p-2 text-left hover:bg-slate-50" onClick={() => navigate("profile")}>
          <div className="grid size-9 place-items-center rounded-full bg-amber-100 text-sm font-extrabold text-amber-700">김</div>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold">김민준 점주님</p><p className="text-xs text-slate-400">매장 3개 운영중</p></div>
          <Icon name="chevron" className="size-4 text-slate-400" />
        </button>
      </aside>

      {mobileMenu && <button className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden" onClick={() => setMobileMenu(false)} aria-label="메뉴 닫기" />}

      <main className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200/80 bg-white/90 px-5 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 text-slate-600 lg:hidden" onClick={() => setMobileMenu(true)} aria-label="메뉴 열기"><Icon name="menu" /></button>
            <div><p className="text-xs font-semibold text-slate-400">STORE MANAGEMENT</p><h1 className="mt-0.5 text-xl font-extrabold tracking-tight">{page === "dashboard" ? "대시보드" : page === "stores" ? "매장 관리" : "개인정보 관리"}</h1></div>
          </div>
          <div className="flex items-center gap-2">
            <label className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 md:flex"><Icon name="search" className="size-4 text-slate-400" /><input className="w-44 bg-transparent text-sm outline-none placeholder:text-slate-400" placeholder="매장 검색" /></label>
            <button className="relative rounded-xl border border-slate-200 bg-white p-2.5 text-slate-500 hover:bg-slate-50" aria-label="알림"><Icon name="bell" className="size-5" /><span className="absolute right-2 top-2 size-1.5 rounded-full bg-rose-500 ring-2 ring-white" /></button>
          </div>
        </header>

        <div className="mx-auto max-w-7xl p-5 md:p-8">
          {page === "dashboard" && <Dashboard onManage={() => navigate("stores")} />}
          {page === "stores" && <StoreManagement selected={selectedStore} female={female} noise={noise} onSelect={selectStore} onFemale={setFemale} onNoise={setNoise} onSave={() => save("매장 데이터가 저장되었습니다.")} />}
          {page === "profile" && <Profile email={email} phone={phone} onEmail={setEmail} onPhone={setPhone} onSave={() => save("개인정보가 안전하게 변경되었습니다.")} />}
        </div>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active, onClick, count }: { icon: IconName; label: string; active: boolean; onClick: () => void; count?: string }) {
  return <button onClick={onClick} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-bold transition ${active ? "bg-indigo-50 text-indigo-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}><Icon name={icon} className="size-5" /><span className="flex-1 text-left">{label}</span>{count && <span className={`rounded-md px-2 py-0.5 text-xs ${active ? "bg-white text-indigo-600" : "bg-slate-100"}`}>{count}</span>}</button>;
}

function Dashboard({ onManage }: { onManage: () => void }) {
  return <div className="space-y-7">
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div><p className="text-sm font-semibold text-indigo-600">2025년 5월 28일 수요일</p><h2 className="mt-1 text-2xl font-extrabold tracking-tight md:text-3xl">좋은 아침이에요, 김민준 점주님</h2><p className="mt-2 text-sm text-slate-500">오늘도 매장의 주요 현황을 한눈에 확인하세요.</p></div>
      <button onClick={onManage} className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700"><Icon name="plus" className="size-4" />매장 데이터 기록</button>
    </div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <Metric icon="store" label="운영 매장" value="3개" detail="전체 정상 운영중" color="indigo" />
      <Metric icon="volume" label="평균 소음" value="55 dB" detail="대화하기 편안해요" color="amber" />
      <Metric icon="trend" label="데이터 기록률" value="92%" detail="+4.2% 이번 달" color="rose" />
    </div>
    <div className="grid gap-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
        <div className="flex items-center justify-between"><div><h3 className="font-extrabold">시간대별 방문 추이</h3><p className="mt-1 text-xs text-slate-400">최근 7일 평균 방문자 수</p></div><select className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold outline-none"><option>전체 매장</option><option>성수 본점</option></select></div>
        <div className="mt-8 flex h-60 items-end gap-3 border-b border-slate-100 px-2">
          {[22, 30, 38, 55, 72, 65, 88, 82, 60, 46, 35, 28].map((height, i) => <div key={i} className="group relative flex h-full flex-1 items-end"><div className={`w-full rounded-t-md transition-all group-hover:bg-indigo-600 ${i === 6 ? "bg-indigo-600" : "bg-indigo-100"}`} style={{ height: `${height}%` }} /><span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-slate-400">{i % 2 === 0 ? `${9 + i}시` : ""}</span></div>)}
        </div>
        <div className="mt-10 flex justify-center gap-5 text-xs text-slate-500"><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-indigo-600" />이번 주</span><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-indigo-100" />지난 주</span></div>
      </section>
    </div>
    <StoreList onManage={onManage} />
  </div>;
}

function Metric({ icon, label, value, detail, color }: { icon: IconName; label: string; value: string; detail: string; color: string }) {
  const palette: Record<string, string> = { indigo: "bg-indigo-50 text-indigo-600", emerald: "bg-emerald-50 text-emerald-600", amber: "bg-amber-50 text-amber-600", rose: "bg-rose-50 text-rose-600" };
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className={`mb-5 grid size-10 place-items-center rounded-xl ${palette[color]}`}><Icon name={icon} className="size-5" /></div><p className="text-xs font-semibold text-slate-400">{label}</p><p className="mt-1 text-2xl font-black tracking-tight">{value}</p><p className={`mt-2 text-xs font-semibold ${color === "amber" ? "text-slate-400" : "text-emerald-600"}`}>{detail}</p></div>;
}

function StoreList({ onManage }: { onManage: () => void }) {
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-100 p-5 md:px-6"><div><h3 className="font-extrabold">내 매장 현황</h3><p className="mt-1 text-xs text-slate-400">최근 업데이트된 매장 정보예요.</p></div><button onClick={onManage} className="text-sm font-bold text-indigo-600">전체보기</button></div><div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-400"><tr><th className="px-6 py-3 font-semibold">매장명</th><th className="px-6 py-3 font-semibold">카테고리</th><th className="px-6 py-3 font-semibold">고객 성비</th><th className="px-6 py-3 font-semibold">평균 소음</th><th className="px-6 py-3 font-semibold">최근 기록</th></tr></thead><tbody className="divide-y divide-slate-100">{stores.map((store, index) => <tr key={store.name} className="hover:bg-slate-50/80"><td className="px-6 py-4"><div className="flex items-center gap-3"><span className={`grid size-9 place-items-center rounded-lg font-extrabold ${index === 0 ? "bg-indigo-100 text-indigo-700" : index === 1 ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{store.name[0]}</span><span className="font-bold">{store.name}</span></div></td><td className="px-6 py-4 text-slate-500">{store.category}</td><td className="px-6 py-4"><span className="font-bold text-indigo-600">여 {store.gender}%</span><span className="text-slate-400"> · 남 {100 - store.gender}%</span></td><td className="px-6 py-4 font-semibold">{store.noise} dB</td><td className="px-6 py-4 text-slate-400">{store.updated}</td></tr>)}</tbody></table></div></section>;
}

function StoreManagement({ selected, female, noise, onSelect, onFemale, onNoise, onSave }: { selected: number; female: number; noise: number; onSelect: (i: number) => void; onFemale: (n: number) => void; onNoise: (n: number) => void; onSave: () => void }) {
  return <div className="space-y-6">
    <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end"><div><h2 className="text-2xl font-extrabold">매장 데이터 관리</h2><p className="mt-2 text-sm text-slate-500">매장별 고객 성비와 소음 데이터를 기록하고 관리해요.</p></div><button className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold shadow-sm"><Icon name="plus" className="size-4" />새 매장 등록</button></div>
    <div className="grid gap-6 xl:grid-cols-[0.8fr_1.4fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><p className="px-2 pb-3 text-xs font-bold text-slate-400">등록된 매장 3</p><div className="space-y-2">{stores.map((store, i) => <button key={store.name} onClick={() => onSelect(i)} className={`flex w-full items-center gap-3 rounded-xl p-3 text-left transition ${selected === i ? "bg-indigo-50 ring-1 ring-indigo-100" : "hover:bg-slate-50"}`}><span className={`grid size-11 place-items-center rounded-xl font-black ${selected === i ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500"}`}>{store.name[0]}</span><span className="min-w-0 flex-1"><span className="block font-bold">{store.name}</span><span className="mt-0.5 block truncate text-xs text-slate-400">{store.category}</span></span><Icon name="chevron" className="size-4 text-slate-300" /></button>)}</div></section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
        <div className="flex items-start justify-between border-b border-slate-100 pb-5"><div><div className="flex items-center gap-2"><h3 className="text-xl font-extrabold">{stores[selected].name}</h3><span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-600">운영중</span></div><p className="mt-1 text-sm text-slate-400">{stores[selected].category}</p></div><button className="rounded-lg border border-slate-200 p-2 text-slate-500"><Icon name="edit" className="size-4" /></button></div>
        <div className="mt-7"><div className="flex items-center justify-between"><div><p className="font-extrabold">방문 고객 성비</p><p className="mt-1 text-xs text-slate-400">오늘 방문한 고객 기준으로 입력해 주세요.</p></div><Icon name="users" className="size-6 text-indigo-500" /></div><div className="mt-6 grid grid-cols-2 gap-4"><div className="rounded-xl bg-indigo-50 p-4"><p className="text-xs font-semibold text-indigo-500">여성 고객</p><p className="mt-1 text-2xl font-black text-indigo-700">{female}%</p></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold text-slate-400">남성 고객</p><p className="mt-1 text-2xl font-black">{100 - female}%</p></div></div><input type="range" min="0" max="100" value={female} onChange={(e) => onFemale(Number(e.target.value))} className="mt-5 w-full accent-indigo-600" aria-label="여성 고객 비율" /></div>
        <div className="mt-8 border-t border-slate-100 pt-7"><div className="flex items-center justify-between"><div><p className="font-extrabold">평균 소음</p><p className="mt-1 text-xs text-slate-400">현재 매장의 평균 소음 수준을 기록해 주세요.</p></div><Icon name="volume" className="size-6 text-amber-500" /></div><div className="mt-5 flex items-center gap-5"><div className="min-w-28 rounded-xl bg-amber-50 p-4"><p className="text-3xl font-black text-amber-700">{noise}<span className="ml-1 text-sm">dB</span></p></div><div className="flex-1"><input type="range" min="30" max="90" value={noise} onChange={(e) => onNoise(Number(e.target.value))} className="w-full accent-amber-500" aria-label="평균 소음" /><div className="mt-1 flex justify-between text-[10px] text-slate-400"><span>조용함 30</span><span>보통 60</span><span>시끄러움 90</span></div></div></div></div>
        <button onClick={onSave} className="mt-8 w-full rounded-xl bg-indigo-600 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700">오늘의 데이터 저장하기</button>
      </section>
    </div>
  </div>;
}

function Profile({ email, phone, onEmail, onPhone, onSave }: { email: string; phone: string; onEmail: (v: string) => void; onPhone: (v: string) => void; onSave: () => void }) {
  const submit = (e: FormEvent) => { e.preventDefault(); onSave(); };
  return <div className="mx-auto max-w-3xl"><div><h2 className="text-2xl font-extrabold">개인정보 관리</h2><p className="mt-2 text-sm text-slate-500">계정 정보와 연락처를 안전하게 관리하세요.</p></div><div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center gap-4 border-b border-slate-100 p-6"><div className="grid size-16 place-items-center rounded-2xl bg-amber-100 text-2xl font-black text-amber-700">김</div><div><h3 className="text-lg font-extrabold">김민준</h3><p className="mt-1 text-sm text-slate-400">매장로그 오너 · 2024년 3월 가입</p></div></div><form onSubmit={submit} className="space-y-6 p-6"><div><label className="mb-2 block text-sm font-bold">이메일 주소</label><div className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100"><Icon name="mail" className="size-5 text-slate-400" /><input type="email" value={email} onChange={(e) => onEmail(e.target.value)} className="w-full bg-transparent text-sm outline-none" /></div><p className="mt-2 text-xs text-slate-400">로그인과 주요 알림에 사용되는 이메일이에요.</p></div><div><label className="mb-2 block text-sm font-bold">휴대전화 번호</label><div className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100"><Icon name="phone" className="size-5 text-slate-400" /><input type="tel" value={phone} onChange={(e) => onPhone(e.target.value)} className="w-full bg-transparent text-sm outline-none" /></div></div><div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-6"><button type="button" className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-bold text-slate-600">취소</button><button type="submit" className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-200">변경사항 저장</button></div></form></div><div className="mt-5 flex items-start gap-3 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-900"><Icon name="settings" className="mt-0.5 size-5 shrink-0 text-indigo-500" /><p className="leading-6"><strong>개인정보는 안전하게 보호돼요.</strong><br /><span className="text-indigo-600">수정된 연락처는 본인 확인 및 매장 운영 알림 용도로만 사용됩니다.</span></p></div></div>;
}

export default App;
