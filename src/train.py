"""특징 표 → 모델 학습·비교·학습 곡선·설명.

운영 방식을 그대로 흉내 낸다: 매달 1일에 그 전날까지의 모든 자료로 다시 학습하고, 그달을 예측한다.
기간 (코드에 고정, 시험 결과를 본 뒤 바꾸지 않는다)
- 검증 2025-01 ~ 2025-06: 이 기간 예측으로 모델 설정과 경보 기준(임계값)을 정한다
- 시험 2025-07 ~ 2025-12: 정해진 설정·기준 그대로, 한 번만 평가한다
모델
- rule: 간단한 규칙 점수 (봄·가을 + 쉬는 날 + 맑음 + 최근 출력제어)
- logistic: 로지스틱 회귀 (빈칸은 중앙값 + 빈칸 표시 열, 표준화)
- hgb: 사이킷런 HistGradientBoosting (빈칸을 그대로 처리)
경보 기준(임계값): 매달 1일, 직전 12개월의 예측 결과에서 F1 이 가장 큰 값으로 다시 정한다
(그 12개월에 출력제어가 15일보다 적으면 3개월씩 더 과거까지 넓힌다). 그달의 답은 보지 않는다.
- 2026-11-10 실험(src/experiments.py): 검증 기간에서 "고정 기준", "누적 기준"과 F1 이 같았고(0.66),
  계절이 바뀌는 데 맞춰 가는 운영 원칙에 따라 이 방식을 골랐다.
- 같은 실험에서 새 항목(예보 변화, 더위·추위, 같은 종류 날 수요)과 방향 제약은 검증에서 효과가 없어 본 모델에 넣지 않았다.
"""
import json
import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score, precision_recall_curve, precision_score,
                             recall_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
# 변형 (docs/MODEL_RESULTS.md 11·15장)
#   full   : 본 모델 (2026-11-12 저녁부터). 사용자가 실제로 아는 두 정보를 쓴다고 가정한다.
#            ① 전날까지의 출력제어 여부 (어제·최근 7/30/90일·마지막 후 경과일): 사업자·운영자는 당일에 안다
#            ② 전력거래소 전날 전망 공지 (kpx_notice): 누구나 볼 수 있는 공개 글
#   public : 두 정보를 모두 쓰지 않음 = 아무것도 모를 때의 하한 (실적 글은 1일~11주 늦게 올라온다)
#   실행: python src/train.py → outputs/   ·   PLANTIES_VARIANT=public python src/train.py → outputs/public/
VARIANT = os.environ.get("PLANTIES_VARIANT", "full")
assert VARIANT in ("full", "public"), VARIANT
HISTORY = {"curt_lag1", "curt_cnt7", "curt_cnt30", "curt_cnt90", "days_since_curt"}
ASSUMED = HISTORY | {"kpx_notice"}
OUT = ROOT / "outputs" / "public" if VARIANT == "public" else ROOT / "outputs"
SEED = 0
P = {"val": ("2025-01-01", "2025-06-30"), "test": ("2025-07-01", "2025-12-31")}
META = {"date", "y", "label_source", "fc_n_areas", "fc_fallback"}
# 특징 표에는 있지만 본 모델에는 넣지 않는 항목 (검증에서 효과 없음, docs/MODEL_RESULTS.md 7장)
NOT_USED = {"fc_clear_share_d2", "fc_clear_delta", "fc_pop_delta", "fc_cool_deg", "fc_heat_deg", "dem_mid_lastsame",
            "sup_mid_lag1", "res_rate_mid_lag1"}  # 공급능력·예비율(EPSIS)은 2026년 시험용 실험 항목
if VARIANT == "public":
    NOT_USED = NOT_USED | ASSUMED
OOT_START = "2023-07-01"   # 경보 기준을 정하는 데 쓸 과거 예측을 이때부터 만들어 둔다
THR_MONTHS, THR_MIN_POS = 12, 15

NAMES = {  # 그래프·문서용 한글 이름
    "month": "월", "doy_sin": "계절(사인)", "doy_cos": "계절(코사인)", "dow": "요일", "is_holiday": "공휴일",
    "is_workers_day": "근로자의 날", "is_offday": "쉬는 날", "offday_run_len": "연휴 길이",
    "prev_offday": "전날 쉬는 날", "next_offday": "다음날 쉬는 날", "fc_sky_mean": "예보 하늘상태 평균",
    "fc_clear_share": "예보 맑음 비율", "fc_pop_mean": "예보 강수확률 평균", "fc_pop_max": "예보 강수확률 최대",
    "fc_sw_sky_mean": "남서부 하늘상태", "fc_sw_pop_mean": "남서부 강수확률", "fc_tmx_mean": "예보 최고기온",
    "dem_mid_lag7": "지난주 같은 요일 한낮 수요", "dem_mid_lag1": "어제 한낮 수요", "dem_min_lag7": "지난주 최저 수요",
    "sol_mid_lag1": "어제 한낮 태양광", "sol_mid_mean7": "최근 7일 한낮 태양광", "sol_share_lag1": "어제 태양광 비중",
    "nuc_lag1": "어제 원전 출력", "sol_cap_lag1": "태양광 설비용량", "curt_lag1": "어제 출력제어",
    "curt_cnt7": "최근 7일 출력제어", "curt_cnt30": "최근 30일 출력제어", "curt_cnt90": "최근 90일 출력제어",
    "days_since_curt": "마지막 출력제어 후 경과일", "kpx_notice": "전력거래소 전날 공지",
}


def load():
    df = pd.read_csv(ROOT / "data" / "features" / "daily_features.csv")
    feats = [c for c in df.columns if c not in META and c not in NOT_USED and not c.startswith("post_")]
    return df, feats


def part(df, name):
    a, b = P[name]
    return df[(df.date >= a) & (df.date <= b)]


def rule_score(X):
    spring_autumn = X["month"].isin([2, 3, 4, 5, 6, 9, 10, 11]).astype(float)
    if VARIANT == "public":  # 공개 자료만: 최근 출력제어 항목을 뺀 세 가지
        return (spring_autumn + X["is_offday"] + (X["fc_clear_share"].fillna(0) >= 0.5)) / 3
    return (spring_autumn + X["is_offday"] + (X["fc_clear_share"].fillna(0) >= 0.5)
            + (X["curt_cnt30"].fillna(0) >= 3)) / 4


def make(kind, **kw):
    if kind == "logistic":
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                             LogisticRegression(C=kw.get("C", 0.1), class_weight="balanced", max_iter=2000))
    if kind == "hgb":
        return HistGradientBoostingClassifier(learning_rate=kw.get("lr", 0.05), max_depth=kw.get("depth", 3),
                                              max_iter=kw.get("iters", 200), l2_regularization=1.0,
                                              min_samples_leaf=kw.get("leaf", 20), class_weight="balanced",
                                              random_state=SEED)
    raise ValueError(kind)


def scores(model, X):
    return model.predict_proba(X)[:, 1]


def best_threshold(y, s):
    p, r, t = precision_recall_curve(y, s)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    i = int(np.nanargmax(f1[:-1]))
    return float(t[i])


def rolling_threshold(df, s, a, b):
    """a~b 의 날마다 경보 기준. s 는 날짜 인덱스(df.index)를 가진 과거 예측 결과(매달 재학습)."""
    out = pd.Series(index=s.index[(df.date[s.index] >= a) & (df.date[s.index] <= b)], dtype=float)
    for m0 in pd.date_range(a, b, freq="MS"):
        start, end = m0.strftime("%Y-%m-%d"), (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        idx = out.index[(df.date[out.index] >= start) & (df.date[out.index] <= end)]
        before = s.index[df.date[s.index] < start]
        k = THR_MONTHS
        while True:
            w = before[df.date[before] >= (m0 - pd.DateOffset(months=k)).strftime("%Y-%m-%d")]
            if df.y[w].sum() >= THR_MIN_POS or k >= 30:
                break
            k += 3
        out[idx] = best_threshold(df.y[w], s[w])
    return out


def metrics(y, s, thr):
    thr = np.asarray(thr, dtype=float) * np.ones(len(s))
    pred = (s >= thr).astype(int)
    return {"pr_auc": round(average_precision_score(y, s), 3), "roc_auc": round(roc_auc_score(y, s), 3),
            "precision": round(precision_score(y, pred, zero_division=0), 3),
            "recall": round(recall_score(y, pred), 3), "f1": round(f1_score(y, pred), 3),
            "threshold_mean": round(float(np.mean(thr)), 3), "n_days": int(len(y)), "n_pos": int(y.sum()),
            "n_pred_pos": int(pred.sum()), "hits": int(((pred == 1) & (y == 1)).sum()),
            "false_alarms": int(((pred == 1) & (y == 0)).sum()), "misses": int(((pred == 0) & (y == 1)).sum())}


def main():
    OUT.mkdir(exist_ok=True)
    df, feats = load()
    va, te = part(df, "val"), part(df, "test")
    report = {"periods": P, "scheme": "매달 1일 재학습(그 전날까지 전체 자료)", "features": feats,
              "base_rate_test": round(te.y.mean(), 3)}

    def backtest(kind, params, a, b, months=None):
        """a~b 기간을 달마다: 그달 1일 이전 자료(months 가 있으면 최근 N개월만)로 학습 → 그달 예측."""
        out = []
        for m0 in pd.date_range(a, b, freq="MS"):
            m1 = (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
            first = (m0 - pd.DateOffset(months=months)).strftime("%Y-%m-%d") if months else "0000"
            m0 = m0.strftime("%Y-%m-%d")
            trn, tst = df[(df.date < m0) & (df.date >= first)], df[(df.date >= m0) & (df.date <= m1)]
            if kind == "rule":
                out.append(rule_score(tst).values)
            else:
                use = [c for c in feats if trn[c].notna().any()]  # 학습 기간에 전부 빈 열(예: 2024년 원전)은 뺀다
                out.append(scores(make(kind, **params).fit(trn[use], trn.y), tst[use]))
        return np.concatenate(out)

    # 1) 설정 고르기 (검증 기간 PR-AUC)
    grid = {"logistic": [{"C": c} for c in (0.01, 0.1, 1.0)],
            "hgb": [{"lr": lr, "depth": d, "iters": it} for lr in (0.03, 0.1) for d in (2, 3) for it in (100, 300)]}
    chosen, val_scores = {"rule": {}}, {"rule": backtest("rule", {}, *P["val"])}
    for kind, opts in grid.items():
        res = []
        for o in opts:
            sc = backtest(kind, o, *P["val"])
            res.append((average_precision_score(va.y, sc), o, sc))
        best = max(res, key=lambda x: x[0])
        chosen[kind], val_scores[kind] = best[1], best[2]
        report[f"val_search_{kind}"] = [{"params": o, "val_pr_auc": round(v, 3)} for v, o, _ in res]
    report["chosen_params"] = chosen

    # 2) 고른 설정으로 2023-07 ~ 2025-12 를 매달 재학습해 예측해 둔다 (경보 기준을 정할 과거 자료)
    oot = {k: pd.Series(backtest(k, chosen[k], OOT_START, P["test"][1]),
                        index=df.index[(df.date >= OOT_START) & (df.date <= P["test"][1])])
           for k in ("rule", "logistic", "hgb")}
    thr_v = {k: rolling_threshold(df, s, *P["val"]) for k, s in oot.items()}
    thr_t = {k: rolling_threshold(df, s, *P["test"]) for k, s in oot.items()}
    val_scores = {k: s[thr_v[k].index].values for k, s in oot.items()}
    test_scores = {k: s[thr_t[k].index].values for k, s in oot.items()}
    report["threshold_method"] = f"매달 직전 {THR_MONTHS}개월 예측에서 F1 최대 (출력제어 {THR_MIN_POS}일 미만이면 기간 확장)"
    report["val"] = {k: metrics(va.y.values, val_scores[k], thr_v[k].values) for k in oot}

    # 3) 시험: 같은 방식으로 2025 하반기를 한 번 평가
    report["test"] = {k: metrics(te.y.values, test_scores[k], thr_t[k].values) for k in oot}
    pred = te[["date", "y"]].copy()
    for k, s in test_scores.items():
        pred[f"p_{k}"] = np.round(s, 4)
        pred[f"thr_{k}"] = np.round(thr_t[k].values, 4)
        pred[f"alert_{k}"] = (s >= thr_t[k].values).astype(int)
    pred.to_csv(OUT / "test_predictions.csv", index=False, encoding="utf-8-sig")
    thr = {k: thr_t[k].values for k in thr_t}
    trf = df[df.date <= "2025-06-30"]
    final = {k: make(k, **chosen[k]).fit(trf[feats], trf.y) for k in ("logistic", "hgb")}  # 설명용

    # 시험 PR-AUC 의 불확실성: 시험 날짜를 복원 추출로 1000번 다시 뽑아 95% 범위
    rng = np.random.default_rng(SEED)
    yt = te.y.values
    for k, sc in test_scores.items():
        bs = []
        for _ in range(1000):
            i = rng.integers(0, len(yt), len(yt))
            if yt[i].sum() > 0:
                bs.append(average_precision_score(yt[i], sc[i]))
        report["test"][k]["pr_auc_ci95"] = [round(float(np.percentile(bs, 2.5)), 3),
                                            round(float(np.percentile(bs, 97.5)), 3)]

    # 4) 학습 곡선: 매달 재학습할 때 "최근 N개월만" 쓰면 시험 성능이 어떻게 되나
    lc = []
    for months in (6, 12, 18, 24, None):
        row = {"months": months or "전체"}
        first = (pd.Timestamp("2025-07-01") - pd.DateOffset(months=months)).strftime("%Y-%m-%d") if months else "0000"
        sub = df[(df.date >= first) & (df.date < "2025-07-01")]
        row["train_pos_at_july"] = int(sub.y.sum())
        for k in ("logistic", "hgb"):
            sc = backtest(k, chosen[k], *P["test"], months=months)
            row[f"{k}_test_pr_auc"] = round(average_precision_score(te.y, sc), 3)
        lc.append(row)
    lcdf = pd.DataFrame(lc)
    lcdf.to_csv(OUT / "learning_curve.csv", index=False, encoding="utf-8-sig")
    report["learning_curve"] = lc

    # 5) 설명: 로지스틱 계수(표준화) + HGB 순열 중요도(시험 기간)
    lr = final["logistic"][-1]
    n = len(feats)
    coef = pd.Series(lr.coef_[0][:n], index=feats)
    pi = permutation_importance(final["hgb"], te[feats], te.y, scoring="average_precision",
                                n_repeats=20, random_state=SEED)
    imp = pd.DataFrame({"feature": feats, "name_ko": [NAMES.get(f, f) for f in feats],
                        "logistic_coef": coef.values.round(3),
                        "hgb_perm_importance": pi.importances_mean.round(4)})
    imp = imp.sort_values("hgb_perm_importance", ascending=False)
    imp.to_csv(OUT / "feature_importance.csv", index=False, encoding="utf-8-sig")
    report["top_features_hgb"] = imp.head(10)[["name_ko", "hgb_perm_importance"]].values.tolist()

    (OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    charts(te, test_scores, thr, lcdf, imp)
    show(report)


def charts(te, s, thr, lcdf, imp):
    c = {"rule": "#888780", "logistic": "#eb6834", "hgb": "#2a78d6"}
    lab = {"rule": "규칙", "logistic": "로지스틱 회귀", "hgb": "그래디언트 부스팅"}
    fig, ax = plt.subplots(figsize=(6, 4.2), dpi=150)
    for k in ("rule", "logistic", "hgb"):
        p, r, _ = precision_recall_curve(te.y, s[k])
        ax.plot(r, p, color=c[k], lw=2, label=f"{lab[k]} (PR-AUC {average_precision_score(te.y, s[k]):.2f})")
    ax.axhline(te.y.mean(), color="#b4b2a9", ls="--", lw=1, label=f"무작위 ({te.y.mean():.2f})")
    ax.set_xlabel("재현율: 실제 출력제어 중 잡아낸 비율"); ax.set_ylabel("정밀도: 경보 중 맞은 비율")
    ax.set_title("시험 기간(2025년 7~12월) 성능", fontsize=11); ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False); fig.tight_layout(); fig.savefig(OUT / "pr_curve.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.8), dpi=150)
    for k in ("logistic", "hgb"):
        ax.plot(range(len(lcdf)), lcdf[f"{k}_test_pr_auc"], marker="o", color=c[k], lw=2, label=lab[k])
    ax.set_xticks(range(len(lcdf)))
    ax.set_xticklabels([f"최근 {m}개월\n({p}일)" if m != "전체" else f"전체\n({p}일)"
                        for m, p in zip(lcdf.months, lcdf.train_pos_at_july)])
    ax.set_ylabel("시험 기간 PR-AUC"); ax.set_title("학습 기간을 늘리면 성능이 오르나? (괄호: 7월 기준 학습 속 출력제어일)", fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "learning_curve.png"); plt.close(fig)

    top = imp.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
    ax.barh(top.name_ko, top.hgb_perm_importance, color="#2a78d6", height=0.6)
    ax.set_xlabel("빼면 PR-AUC가 얼마나 떨어지나"); ax.set_title("중요한 입력 (그래디언트 부스팅, 시험 기간)", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False); fig.tight_layout(); fig.savefig(OUT / "feature_importance.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.2), dpi=150)
    d = pd.to_datetime(te.date)
    ax.fill_between(d, 0, 1, where=te.y.values == 1, color="#f7c1c1", step="mid", label="실제 출력제어일")
    ax.plot(d, s["hgb"], color="#2a78d6", lw=1.5, label="예측 확률 (그래디언트 부스팅)")
    ax.step(d, thr["hgb"], where="mid", color="#444441", ls="--", lw=1, label="경보 기준 (매달 다시 정함)")
    ax.set_ylim(0, 1); ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.set_title("2025년 하반기: 전날 예측 확률과 실제 출력제어", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False); fig.tight_layout(); fig.savefig(OUT / "test_timeline.png"); plt.close(fig)


def show(r):
    print("선택된 설정:", r["chosen_params"])
    for part_name in ("val", "test"):
        print(f"\n[{part_name}]")
        cols = (["pr_auc"] + (["pr_auc_ci95"] if part_name == "test" else [])
                + ["roc_auc", "precision", "recall", "f1", "n_pos", "hits", "false_alarms", "misses"])
        print(pd.DataFrame(r[part_name]).T[cols].to_string())
    print("\n학습 곡선\n", pd.DataFrame(r["learning_curve"]).to_string(index=False))
    print("\n중요 입력 상위", r["top_features_hgb"][:8])


if __name__ == "__main__":
    main()
