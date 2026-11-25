"""2026년 독립 시험의 '출력제어 시간 기준' 집계 (예선 PPT 표지·2장 숫자의 근거).

본 모델(outputs/test_2026_predictions.csv, alert_N+C)이 전날 "높음" 이상으로 알린 날에
육지 출력제어가 걸린 시간이 전체 출력제어 시간 중 얼마인지 센다.

시간 기준
- 육지에서 태양광·풍력 중 어느 지역이든 출력제어가 있던 시간대를 하루 단위로 합친다(겹치면 1시간).
- 1~6월: 공식 실적(data/clean/curtailment_daily.csv)의 시간 칸.
- 7~10월: 게시판 실적 글(data/clean/kpx_board_daily.csv)의 end_h - start_h.
  공식 실적과 겹치는 149일에서 이 방식은 89%가 같은 시간 수를 준다.
- 시간이 공개되지 않은 날(10월 2·5·6일)은 뺀다. 셋 다 경보한 날이라 넣으면 비율은 올라간다.

실행: python src/curtail_hours_2026.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
H = [f"h{i:02d}_raw" for i in range(1, 25)]


def official_hours():
    c = pd.read_csv(ROOT / "data/clean/curtailment_daily.csv", parse_dates=["date"])
    c = c[c.grid == "육지"]
    out = {}
    for d, g in c.groupby("date"):
        m = np.zeros(24, bool)
        for _, r in g.iterrows():
            m |= r[H].astype(str).str.contains("출력제어").values
        out[d] = int(m.sum())
    return out


def main():
    p = pd.read_csv(ROOT / "outputs/test_2026_predictions.csv", parse_dates=["date"])
    b = pd.read_csv(ROOT / "data/clean/kpx_board_daily.csv", parse_dates=["date"])
    b = b[b.occurred == 1].dropna(subset=["start_h"]).set_index("date")
    off = official_hours()

    rows = []
    for _, r in p[p.y == 1].iterrows():
        d = r.date
        if d in off:
            h, src = off[d], "공식"
        elif d in b.index:
            h, src = float(b.loc[d, "end_h"] - b.loc[d, "start_h"]), "게시판"
        else:
            h, src = np.nan, "미공개"
        rows.append((d.date(), src, h, int(r["alert_N+C"])))
    df = pd.DataFrame(rows, columns=["date", "hours_source", "hours", "alert"])
    known = df.dropna(subset=["hours"])

    tot, hit = known.hours.sum(), known[known.alert == 1].hours.sum()
    print(f"출력제어일 {len(df)}일, 시간 확인 {len(known)}일 (미공개: {df[df.hours.isna()].date.tolist()})")
    print(f"출력제어 시간 {tot:.0f}시간 중 경보한 날 {hit:.0f}시간 = {hit / tot:.1%}")
    print(f"경보한 날 평균 {known[known.alert == 1].hours.mean():.1f}시간, "
          f"놓친 날 평균 {known[known.alert == 0].hours.mean():.1f}시간")

    t = p[p.kpx_notice == 1]
    print(f"전력거래소 전망을 낸 날 {len(t)}일 중 실제 출력제어 {int(t.y.sum())}일 = {t.y.mean():.1%}")
    print(f"출력제어 {int(p.y.sum())}일 중 전망 있던 날 {int(((p.kpx_notice == 1) & (p.y == 1)).sum())}일")


if __name__ == "__main__":
    main()
