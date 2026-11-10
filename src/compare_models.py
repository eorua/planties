"""여러 머신러닝 모델을 같은 조건으로 비교한다 (train.py 와 같은 평가 방식).

- 매달 1일에 그 전날까지의 자료로 다시 학습 → 그달 예측
- 모델 고르기는 검증 기간(2025-01 ~ 06) PR-AUC 로만 한다
- 시험 기간(2025-07 ~ 12) 결과는 기록만 한다 (시험 결과로 모델을 바꾸지 않는다)
"""
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import train as T

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED = 0


def imp_scale(model):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), model)


def imp(model):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), model)


# (이름, 한글 이름, 계열, [설정별 모델 만드는 함수])
CANDIDATES = [
    ("logistic", "로지스틱 회귀", "선형", [lambda c=c: imp_scale(LogisticRegression(C=c, class_weight="balanced", max_iter=3000))
                                          for c in (0.01, 0.1, 1.0)]),
    ("naive_bayes", "나이브 베이즈", "확률", [lambda: imp_scale(GaussianNB())]),
    ("knn", "k-최근접 이웃", "거리", [lambda k=k: imp_scale(KNeighborsClassifier(n_neighbors=k, weights="distance"))
                                     for k in (15, 31)]),
    ("svm", "서포트 벡터 머신", "커널", [lambda c=c: imp_scale(SVC(C=c, kernel="rbf", probability=True, class_weight="balanced",
                                                            random_state=SEED)) for c in (0.3, 1.0)]),
    ("mlp", "신경망(MLP)", "신경망", [lambda h=h: imp_scale(MLPClassifier(hidden_layer_sizes=h, alpha=1e-2, max_iter=2000,
                                                                     early_stopping=True, random_state=SEED))
                                     for h in ((16,), (32, 16))]),
    ("random_forest", "랜덤 포레스트", "트리 앙상블", [lambda l=l: imp(RandomForestClassifier(
        n_estimators=500, min_samples_leaf=l, class_weight="balanced_subsample", random_state=SEED, n_jobs=-1))
        for l in (3, 10)]),
    ("extra_trees", "엑스트라 트리", "트리 앙상블", [lambda l=l: imp(ExtraTreesClassifier(
        n_estimators=500, min_samples_leaf=l, class_weight="balanced_subsample", random_state=SEED, n_jobs=-1))
        for l in (3, 10)]),
    ("hgb", "그래디언트 부스팅", "트리 부스팅", [lambda lr=lr, d=d, it=it: HistGradientBoostingClassifier(
        learning_rate=lr, max_depth=d, max_iter=it, l2_regularization=1.0, min_samples_leaf=20,
        class_weight="balanced", random_state=SEED) for lr in (0.03, 0.1) for d in (2, 3) for it in (100, 300)]),
]


def backtest(df, feats, factory, a, b):
    out = []
    for m0 in pd.date_range(a, b, freq="MS"):
        m1 = (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        m0 = m0.strftime("%Y-%m-%d")
        trn, tst = df[df.date < m0], df[(df.date >= m0) & (df.date <= m1)]
        use = [c for c in feats if trn[c].notna().any()]
        m = factory().fit(trn[use], trn.y)
        out.append(m.predict_proba(tst[use])[:, 1])
    return np.concatenate(out)


def prec_at_recall(y, s, target=0.8):
    p, r, _ = precision_recall_curve(y, s)
    return float(p[:-1][r[:-1] >= target].max())


def ci(y, s, n=1000):
    rng = np.random.default_rng(SEED)
    bs = [average_precision_score(y[i], s[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(n)) if y[i].sum()]
    return [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]


def rank(s):
    return pd.Series(s).rank(pct=True).values


def main():
    df, feats = T.load()
    va, te = T.part(df, "val"), T.part(df, "test")
    rows, test_scores, val_scores = [], {}, {}
    for key, name, family, factories in CANDIDATES:
        t0 = time.time()
        best = None
        for i, f in enumerate(factories):
            sv = backtest(df, feats, f, *T.P["val"])
            v = average_precision_score(va.y, sv)
            if best is None or v > best[0]:
                best = (v, i, sv)
        sv = best[2]
        st = backtest(df, feats, factories[best[1]], *T.P["test"])
        val_scores[key], test_scores[key] = sv, st
        rows.append({"key": key, "모델": name, "계열": family, "설정 수": len(factories),
                     "검증 PR-AUC": round(best[0], 3), "시험 PR-AUC": round(average_precision_score(te.y, st), 3),
                     "시험 95% 범위": ci(te.y.values, st), "시험 ROC-AUC": round(roc_auc_score(te.y, st), 3),
                     "재현율80% 정밀도": round(prec_at_recall(te.y.values, st), 3),
                     "소요(초)": round(time.time() - t0, 1)})
        print(rows[-1], flush=True)

    # 앙상블: 순위를 평균 (검증에서 상위 3개를 고른다)
    top3 = [r["key"] for r in sorted(rows, key=lambda r: -r["검증 PR-AUC"])[:3]]
    for label, keys in (("앙상블(로지스틱+부스팅)", ["logistic", "hgb"]), (f"앙상블(검증 상위3: {'+'.join(top3)})", top3)):
        sv = np.mean([rank(val_scores[k]) for k in keys], axis=0)
        st = np.mean([rank(test_scores[k]) for k in keys], axis=0)
        rows.append({"key": label, "모델": label, "계열": "앙상블", "설정 수": 0,
                     "검증 PR-AUC": round(average_precision_score(va.y, sv), 3),
                     "시험 PR-AUC": round(average_precision_score(te.y, st), 3), "시험 95% 범위": ci(te.y.values, st),
                     "시험 ROC-AUC": round(roc_auc_score(te.y, st), 3),
                     "재현율80% 정밀도": round(prec_at_recall(te.y.values, st), 3), "소요(초)": 0})
    rule_v, rule_t = T.rule_score(va).values, T.rule_score(te).values
    rows.append({"key": "rule", "모델": "규칙(학습 없음)", "계열": "기준선", "설정 수": 0,
                 "검증 PR-AUC": round(average_precision_score(va.y, rule_v), 3),
                 "시험 PR-AUC": round(average_precision_score(te.y, rule_t), 3), "시험 95% 범위": ci(te.y.values, rule_t),
                 "시험 ROC-AUC": round(roc_auc_score(te.y, rule_t), 3),
                 "재현율80% 정밀도": round(prec_at_recall(te.y.values, rule_t), 3), "소요(초)": 0})
    out = pd.DataFrame(rows).sort_values("검증 PR-AUC", ascending=False)
    # 소요 시간은 실행할 때마다 달라서 파일에는 남기지 않는다 (다시 만들어도 같은 파일)
    out.drop(columns="소요(초)").to_csv(ROOT / "outputs" / "model_comparison.csv", index=False, encoding="utf-8-sig")
    print(out.drop(columns="key").to_string(index=False))


if __name__ == "__main__":
    main()
