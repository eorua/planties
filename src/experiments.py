"""개선안 실험: 새 입력 항목, 방향 제약(단조 제약), 경보 기준 정하는 방식.

모두 매달 재학습 방식으로 2024-01 ~ 2025-12 를 예측해 두고,
- 고르기: 넓힌 검증 기간 2024-03 ~ 2025-06 (출력제어 82일)
- 기록만: 시험 기간 2025-07 ~ 2025-12
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, precision_score, recall_score

import train as T

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
VAL = ("2024-03-01", "2025-06-30")
TEST = ("2025-07-01", "2025-12-31")
NEW = ["fc_clear_share_d2", "fc_clear_delta", "fc_pop_delta", "fc_cool_deg", "fc_heat_deg", "dem_mid_lastsame"]

# 전력계통 상식으로 정한 방향: +1 = 클수록 출력제어 위험 증가, -1 = 클수록 감소, 없으면 제약 없음
DIRECTION = {
    "is_offday": 1, "is_holiday": 1, "offday_run_len": 1,
    "fc_clear_share": 1, "fc_sky_mean": -1, "fc_sw_sky_mean": -1,
    "fc_pop_mean": -1, "fc_pop_max": -1, "fc_sw_pop_mean": -1,
    "fc_cool_deg": -1, "fc_heat_deg": -1,
    "dem_mid_lag7": -1, "dem_mid_lag1": -1, "dem_min_lag7": -1, "dem_mid_lastsame": -1,
    "sol_cap_lag1": 1, "sol_mid_mean7": 1,
    "nuc_lag1": 1,
    "curt_lag1": 1, "curt_cnt7": 1, "curt_cnt30": 1, "curt_cnt90": 1, "days_since_curt": -1,
}


def hgb(cols, mono):
    cst = {c: DIRECTION[c] for c in cols if mono and c in DIRECTION}
    return HistGradientBoostingClassifier(learning_rate=0.1, max_depth=3, max_iter=300, l2_regularization=1.0,
                                          min_samples_leaf=20, class_weight="balanced", random_state=0,
                                          monotonic_cst=cst or None)


def backtest(df, feats, mono, a, b):
    out = []
    for m0 in pd.date_range(a, b, freq="MS"):
        m1 = (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        m0 = m0.strftime("%Y-%m-%d")
        trn, tst = df[df.date < m0], df[(df.date >= m0) & (df.date <= m1)]
        use = [c for c in feats if trn[c].notna().any()]
        out.append(pd.Series(hgb(use, mono).fit(trn[use], trn.y).predict_proba(tst[use])[:, 1], index=tst.index))
    return pd.concat(out)


def f1_thr(y, s):
    if y.sum() == 0:
        return None
    p, r, t = precision_recall_curve(y, s)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    return float(t[int(np.nanargmax(f1[:-1]))])


SEASON = {7: "한여름", 8: "한여름", 12: "한겨울", 1: "한겨울"}


def season(m):
    return SEASON.get(m, "봄가을")


def thresholds(df, s, policy, a, b, fixed=None):
    """a~b 의 날마다 경보 기준을 정한다. 기준은 그달 1일 이전 예측 결과만 보고 정한다."""
    thr = pd.Series(index=df.index[(df.date >= a) & (df.date <= b)], dtype=float)
    month = pd.to_datetime(df.date).dt.month
    for m0 in pd.date_range(a, b, freq="MS"):
        idx = df.index[(df.date >= m0.strftime("%Y-%m-%d")) & (df.date <= (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"))]
        past = df.index[(df.date < m0.strftime("%Y-%m-%d")) & (df.date >= (m0 - pd.DateOffset(months=12)).strftime("%Y-%m-%d"))]
        past = past[past.isin(s.index)]
        if policy == "fixed":
            v = fixed
        elif policy == "rolling":
            v = f1_thr(df.y[past], s[past])
        elif policy == "seasonal":
            same = past[month[past].map(season) == season(m0.month)]
            v = f1_thr(df.y[same], s[same])
            if v is None:  # 같은 계절에 출력제어가 없었으면: 그 계절 과거 예측 중 가장 높은 값보다 커야 경보
                v = float(s[same].max()) + 1e-6 if len(same) else f1_thr(df.y[past], s[past])
        thr[idx] = v
    return thr


def summarize(y, s, thr):
    pred = (s >= thr).astype(int)
    return {"pr_auc": round(average_precision_score(y, s), 3), "precision": round(precision_score(y, pred, zero_division=0), 3),
            "recall": round(recall_score(y, pred), 3), "f1": round(f1_score(y, pred), 3),
            "alerts": int(pred.sum()), "hits": int((pred & y).sum()), "false_alarms": int((pred & (1 - y)).sum()),
            "misses": int(((1 - pred) & y).sum())}


def main():
    df, base = T.load()          # 본 모델 항목 (새 항목 제외)
    feats_all = base + NEW
    variants = {"A 기존 항목": (base, False), "B 기존 + 방향 제약": (base, True),
                "C 새 항목 추가": (feats_all, False), "D 새 항목 + 방향 제약": (feats_all, True)}
    vmask = (df.date >= VAL[0]) & (df.date <= VAL[1])
    tmask = (df.date >= TEST[0]) & (df.date <= TEST[1])
    preds, rows = {}, []
    for name, (feats, mono) in variants.items():
        s = backtest(df, feats, mono, "2023-07-01", TEST[1])
        preds[name] = s
        v, t = s[vmask[s.index]], s[tmask[s.index]]
        yv, yt = df.y[v.index], df.y[t.index]
        y24 = df.y[v.index][df.date[v.index] < "2025-01-01"]
        rows.append({"변형": name, "넓힌 검증 PR-AUC": round(average_precision_score(yv, v), 3),
                     "2024년 3~12월": round(average_precision_score(y24, v[y24.index]), 3),
                     "2025년 1~6월": round(average_precision_score(df.y[v.index[df.date[v.index] >= "2025-01-01"]],
                                                                v[df.date[v.index] >= "2025-01-01"]), 3),
                     "시험 PR-AUC(기록)": round(average_precision_score(yt, t), 3)})
        print(rows[-1], flush=True)
    feat_table = pd.DataFrame(rows)
    best = max(rows, key=lambda r: r["넓힌 검증 PR-AUC"])["변형"]
    s = preds[best]

    # 경보 기준 방식 비교 — 공정하게: 모든 방식이 "그달 1일 이전 예측 결과"만 보고 기준을 정한다.
    # 고르기는 2025년 1~6월 F1, 시험(2025년 7~12월)은 기록만.
    def thr_for(s, policy, a, b):
        out = pd.Series(dtype=float)
        for m0 in pd.date_range(a, b, freq="MS"):
            start, end = m0.strftime("%Y-%m-%d"), (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
            idx = s.index[(df.date[s.index] >= start) & (df.date[s.index] <= end)]
            before = s.index[df.date[s.index] < start]
            if policy == "고정(2024년 3~12월로 한 번)":
                w = s.index[(df.date[s.index] >= "2024-03-01") & (df.date[s.index] <= "2024-12-31")]
            elif policy == "최근 12개월(매달)":
                k = 12
                while True:
                    w = before[df.date[before] >= (m0 - pd.DateOffset(months=k)).strftime("%Y-%m-%d")]
                    if df.y[w].sum() >= 15 or k >= 30:
                        break
                    k += 3
            else:  # 누적(매달)
                w = before
            out = pd.concat([out, pd.Series(f1_thr(df.y[w], s[w]), index=idx)])
        return out

    pol_rows = []
    for vname in ("A 기존 항목", "C 새 항목 추가"):
        s = preds[vname]
        for policy in ("고정(2024년 3~12월로 한 번)", "최근 12개월(매달)", "누적(매달)"):
            tv, tt = thr_for(s, policy, "2025-01-01", "2025-06-30"), thr_for(s, policy, *TEST)
            rv = summarize(df.y[tv.index].values, s[tv.index].values, tv.values)
            rt = summarize(df.y[tt.index].values, s[tt.index].values, tt.values)
            pol_rows.append({"변형": vname, "방식": policy, "검증 F1": rv["f1"], "검증 경보": rv["alerts"],
                             "검증 맞음": rv["hits"], "시험 F1(기록)": rt["f1"], "시험 맞음": rt["hits"],
                             "시험 헛경보": rt["false_alarms"], "시험 놓침": rt["misses"]})
            print(pol_rows[-1], flush=True)
    pol = pd.DataFrame(pol_rows)
    out = ROOT / "outputs"
    feat_table.to_csv(out / "experiment_features.csv", index=False, encoding="utf-8-sig")
    pol.to_csv(out / "experiment_threshold.csv", index=False, encoding="utf-8-sig")
    print("\n", feat_table.to_string(index=False), "\n\n선택(검증 기준):", best, "\n\n", pol.to_string(index=False))


if __name__ == "__main__":
    main()
