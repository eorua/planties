"""2026년 독립 시험 (계획: docs/TEST_2026_PLAN.md, 결과를 보기 전에 올림).

태양광·원전 입력 없이(2026년 미공개) 매달 재학습 방식으로 2026-01 ~ 2026-10 을 예측한다.
"""
import json
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import experiments as E
import train as T

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = T.OUT   # 변형(PLANTIES_VARIANT)에 따라 outputs/ 또는 outputs/public/
PERIODS = {"시험1 (1/1~6/13, 공식)": ("2026-01-01", "2026-06-13"),
           "시험2 (6/14~10/31, 게시판)": ("2026-06-14", "2026-10-31"),
           "합계 (1/1~10/31)": ("2026-01-01", "2026-10-31")}
SUPPLY = ["sup_mid_lag1", "res_rate_mid_lag1"]
PRIMARY = "N+C"


def ci(y, s, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum():
            bs.append(average_precision_score(y[i], s[i]))
    return [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]


def evaluate(y, s, thr):
    pred = (s >= thr).astype(int)
    hits, fa, miss = int((pred & y).sum()), int((pred & (1 - y)).sum()), int(((1 - pred) & y).sum())
    return {"n_days": int(len(y)), "n_pos": int(y.sum()), "pr_auc": round(average_precision_score(y, s), 3),
            "pr_auc_ci95": ci(y, s), "roc_auc": round(roc_auc_score(y, s), 3), "hits": hits, "false_alarms": fa,
            "misses": miss, "precision": round(hits / max(hits + fa, 1), 3), "recall": round(hits / max(y.sum(), 1), 3)}


def main():
    df, base = T.load()
    n = [c for c in base if not c.startswith("sol_") and c != "nuc_lag1"]
    variants = {"N+C": n + E.NEW, "N+S+C": n + SUPPLY + E.NEW, "N": n, "N+S": n + SUPPLY}
    assert df[df.date.between("2026-01-01", "2026-10-31")][n + E.NEW + SUPPLY].notna().mean().min() > 0.9, \
        "2026년 입력에 빈칸이 많다 (예보 정리본을 먼저 만들 것)"

    scores, thrs = {}, {}
    for name, cols in variants.items():
        s = E.backtest(df, cols, False, "2023-07-01", "2026-10-31")
        scores[name] = s
        thrs[name] = T.rolling_threshold(df, s, "2026-01-01", "2026-10-31")
        print(name, "완료", flush=True)
    rule = pd.Series(T.rule_score(df).values, index=df.index)
    scores["규칙"] = rule
    thrs["규칙"] = T.rolling_threshold(df, rule[df.date >= "2023-07-01"], "2026-01-01", "2026-10-31")

    board = pd.read_csv(ROOT / "data" / "clean" / "kpx_board_daily.csv").set_index("date")
    report = {"plan": "docs/TEST_2026_PLAN.md", "primary": PRIMARY, "results": {}}
    rows = []
    for pname, (a, b) in PERIODS.items():
        idx = df.index[(df.date >= a) & (df.date <= b)]
        y = df.y[idx].values
        for name in list(variants) + ["규칙"]:
            r = evaluate(y, scores[name][idx].values, thrs[name][idx].values)
            report["results"].setdefault(pname, {})[name] = r
            rows.append({"기간": pname, "모델": name, **r})
        # 전력거래소 전날 전망 공지: 예/아니오
        notice = df.date[idx].map(board["notice_forecast"]).fillna(0).astype(int).values
        hits, fa = int((notice & y).sum()), int((notice & (1 - y)).sum())
        r = {"n_days": int(len(y)), "n_pos": int(y.sum()), "hits": hits, "false_alarms": fa,
             "misses": int(y.sum() - hits), "precision": round(hits / max(hits + fa, 1), 3),
             "recall": round(hits / max(y.sum(), 1), 3)}
        report["results"][pname]["전력거래소 전날 공지"] = r
        rows.append({"기간": pname, "모델": "전력거래소 전날 공지", **r})

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "test_2026_results.csv", index=False, encoding="utf-8-sig")
    (OUT / "test_2026.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    idx = df.index[(df.date >= "2026-01-01") & (df.date <= "2026-10-31")]
    pred = df.loc[idx, ["date", "y", "label_source"]].copy()
    for name in scores:
        pred[f"p_{name}"] = scores[name][idx].round(4).values
        pred[f"alert_{name}"] = (scores[name][idx].values >= thrs[name][idx].values).astype(int)
    pred["kpx_notice"] = pred.date.map(board["notice_forecast"]).fillna(0).astype(int)
    pred.to_csv(OUT / "test_2026_predictions.csv", index=False, encoding="utf-8-sig")
    chart(df, idx, scores[PRIMARY], thrs[PRIMARY], pred)
    pd.set_option("display.width", 200)
    print(table[["기간", "모델", "n_pos", "pr_auc", "pr_auc_ci95", "hits", "false_alarms", "misses", "precision", "recall"]]
          .to_string(index=False))


def chart(df, idx, s, thr, pred):
    fig, ax = plt.subplots(figsize=(10, 3.4), dpi=150)
    d = pd.to_datetime(df.date[idx])
    ax.fill_between(d, 0, 1, where=df.y[idx].values == 1, color="#f7c1c1", step="mid", label="실제 출력제어일")
    ax.plot(d, s[idx].values, color="#2a78d6", lw=1.3, label=f"예측 확률 ({PRIMARY})")
    ax.step(d, thr[idx].values, where="mid", color="#444441", ls="--", lw=1, label="경보 기준")
    k = pred.kpx_notice.values == 1
    ax.scatter(d[k], np.full(k.sum(), 0.97), marker="v", s=14, color="#eb6834", label="전력거래소 전날 전망 공지", zorder=3)
    ax.axvline(pd.Timestamp("2026-06-14"), color="#b4b2a9", lw=1)
    ax.set_ylim(0, 1.02); ax.legend(fontsize=8, frameon=False, ncol=4, loc="upper left", bbox_to_anchor=(0, 1.15))
    ax.set_title("2026년 독립 시험: 전날 예측과 실제 출력제어 (세로선 왼쪽 공식 정답, 오른쪽 게시판)", fontsize=10, pad=22)
    ax.spines[["top", "right"]].set_visible(False); fig.tight_layout(); fig.savefig(OUT / "test_2026_timeline.png"); plt.close(fig)


if __name__ == "__main__":
    main()
