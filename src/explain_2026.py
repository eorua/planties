"""시연용 2026년 날짜별 예보: 2026년 독립 시험의 주 모델(N+C)로 위험도 3단계와 원인을 만든다.

- 모델·학습 방식은 src/test_2026.py 와 같다 (태양광·원전 입력 없음, 매달 1일 재학습, 2023-07부터).
  결과가 test_2026_predictions.csv 의 p_N+C, alert_N+C 와 같은지 먼저 확인한다.
- 위험도·원인 계산은 src/explain.py 와 같은 규칙 (높음 = 경보 기준, 주의 = 직전 12개월 출력제어일 90% 선).
- 기본은 공개 자료 변형 (PLANTIES_VARIANT=public, 시연에 쓰는 것). 결과: outputs/public/demo_days_2026.csv

2026-06-14 이후 정답은 게시판 실적이고, 10월 2일 이후 실적 글은 2026-11-12 현재 아직 올라오지 않았다 (잠정).
"""
import json

import numpy as np
import pandas as pd

import experiments as E
import explain as X
import train as T

OUT = T.OUT
START, END = "2023-07-01", "2026-10-31"
DEMO = ("2026-01-01", "2026-10-31")
LABEL_FINAL_UNTIL = "2026-10-01"   # 게시판에 실적 글이 올라온 마지막 사건일 (2026-11-12 확인)

# explain.GROUPS 에 2026년 모델의 새 항목(E.NEW)을 같은 뜻의 묶음으로 더한다
GROUPS = {g: list(c) for g, c in X.GROUPS.items()}
GROUPS["맑음 예보"] += ["fc_clear_share_d2", "fc_clear_delta"]
GROUPS["비 예보"] += ["fc_pop_delta"]
GROUPS["기온 예보"] += ["fc_cool_deg", "fc_heat_deg"]
GROUPS["수요"] += ["dem_mid_lastsame"]


def backtest_with_attr(df, feats):
    probs, attrs = [], []
    for m0 in pd.date_range(START, END, freq="MS"):
        m1 = (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        m0 = m0.strftime("%Y-%m-%d")
        trn, tst = df[df.date < m0], df[(df.date >= m0) & (df.date <= m1)]
        use = [c for c in feats if trn[c].notna().any()]
        model = E.hgb(use, False).fit(trn[use], trn.y)
        Xt = tst[use]
        p = model.predict_proba(Xt)[:, 1]
        probs.append(pd.Series(p, index=tst.index))
        a = pd.DataFrame(index=tst.index)
        if m0 >= DEMO[0]:   # 원인은 시연 기간만 계산
            med = trn[use].median()
            for g, cols in GROUPS.items():
                cols = [c for c in cols if c in use]
                if not cols:
                    a[g] = 0.0
                    continue
                X2 = Xt.copy()
                for c in cols:
                    X2[c] = med[c]
                a[g] = p - model.predict_proba(X2)[:, 1]
        attrs.append(a)
    return pd.concat(probs), pd.concat(attrs)


def main():
    df, base = T.load()
    n = [c for c in base if not c.startswith("sol_") and c != "nuc_lag1"]
    feats = n + E.NEW
    p, attr = backtest_with_attr(df, feats)

    ref = pd.read_csv(OUT / "test_2026_predictions.csv")
    idx = df.index[df.date.isin(ref.date)]
    gap = float(np.max(np.abs(p[idx].round(4).values - ref["p_N+C"].values)))
    assert gap < 1e-3, f"test_2026.py 와 예측이 다르다 (최대 차이 {gap})"

    hi = X.rolling(df, p, DEMO[0], DEMO[1], T.best_threshold)
    wa = np.minimum(X.rolling(df, p, DEMO[0], DEMO[1], X.watch_threshold), hi)
    alert = (p[hi.index] >= hi).astype(int).values
    diff = int((alert != ref["alert_N+C"].values).sum())
    assert diff == 0, f"test_2026.py 와 경보가 {diff}일 다르다"

    board = pd.read_csv(X.ROOT / "data" / "clean" / "kpx_board_daily.csv").set_index("date")
    hol = pd.read_csv(X.ROOT / "data" / "manual" / "holidays_kr.csv").set_index("date")["name"].to_dict()
    rows = []
    for i in hi.index:
        r = df.loc[i]
        lv = "높음" if p[i] >= hi[i] else "주의" if p[i] >= wa[i] else "낮음"
        a = attr.loc[i].dropna().sort_values(ascending=False)
        up = [g for g, v in a.items() if v > 0.005][:3]
        down = [g for g, v in a.sort_values().items() if v < -0.005][:2]
        src = r.label_source if "label_source" in df.columns else ""
        rows.append({"date": r.date, "dow": X.DOW[pd.Timestamp(r.date).dayofweek], "holiday": hol.get(r.date, ""),
                     "y": int(r.y), "p": round(float(p[i]), 4), "thr_high": round(float(hi[i]), 4),
                     "thr_watch": round(float(wa[i]), 4), "level": lv,
                     "up": " | ".join(f"{X.reason_text(g, r, hol)}:{a[g]:+.3f}" for g in up),
                     "down": " | ".join(f"{X.reason_text(g, r, hol)}:{a[g]:+.3f}" for g in down),
                     "trend": "",
                     "kpx_notice": int(board["notice_forecast"].get(r.date, 0)),
                     "board_reason": ("전력망" if board["reason_grid"].get(r.date, 0) == 1 else "")
                     + ("·수급" if board["reason_supply"].get(r.date, 0) == 1 else ""),
                     "board_hours": (f"{int(board['start_h'][r.date])}~{int(board['end_h'][r.date])}시"
                                     if r.date in board.index and pd.notna(board["start_h"].get(r.date)) else ""),
                     "label": ("공식" if r.date <= "2026-06-13" else
                               "게시판" if r.date <= LABEL_FINAL_UNTIL else "게시판 (잠정)"),
                     "label_source": src})
    demo = pd.DataFrame(rows)
    demo.to_csv(OUT / "demo_days_2026.csv", index=False, encoding="utf-8-sig")

    summ = {"made": "src/explain_2026.py", "model": "N+C (test_2026.py 주 모델)", "check_vs_test_2026_max_gap": round(gap, 6)}
    for name, (a, b) in {"시험1 (1/1~6/13)": ("2026-01-01", "2026-06-13"), "봄 (3~5월)": ("2026-03-01", "2026-05-31"),
                         "합계 (1/1~10/31)": DEMO}.items():
        k = df.index[(df.date >= a) & (df.date <= b)]
        summ[name] = X.level_table(df, k, p, hi, wa)
    hs = demo[demo.level == "높음"]
    summ["top_reason_counts_high"] = hs.up.str.split(" \\(|:").str[0].value_counts().to_dict()
    (OUT / "explain_2026_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
