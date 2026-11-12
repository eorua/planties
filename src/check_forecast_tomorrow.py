"""실시간 예보(src/forecast_tomorrow.py)의 입력 계산이 학습 때(src/build_features.py)와 같은지 확인한다.

저장소의 과거 자료를 기상청 API·EPSIS 응답과 같은 모양으로 바꿔 실시간 계산 함수에 넣고,
특징 표(data/features/daily_features.csv)의 같은 날 값과 비교한다. 인터넷이 필요 없다.

실행: python src/check_forecast_tomorrow.py   → "N일 × M항목 모두 일치"
"""
import json

import numpy as np
import pandas as pd

import forecast_tomorrow as F
import train as T

live = json.loads((F.OUT / "live_thresholds.json").read_text(encoding="utf-8"))
feats = live["features"]
df, _ = T.load()
ref = df.set_index("date")
rng = np.random.default_rng(0)
days = sorted(rng.choice(df.date[(df.date >= "2026-01-10") & (df.date <= "2026-10-31")].values, 40, replace=False))
days += ["2026-05-05", "2026-10-03", "2026-10-05", "2026-10-10", "2026-02-17"]   # 연휴·대체공휴일 포함
bad = []
for d in sorted(set(days)):
    main, d2, load = F.offline_sources(d)
    row = F.build_row(d, main, d2, load, False)
    for c in feats:
        a, b = row[c], ref.loc[d, c]
        if (pd.isna(a) and pd.isna(b)) or (pd.notna(a) and pd.notna(b) and abs(float(a) - float(b)) < 1e-6 + 1e-6 * abs(b)):
            continue
        bad.append((d, c, a, b))
n = len(set(days))
if bad:
    print(pd.DataFrame(bad, columns=["date", "feature", "live", "train"]).to_string(index=False))
    raise SystemExit(f"{n}일 중 {len(bad)}칸이 다르다")
print(f"{n}일 × {len(feats)}항목 모두 일치")
