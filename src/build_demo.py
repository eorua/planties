"""시연 화면 만들기 → demo/index.html (파일 하나, 인터넷 연결 없이 열림).

시연은 본 모델(outputs/, 최근 출력제어 여부와 전날 공지를 안다고 가정)을 쓴다 (docs/MODEL_RESULTS.md 15장).
공개 자료만 쓴 결과(outputs/public/)는 성적 칸에 하한으로 한 줄 적는다. 날짜는 두 시험 기간만 보여 준다.
- 2025-07 ~ 2025-12: 2025년 하반기 시험 (본 모델, src/explain.py → demo_days.csv)
- 2026-01 ~ 2026-10: 2026년 독립 시험 (태양광·원전 입력 없는 N+C 모델, src/explain_2026.py → demo_days_2026.csv)
2025년 상반기는 검증 기간(모델을 고르는 데 쓴 기간)이고, 경보 선을 정할 직전 출력제어 사례가 적어 선이 불안정하므로 뺀다.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PUB = OUT / "public"
d25 = pd.read_csv(OUT / "demo_days.csv")
d25 = d25[d25.date >= "2025-07-01"].assign(period="2025", label="공식")
d26 = pd.read_csv(OUT / "demo_days_2026.csv").drop(columns="label_source").assign(period="2026")
parts = [d25, d26]
if (OUT / "live_days.csv").exists():   # src/forecast_tomorrow.py 가 만든 실시간 예보
    parts.append(pd.read_csv(OUT / "live_days.csv", dtype=str).assign(period="live"))
d = pd.concat(parts).fillna("")
for c in ("p", "thr_high", "thr_watch"):
    d[c] = d[c].astype(float)
for c in ("prob", "thr_vhigh"):
    d[c] = d[c].astype(float)
rows = d.to_dict(orient="records")


def kpis(x, s4):
    """성적 칸 숫자: 결과 파일에서 계산한다 (손으로 적지 않는다)."""
    al = x.level.isin(["높음", "매우 높음"])
    pct = lambda v: f"{v['curtailed'] / max(v['days'], 1):.0%}"
    return {"HIT": f"{int((al & (x.y == 1)).sum())} / {int(x.y.sum())}일", "FA": str(int((al & (x.y == 0)).sum())),
            "VH": pct(s4["매우 높음"]), "VH_N": f"{s4['매우 높음']['days']}일 중 {s4['매우 높음']['curtailed']}일",
            "LO": pct(s4["낮음"]), "LO_N": f"{s4['낮음']['days']}일 중 {s4['낮음']['curtailed']}일",
            "STAIR": " / ".join(f"{k} {pct(v)}" for k, v in s4.items())}


s25 = json.loads((OUT / "explain_summary.json").read_text(encoding="utf-8"))["risk_levels4"]["test"]
s26 = json.loads((OUT / "explain_2026_summary.json").read_text(encoding="utf-8"))["risk_levels4"]["합계 (1/1~10/31)"]
K = {f"K25_{k}": v for k, v in kpis(d25, s25).items()} | {f"K26_{k}": v for k, v in kpis(d26, s26).items()}
al26 = d26.level.isin(["높음", "매우 높음"]) & (d26.y == 1)
sp = (d26.date >= "2026-03-01") & (d26.date <= "2026-05-31")
K["K26_SPRING"] = f"{int((al26 & sp).sum())} / {int((sp & (d26.y == 1)).sum())}일"
nn = (d26.kpx_notice == 0) & (d26.y == 1)
K["K26_NONOTICE"] = f"{int((al26 & nn).sum())} / {int(nn.sum())}일"
tpl = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
for tag, f, a, folder in (("K25PUB", "demo_days.csv", "2025-07-01", PUB), ("K26PUB", "demo_days_2026.csv", "2026-01-01", PUB),
                          ("K25POST", "demo_days.csv", "2025-07-01", OUT / "posted"),
                          ("K26POST", "demo_days_2026.csv", "2026-01-01", OUT / "posted")):   # 하한(공개 자료만), 민감도(게시된 전망만)
    x = pd.read_csv(folder / f)
    x = x[x.date >= a]
    al = x.level.isin(["높음", "매우 높음"])
    K[f"{tag}_HIT"] = f"{int((al & (x.y == 1)).sum())} / {int(x.y.sum())}일"
    K[f"{tag}_FA"] = str(int((al & (x.y == 0)).sum()))
pre = json.loads((OUT / "prereg_2026" / "test_2026.json").read_text(encoding="utf-8"))["results"]["합계 (1/1~10/31)"]["N+C"]
K["K26_PREREG"] = f"{pre['hits']} / {pre['n_pos']}일, 헛경보 {pre['false_alarms']}번"
for k in sorted(K, key=len, reverse=True):   # 긴 이름부터 (K25_VH_N 이 K25_VH 보다 먼저)
    tpl = tpl.replace(f"__{k}__", K[k])
assert "__K2" not in tpl, "채워지지 않은 성적 칸이 있다"
html = tpl.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
head = '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
(ROOT / "demo" / "index.html").write_text(head + html.replace("<style>", "</head><body>\n<style>", 1) + "\n</body></html>\n", encoding="utf-8")
print("demo/index.html", len(rows), "일 (2025년", len(d25), "일, 2026년", len(d26), "일, 실시간", len(parts) - 2 and len(parts[2]), "일)")
