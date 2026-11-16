"""
T1 산출물 자동 생성 — 코드(models.py, 라우터)에서 직접 뽑으므로 문서와 코드가 어긋나지 않는다.
사용법 (프로젝트 루트에서): python scripts/export_docs.py

  docs/schema.sql     PostgreSQL DDL (Render/Neon/Supabase 에 그대로 실행 가능)
  docs/ERD.md         Mermaid ERD (노션·깃허브에서 그림으로 보임)
  docs/openapi.json   API 명세 (Postman > Import 로 컬렉션 생성, Swagger 는 서버의 /docs)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from backend import models  # noqa: F401
from backend.db import Base
from backend.main import app

DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# ---------------------------------------------------------------- DDL
dialect = postgresql.dialect()
parts = ["-- NoiseAI DB 스키마 (PostgreSQL). scripts/export_docs.py 로 생성됨 — 직접 고치지 말고 models.py 를 고칠 것\n"]
for table in Base.metadata.sorted_tables:
    ddl = "\n".join(line.rstrip() for line in str(CreateTable(table).compile(dialect=dialect)).strip().splitlines())
    parts.append(ddl + ";\n")
    for idx in sorted(table.indexes, key=lambda i: i.name):
        parts.append(str(CreateIndex(idx).compile(dialect=dialect)).strip() + ";\n")
(DOCS / "schema.sql").write_text("\n".join(parts), encoding="utf-8")

# ---------------------------------------------------------------- ERD
DESC = {
    "users": "점주 계정 + 매장 설정", "tracks": "AI 생성곡 = 재생 대기열", "status_log": "3초마다 소음 dB",
    "seat_events": "키오스크 자리 선택/퇴석", "feedback": "손님 키워드 요청", "sales_hourly": "시간대별 매출",
}
lines = ["# NoiseAI ERD", "", "`scripts/export_docs.py` 로 생성됨.", "", "```mermaid", "erDiagram"]
for table in Base.metadata.sorted_tables:
    lines.append(f"    {table.name} {{")
    for col in table.columns:
        typ = col.type.compile(dialect=dialect).split("(")[0].replace(" ", "_").lower()
        key = "PK" if col.primary_key else ("FK" if col.foreign_keys else "")
        lines.append(f"        {typ} {col.name} {key}".rstrip())
    lines.append("    }")
for table in Base.metadata.sorted_tables:
    for col in table.columns:
        for fk in col.foreign_keys:
            lines.append(f'    {fk.column.table.name} ||--o{{ {table.name} : "{col.name}"')
lines += ["```", "", "| 테이블 | 설명 |", "| --- | --- |"] + [f"| `{k}` | {v} |" for k, v in DESC.items()]
(DOCS / "ERD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- OpenAPI
(DOCS / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print("생성:", ", ".join(str(p.relative_to(ROOT)) for p in (DOCS / "schema.sql", DOCS / "ERD.md", DOCS / "openapi.json")))
