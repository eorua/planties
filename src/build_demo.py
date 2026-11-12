"""시연 화면 만들기 → demo/index.html (파일 하나, 인터넷 연결 없이 열림).

시연은 공개 자료 모델(outputs/public/)을 쓴다 (docs/MODEL_RESULTS.md 11장). 날짜는 두 시험 기간만 보여 준다.
- 2025-07 ~ 2025-12: 2025년 하반기 시험 (본 모델, src/explain.py → demo_days.csv)
- 2026-01 ~ 2026-10: 2026년 독립 시험 (태양광·원전 입력 없는 N+C 모델, src/explain_2026.py → demo_days_2026.csv)
2025년 상반기는 검증 기간(모델을 고르는 데 쓴 기간)이고, 경보 선을 정할 직전 출력제어 사례가 적어 선이 불안정하므로 뺀다.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "public"
d25 = pd.read_csv(OUT / "demo_days.csv")
d25 = d25[d25.date >= "2025-07-01"].assign(period="2025", label="공식")
d26 = pd.read_csv(OUT / "demo_days_2026.csv").drop(columns="label_source").assign(period="2026")
parts = [d25, d26]
if (OUT / "live_days.csv").exists():   # src/forecast_tomorrow.py 가 만든 실시간 예보
    parts.append(pd.read_csv(OUT / "live_days.csv", dtype=str).assign(period="live"))
d = pd.concat(parts).fillna("")
for c in ("p", "thr_high", "thr_watch"):
    d[c] = d[c].astype(float)
rows = d.to_dict(orient="records")
tpl = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
html = tpl.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
head = '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
(ROOT / "demo" / "index.html").write_text(head + html.replace("<style>", "</head><body>\n<style>", 1) + "\n</body></html>\n", encoding="utf-8")
print("demo/index.html", len(rows), "일 (2025년", len(d25), "일, 2026년", len(d26), "일, 실시간", len(parts) - 2 and len(parts[2]), "일)")
