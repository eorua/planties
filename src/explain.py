"""시연·발표용: 위험도 3단계, 날마다 원인 설명, 전력거래소 전날 공지와 비교.

본 모델(src/train.py 와 같은 설정)을 같은 방식(매달 1일, 그 전날까지 자료로 재학습)으로 다시 돌려
2023-07 ~ 2025-12 예측을 만들고, 그 예측으로 아래를 계산한다. train.py 의 결과와 같은지 먼저 확인한다.

1) 위험도 3단계 (2026-11-11 정함, 시험 결과를 보기 전에 원칙으로 정함)
   - 높음: 본 모델 경보 기준 이상 (매달 직전 12개월 예측에서 F1 최대인 값, train.py 와 같음)
   - 주의: 매달 직전 12개월 예측에서 "실제 출력제어일의 90%가 이 값 이상"이 되는 가장 높은 값 이상
           (= 출력제어 10번 중 9번은 적어도 '주의' 이상으로 알리는 선). 높음 기준보다 높으면 높음 기준으로 맞춘다.
   - 낮음: 그 아래
2) 원인 설명: 입력을 10개 묶음(쉬는 날, 계절, 최근 출력제어, 맑음 예보, 비 예보, 기온 예보, 수요, 어제 태양광,
   태양광 설비, 원전)으로
   나누고, 묶음 하나를 그달 학습 자료의 중앙값으로 바꿨을 때 확률이 얼마나 내려가나(= 그 묶음이 올린 몫)를 잰다.
   그달 예측에 쓴 바로 그 모델로 계산한다. 값이 클수록 위험을 올린 원인이다.
   "태양광 설비"(해마다 늘어나는 시장 설비용량)는 그날의 원인이라기보다 "출력제어가 늘어난 시기"를 나타내는 추세라,
   원인 3가지에서 빼고 따로(trend 열) 보여 준다.
3) 전력거래소 전날 공지와 비교 (2024-10 ~ 2025-06: 게시판에 전날 전망 공지가 꾸준히 있던 기간)
   - 공지: 게시판에 그날의 "출력제어 전망" 글이 있으면 경보로 본다 (없으면 경보 없음)
   - 모델: 같은 날짜에 본 모델 경보 (위 '높음')

결과: outputs/demo_days.csv (2025년 날짜별 확률·위험도·원인 3가지), outputs/explain_summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve

import train as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
START, END = T.OOT_START, "2025-12-31"
DEMO = ("2025-01-01", "2025-12-31")
KPX = ("2024-10-01", "2025-06-30")
WATCH_RECALL = 0.90

GROUPS = {
    "쉬는 날": ["is_holiday", "is_workers_day", "is_offday", "offday_run_len", "prev_offday", "next_offday", "dow"],
    "계절": ["month", "doy_sin", "doy_cos"],
    "최근 출력제어": ["curt_lag1", "curt_cnt7", "curt_cnt30", "curt_cnt90", "days_since_curt"],
    "맑음 예보": ["fc_sky_mean", "fc_clear_share", "fc_sw_sky_mean"],
    "비 예보": ["fc_pop_mean", "fc_pop_max", "fc_sw_pop_mean"],
    "기온 예보": ["fc_tmx_mean"],
    "수요": ["dem_mid_lag7", "dem_mid_lag1", "dem_min_lag7"],
    "어제 태양광": ["sol_mid_lag1", "sol_mid_mean7", "sol_share_lag1"],
    "태양광 설비": ["sol_cap_lag1"],   # 해마다 늘어나는 추세 (그날의 원인이라기보다 배경)
    "원전": ["nuc_lag1"],
}
DOW = "월화수목금토일"


def backtest_with_attr(df, feats, params):
    """달마다 재학습 → 그달 확률 + 묶음별 기여도."""
    probs, attrs = [], []
    for m0 in pd.date_range(START, END, freq="MS"):
        m1 = (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        m0 = m0.strftime("%Y-%m-%d")
        trn, tst = df[df.date < m0], df[(df.date >= m0) & (df.date <= m1)]
        use = [c for c in feats if trn[c].notna().any()]
        model = T.make("hgb", **params).fit(trn[use], trn.y)
        X = tst[use]
        p = model.predict_proba(X)[:, 1]
        probs.append(pd.Series(p, index=tst.index))
        med = trn[use].median()
        a = pd.DataFrame(index=tst.index)
        for g, cols in GROUPS.items():
            cols = [c for c in cols if c in use]
            if not cols:
                a[g] = 0.0
                continue
            X2 = X.copy()
            for c in cols:
                X2[c] = med[c]
            a[g] = p - model.predict_proba(X2)[:, 1]
        attrs.append(a)
    return pd.concat(probs), pd.concat(attrs)


def watch_threshold(y, s, target=WATCH_RECALL):
    """실제 출력제어일의 target 비율 이상이 이 값 이상이 되는 가장 높은 값."""
    pos = np.sort(s[y == 1])[::-1]
    if len(pos) == 0:
        return np.nan
    k = int(np.ceil(target * len(pos))) - 1
    return float(pos[k])


def rolling(df, s, a, b, fn):
    out = pd.Series(index=s.index[(df.date[s.index] >= a) & (df.date[s.index] <= b)], dtype=float)
    for m0 in pd.date_range(a, b, freq="MS"):
        start, end = m0.strftime("%Y-%m-%d"), (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        idx = out.index[(df.date[out.index] >= start) & (df.date[out.index] <= end)]
        before = s.index[df.date[s.index] < start]
        k = T.THR_MONTHS
        while True:
            w = before[df.date[before] >= (m0 - pd.DateOffset(months=k)).strftime("%Y-%m-%d")]
            if df.y[w].sum() >= T.THR_MIN_POS or k >= 30:
                break
            k += 3
        out[idx] = fn(df.y[w].values, s[w].values)
    return out


def level_table(df, idx, p, hi, wa):
    lv = np.where(p[idx] >= hi[idx], "높음", np.where(p[idx] >= wa[idx], "주의", "낮음"))
    t = pd.DataFrame({"level": lv, "y": df.y[idx].values})
    g = t.groupby("level").y.agg(["size", "sum"]).reindex(["높음", "주의", "낮음"]).fillna(0).astype(int)
    g["rate"] = (g["sum"] / g["size"].clip(lower=1)).round(3)
    return {k: {"days": int(r["size"]), "curtailed": int(r["sum"]), "rate": float(r["rate"])} for k, r in g.iterrows()}


def reason_text(g, r, hol):
    d = pd.Timestamp(r.date)
    if g == "쉬는 날":
        if r.date in hol:
            return f"쉬는 날 ({hol[r.date]})"
        return f"쉬는 날 ({DOW[d.dayofweek]}요일)" if r.is_offday else f"평일 ({DOW[d.dayofweek]}요일)"
    if g == "계절":
        s = "봄" if d.month in (3, 4, 5) else "여름" if d.month in (6, 7, 8) else "가을" if d.month in (9, 10, 11) else "겨울"
        return f"{s} ({d.month}월)"
    if g == "최근 출력제어":
        y1 = "어제 있음" if r.curt_lag1 == 1 else "어제 없음"
        return f"최근 출력제어 (마지막 뒤 {int(r.days_since_curt)}일, 최근 7일 중 {int(r.curt_cnt7)}일, {y1})"
    if g == "맑음 예보":
        return f"맑음 예보 (5개 지역 맑음 비율 {r.fc_clear_share:.0%})" if pd.notna(r.fc_clear_share) else "맑음 예보 (자료 없음)"
    if g == "비 예보":
        return f"강수확률 예보 (평균 {r.fc_pop_mean:.0f}%)" if pd.notna(r.fc_pop_mean) else "강수확률 예보 (자료 없음)"
    if g == "기온 예보":
        return f"최고기온 예보 ({r.fc_tmx_mean:.1f}°C)" if pd.notna(r.fc_tmx_mean) else "최고기온 예보 (자료 없음)"
    if g == "수요":
        return f"전력수요 (지난주 최저 {r.dem_min_lag7:.1f}GW, 어제 한낮 {r.dem_mid_lag1:.1f}GW)"
    if g == "어제 태양광":
        return f"어제 태양광 (한낮 시장 거래량 {r.sol_mid_lag1:.1f}GW)" if pd.notna(r.sol_mid_lag1) else "어제 태양광"
    if g == "태양광 설비":
        return f"태양광 설비 증가 (시장 설비 {r.sol_cap_lag1:.1f}GW)" if pd.notna(r.sol_cap_lag1) else "태양광 설비"
    if g == "원전":
        return f"원전 (어제 1~16시 평균 {r.nuc_lag1:.1f}GW)" if pd.notna(r.nuc_lag1) else "원전 (자료 없음)"
    return g


def main():
    df, feats = T.load()
    params = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))["chosen_params"]["hgb"]
    p, attr = backtest_with_attr(df, feats, params)

    # train.py 와 같은 예측인지 확인 (시험 기간)
    ref = pd.read_csv(OUT / "test_predictions.csv")
    mine = p[df.index[df.date.isin(ref.date)]].round(4).values
    gap = float(np.max(np.abs(mine - ref.p_hgb.values)))
    assert gap < 1e-3, f"train.py 와 예측이 다르다 (최대 차이 {gap})"

    hi = rolling(df, p, "2024-01-01", END, T.best_threshold)
    wa = rolling(df, p, "2024-01-01", END, watch_threshold)
    wa = np.minimum(wa, hi)
    summary = {"made": "src/explain.py", "check_vs_train_max_gap": round(gap, 6),
               "risk_levels": {"rule": "높음 = 경보 기준(직전 12개월 F1 최대) 이상, 주의 = 직전 12개월 출력제어일의 "
                                       f"{WATCH_RECALL:.0%}가 이 값 이상이 되는 선 이상, 낮음 = 그 아래"}}
    for name, (a, b) in {"val": T.P["val"], "test": T.P["test"]}.items():
        idx = df.index[(df.date >= a) & (df.date <= b)]
        summary["risk_levels"][name] = level_table(df, idx, p, hi, wa)

    # 전력거래소 전날 공지와 비교
    board = pd.read_csv(ROOT / "data" / "clean" / "kpx_board_daily.csv").set_index("date")
    idx = df.index[(df.date >= KPX[0]) & (df.date <= KPX[1])]
    y = df.y[idx].values
    notice = df.date[idx].map(board["notice_forecast"]).fillna(0).astype(int).values
    model = (p[idx].values >= hi[idx].values).astype(int)

    def pr(a):
        h = int(((a == 1) & (y == 1)).sum())
        return {"alerts": int(a.sum()), "hits": h, "false_alarms": int(((a == 1) & (y == 0)).sum()),
                "misses": int(((a == 0) & (y == 1)).sum()), "recall": round(h / max(y.sum(), 1), 3),
                "precision": round(h / max(a.sum(), 1), 3)}
    n = int(notice.sum())
    topn = np.zeros(len(idx), int)
    topn[np.argsort(-p[idx].values)[:n]] = 1
    both = (notice == 1) & (model == 1)
    summary["kpx_compare"] = {
        "period": KPX, "days": int(len(idx)), "curtailed": int(y.sum()),
        "kpx_notice": pr(notice), "model_alert": pr(model),
        "model_top_same_count": {**pr(topn), "note": "공지와 같은 수만큼, 확률이 높은 날부터 경보했다고 볼 때"},
        "model_pr_auc": round(average_precision_score(y, p[idx].values), 3),
        "curtailed_without_notice_caught_by_model": int(((notice == 0) & (model == 1) & (y == 1)).sum()),
        "curtailed_without_notice": int(((notice == 0) & (y == 1)).sum()),
        "both_alert": int(both.sum()),
    }

    # 시연용 날짜별 표 (2025년)
    hol = pd.read_csv(ROOT / "data" / "manual" / "holidays_kr.csv").set_index("date")["name"].to_dict()
    rows = []
    for i in df.index[(df.date >= DEMO[0]) & (df.date <= DEMO[1])]:
        r = df.loc[i]
        lv = "높음" if p[i] >= hi[i] else "주의" if p[i] >= wa[i] else "낮음"
        a = attr.loc[i].sort_values(ascending=False)
        # "태양광 설비"는 해마다 늘어나는 추세라 그날의 원인과 따로 보여 준다 (trend 열)
        daily = a.drop("태양광 설비")
        up = [g for g, v in daily.items() if v > 0.005][:3]
        down = [g for g, v in daily.sort_values().items() if v < -0.005][:2]
        rows.append({"date": r.date, "dow": DOW[pd.Timestamp(r.date).dayofweek], "holiday": hol.get(r.date, ""),
                     "y": int(r.y), "p": round(float(p[i]), 4), "thr_high": round(float(hi[i]), 4),
                     "thr_watch": round(float(wa[i]), 4), "level": lv,
                     "up": " | ".join(f"{reason_text(g, r, hol)}:{a[g]:+.3f}" for g in up),
                     "down": " | ".join(f"{reason_text(g, r, hol)}:{a[g]:+.3f}" for g in down),
                     "trend": f"{reason_text('태양광 설비', r, hol)}:{a['태양광 설비']:+.3f}",
                     "kpx_notice": int(board["notice_forecast"].get(r.date, 0)),
                     "board_reason": ("전력망" if board["reason_grid"].get(r.date, 0) == 1 else "")
                     + ("·수급" if board["reason_supply"].get(r.date, 0) == 1 else ""),
                     "board_hours": (f"{int(board['start_h'][r.date])}~{int(board['end_h'][r.date])}시"
                                     if r.date in board.index and pd.notna(board["start_h"].get(r.date)) else "")})
    demo = pd.DataFrame(rows)
    demo.to_csv(OUT / "demo_days.csv", index=False, encoding="utf-8-sig")
    # 원인 묶음이 상위 1위로 나온 횟수 (2025 하반기, 높음인 날)
    hs = demo[(demo.date >= T.P["test"][0]) & (demo.level == "높음")]
    summary["top_reason_counts_test_high"] = hs.up.str.split(" \\(|:").str[0].value_counts().to_dict()
    (OUT / "explain_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ('check_vs_train_max_gap', 'top_reason_counts_test_high')}, ensure_ascii=False))


if __name__ == "__main__":
    main()
