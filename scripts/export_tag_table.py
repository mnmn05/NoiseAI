"""
T5 -> T2 전달용 태그 매핑표(엑셀) 생성. prompt_engine.py 를 실제로 실행해서 뽑으므로 표와 코드가 항상 같다.
사용법 (프로젝트 루트에서): python scripts/export_tag_table.py [저장할 경로.xlsx]
필요: pip install openpyxl
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from backend import prompt_engine as pe

out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "tag_mapping_v2.xlsx"
wb = Workbook()
HEAD = PatternFill("solid", fgColor="DDE7F5")


def sheet(title, headers, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.font, c.fill = Font(bold=True), HEAD
    for r in rows:
        ws.append(r)
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    return ws


wb.remove(wb.active)
ko = {"cafe": "카페", "bar": "주점", "restaurant": "음식점"}
dict_rows = [("업종", ko[k], k, ", ".join(w for w, _ in v)) for k, v in pe.CATEGORY_KEYWORDS.items()]
dict_rows += [("분위기", next(a for a, b in pe.MOOD_ALIASES.items() if b == k and not a.isascii()), k,
               ", ".join(w for w, _ in v)) for k, v in pe.MOOD_KEYWORDS.items()]
dict_rows += [("연령대", o, pe.AGE_ALIASES[o], ", ".join(w for w, _ in pe.AGE_KEYWORDS[pe.AGE_ALIASES[o]]))
              for o in pe.OPTIONS["age_group"]]
dict_rows += [("손님 버튼", k, en, kind) for k, (en, kind) in pe.GUEST_KEYWORDS.items()]
sheet("키워드 사전", ["구분", "입력값(화면)", "내부 코드", "음악 스타일 키워드 / 종류"], dict_rows, [10, 14, 14, 50])

levels = [("quiet", 45, "조용함 (≤50dB)"), ("normal", 62, "보통"), ("loud", 80, "시끄러움 (≥75dB)")]
rows = []
for strat in ("stable", "lively"):
    for level, db, label in levels:
        for cat in pe.OPTIONS["category"]:
            for age in pe.OPTIONS["age_group"]:
                for mood in [None] + pe.OPTIONS["mood"]:
                    r = pe.build_prompt_detail(db, pe.StoreProfile(cat, age, None, mood), strat)
                    rows.append((pe.STRATEGY_LABEL_KO[strat], label, cat, age, mood or "(선택 안 함)",
                                 ", ".join(r.keywords), ", ".join(r.dropped) or "-", r.prompt))
sheet("조합표(전략×소음)", ["전략", "소음", "업종", "연령대", "분위기", "최종 키워드", "버려진 키워드(모순)", "MusicGen 프롬프트"],
      rows, [8, 16, 8, 10, 12, 50, 22, 80])

sit_rows = []
cases = [("focus", "점유율 높음(≥70%) + 조용함", dict(occupancy=0.9), 45),
         ("hold", "점유율 낮음(≤30%) + 시끄러움 (직전 보통)", dict(occupancy=0.1, prev_level="normal"), 80),
         ("quiet_request", "'조용했으면' 버튼 (10분)", dict(quiet_requested=True), 80),
         ("guest", "손님 키워드: 재즈 + 따뜻한", dict(guest_keywords=["재즈", "따뜻한"]), 62)]
for key, label, kw, db in cases:
    for strat in ("stable", "lively"):
        r = pe.build_prompt_detail(db, pe.StoreProfile("카페", "20대", None, None), strat, **kw)
        sit_rows.append((label, pe.STRATEGY_LABEL_KO[strat], r.situation, ", ".join(r.keywords), r.prompt))
sheet("3요소·피드백 예시(카페 20대)", ["상황", "전략", "판정", "최종 키워드", "MusicGen 프롬프트"], sit_rows, [34, 8, 14, 50, 80])

rules = [
    ("1", "우선순위", "손님 피드백('조용했으면' > 키워드) > 3요소 판정(점유율+소음) > 전략별 소음 규칙 > 분위기 > 업종 > 연령대"),
    ("2", "소음 구간", f"평균 dB(최근 4분, 샘플 20개 이상). 진입: ≥{pe.LOUD_DB:.0f} 시끄러움 / ≤{pe.QUIET_DB:.0f} 조용함. "
                    f"해제: 시끄러움은 {pe.LOUD_EXIT_DB:.0f} 미만, 조용함은 {pe.QUIET_EXIT_DB:.0f} 초과 (히스테리시스)"),
    ("3", "안정형", "시끄러울수록 lofi beats·acoustic guitar·soft jazz + steady rhythm/slow tempo/calm (업종 장르 대체, 말소리 마스킹)"),
    ("4", "활기형", "시끄러울수록 fast tempo, energetic, rhythmic / 조용하면 slow tempo, calm"),
    ("5", "3요소", f"점유율 ≥{pe.OCC_HIGH:.0%} + 조용함 -> 집중용 BGM / 점유율 ≤{pe.OCC_LOW:.0%} + 시끄러움 -> 직전 분위기 유지"),
    ("6", "모순 제거", "느림(" + ", ".join(sorted(pe.LOW_ENERGY)) + ") vs 빠름(" + ", ".join(sorted(pe.HIGH_ENERGY)) + ")"),
    ("7", "안전 장르", "장르가 모두 빠지면 카페 lofi beats / 주점 chill house / 음식점 jazz"),
    ("8", "성별", "저장만 하고 프롬프트에는 쓰지 않음"),
    ("9", "출처", "backend/prompt_engine.py 를 scripts/export_tag_table.py 로 실행해서 뽑은 값"),
]
sheet("규칙", ["No", "항목", "내용"], rules, [5, 12, 110])
out.parent.mkdir(parents=True, exist_ok=True)
wb.save(out)
print(f"저장: {out}  (조합 {len(rows)}행)")
