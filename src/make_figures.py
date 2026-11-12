"""발표용 그림 5종 → outputs/figures/*.png (숫자는 모두 결과 파일에서 읽는다, 손으로 적지 않는다).

1 yearly_curtailment.png   연도별 육지 출력제어 발생일
2 pipeline.png             전체 구조도
3 risk_levels.png          위험도 4단계별 실제 출력제어 비율, 2025 하반기와 2026년
  calibration.png          예보한 확률 구간별 실제 출력제어 비율
4 notice_vs_model.png      2026년 출력제어 70일: 전력거래소 공지 / 모델만 / 둘 다 놓침
5 test_design.png          시험 설계 타임라인

실행: python src/make_figures.py   (공개 자료 모델 결과 outputs/public/ 을 쓴다)
"""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "outputs" / "public"
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False
INK, MUTED, LINE, BG = "#152033", "#5d6879", "#dde3ec", "#ffffff"
ACCENT, ACCENT_SOFT, GRAY = "#1d5fc4", "#a9c4ee", "#c3cad6"
LV = {"매우 높음": "#e8887a", "높음": "#f6c9b6", "주의": "#f7dc94", "낮음": "#bfe3cf"}       # 시연 화면과 같은 뜻의 색
LV_INK = {"높음": "#d23b2a", "주의": "#b77700", "낮음": "#1d8152"}


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("outputs/figures/" + name)


def clean(ax):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(length=0, colors=MUTED)


# ---------- 1. 연도별 발생일 ----------
def yearly():
    f = pd.read_csv(ROOT / "data" / "features" / "daily_features.csv", usecols=["date", "y"])
    n = f.groupby(f.date.str[:4]).y.sum()
    labels = ["2023년", "2024년", "2025년", "2026년\n(1~10월)"]
    vals = [int(n["2023"]), int(n["2024"]), int(n["2025"]), int(n["2026"])]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, vals, width=0.55, color=[ACCENT, ACCENT, ACCENT, ACCENT_SOFT])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v}일", ha="center", va="bottom", fontsize=17,
                fontweight="bold", color=INK)
    ax.set_ylim(0, max(vals) * 1.2)
    ax.set_yticks([])
    clean(ax)
    ax.tick_params(axis="x", labelsize=12.5, colors=INK)
    ax.set_title(f"육지 출력제어 발생일: 3년 만에 {vals[2] // vals[0] // 10 * 10}배 이상", fontsize=16, fontweight="bold", color=INK,
                 loc="left", pad=16)
    fig.text(0.125, -0.06, "출처: 한국전력거래소 출력제어 실적(공공데이터포털). 2026년 6월 14일 이후는 전력거래소 게시판 실적, 10월은 잠정.",
             fontsize=8.5, color=MUTED)
    save(fig, "yearly_curtailment.png")


# ---------- 2. 구조도 ----------
def pipeline():
    fig, ax = plt.subplots(figsize=(12.5, 4.3))
    ax.set_xlim(0, 125)
    ax.set_ylim(0, 43)
    ax.axis("off")
    stages = [
        ("공개 데이터 8종", ["기상청 예보·관측", "전력수요 (시간별·5분)", "태양광·연료원 실적", "출력제어 실적·공지", "공휴일"], False),
        ("정제·검증", ["원본 306개 지문 관리", "자동 검증 675개", "결함 발견·기록", "(쉼표 값 461칸 등)"], False),
        ("전날 17시 입력", ["그 시각에 공개된", "정보만 사용", "누수 점검 9가지", "입력 26개"], False),
        ("AI 모델", ["그래디언트 부스팅", "(10가지 비교로 선택)", "매달 다시 학습", "시간 순서 검증"], True),
        ("위험도 · 원인", ["높음 / 주의 / 낮음", "원인 3가지", "대비 방법"], False),
        ("화면", ["시연 화면", "(지난 날짜 재현)", "실시간 내일 예보"], False),
    ]
    w, gap, x = 18.2, 3.0, 0.5
    for i, (title, lines, dark) in enumerate(stages):
        fc, tc, sc = (INK, "#ffffff", "#c9d3e3") if dark else ("#f4f6f9", INK, MUTED)
        ax.add_patch(FancyBboxPatch((x, 5), w, 33, boxstyle="round,pad=0,rounding_size=1.6", fc=fc, ec=LINE, lw=1))
        ax.text(x + w / 2, 33, title, ha="center", va="center", fontsize=12.5, fontweight="bold", color=tc)
        for j, s in enumerate(lines):
            ax.text(x + w / 2, 27 - j * 4.3, s, ha="center", va="center", fontsize=9.3, color=sc)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap - 0.3, 21.5), xytext=(x + w + 0.3, 21.5),
                        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.4))
        x += w + gap
    ax.text(0.5, 1, "외부 API는 입력 자료(기상청 단기예보, 전력거래소 실시간 수급)를 받는 데만 쓴다. 예측은 직접 학습한 모델이 한다.",
            fontsize=8.8, color=MUTED)
    save(fig, "pipeline.png")


# ---------- 3. 위험도별 실제 발생 비율 ----------
def levels():
    import json
    s25 = json.loads((PUB / "explain_summary.json").read_text(encoding="utf-8"))["risk_levels4"]["test"]
    s26 = json.loads((PUB / "explain_2026_summary.json").read_text(encoding="utf-8"))["risk_levels4"]["합계 (1/1~10/31)"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, s, title in [(axes[0], s25, "2025년 하반기 시험"), (axes[1], s26, "2026년 독립 시험 (1~10월)")]:
        tot_d = sum(v["days"] for v in s.values())
        tot_c = sum(v["curtailed"] for v in s.values())
        base = tot_c / tot_d
        names = ["매우 높음", "높음", "주의", "낮음"]
        rates = [s[k]["curtailed"] / max(s[k]["days"], 1) for k in names]
        bars = ax.bar([f"위험 {k}" for k in names], rates, width=0.55, color=[LV[k] for k in names])
        for b_, k, r in zip(bars, names, rates):
            ax.text(b_.get_x() + b_.get_width() / 2, r + 0.012, f"{r:.0%}", ha="center", va="bottom", fontsize=18,
                    fontweight="bold", color=INK)
            ax.text(b_.get_x() + b_.get_width() / 2, r + 0.075, f"{s[k]['days']}일 중 {s[k]['curtailed']}일", ha="center",
                    va="bottom", fontsize=9.5, color=MUTED)
        ax.set_ylim(0, 0.72)
        ax.set_yticks([])
        clean(ax)
        ax.tick_params(axis="x", labelsize=12, colors=INK)
        ax.set_title(f"{title}  ·  전체 평균 {base:.0%} ({tot_d}일 중 {tot_c}일)", fontsize=11.5, color=INK, loc="left", pad=10)
    fig.suptitle("위험도가 한 단계 오를 때마다 실제 출력제어 비율도 올랐다", fontsize=15, fontweight="bold", color=INK, x=0.065,
                 ha="left", y=1.03)
    fig.text(0.065, -0.04, "막대 = 그 위험도로 예보한 날 중 실제로 출력제어가 있던 날의 비율. 공개 자료 모델, 전날 17시 기준, 미리 보지 않은 기간. "
             "2026년 10월 정답은 잠정. 단계 선은 매달 그 전 12개월 예보 결과로만 정한다.", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.065, right=0.97, wspace=0.08)
    save(fig, "risk_levels.png")


# ---------- 3-2. 예보 확률 대 실제 ----------
def calibration():
    import json
    c25 = json.loads((PUB / "explain_summary.json").read_text(encoding="utf-8"))["calibration"]["test"]
    c26 = json.loads((PUB / "explain_2026_summary.json").read_text(encoding="utf-8"))["calibration"]["합계 (1/1~10/31)"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, c, title in [(axes[0], c25, "2025년 하반기 시험"), (axes[1], c26, "2026년 독립 시험 (1~10월)")]:
        labs = [("5% 이하" if r["to"] <= 0.05 else f"{r['from']:.0%}~{r['to']:.0%}" if r["to"] < 1 else f"{r['from']:.0%} 이상") for r in c]
        xs = range(len(c))
        bars = ax.bar(xs, [r["actual_rate"] for r in c], width=0.55, color=ACCENT)
        ax.plot(xs, [r["forecast_mean"] for r in c], "o", ms=9, mfc=BG, mec=INK, mew=1.8, zorder=3)
        for x, r in zip(xs, c):
            top = max(r["actual_rate"], r["forecast_mean"])
            ax.text(x, top + 0.05, f"실제 {r['actual_rate']:.0%}", ha="center", va="bottom", fontsize=14, fontweight="bold", color=INK)
            ax.text(x, top + 0.135, f"예보 평균 {r['forecast_mean']:.0%}", ha="center", va="bottom", fontsize=9, color=MUTED)
            ax.text(x, -0.105, f"{r['days']}일 중 {r['curtailed']}일", ha="center", va="top", fontsize=8.5, color=MUTED)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labs)
        ax.set_ylim(0, 0.85)
        ax.set_yticks([])
        clean(ax)
        ax.tick_params(axis="x", labelsize=11, colors=INK)
        ax.set_title(title, fontsize=11.5, color=INK, loc="left", pad=10)
    fig.suptitle("모델이 예보한 확률과 실제로 일어난 비율", fontsize=15, fontweight="bold", color=INK, x=0.065, ha="left", y=1.08)
    fig.text(0.065, 0.965, "막대 = 실제 출력제어 비율      ○ = 그 구간에서 모델이 예보한 확률의 평균", fontsize=10, color=INK)
    fig.text(0.065, -0.1, "○가 막대 위에 있으면 모델이 실제보다 높게 예보한 것이다. 확률은 매달 그 전 12개월 예보 결과로만 보정한다. "
             "확률이 60% 이상으로 나온 날은 7~11일뿐이라 40% 이상으로 묶었다. 2026년 10월 정답은 잠정.", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.065, right=0.97, wspace=0.08, top=0.84)
    save(fig, "calibration.png")


# ---------- 4. 공지와 비교 ----------
def notice(d26):
    y = d26[d26.y == 1]
    al = y.level.isin(["높음", "매우 높음"])
    a = int((y.kpx_notice == 1).sum())
    b = int(((y.kpx_notice == 0) & al).sum())
    c = int(((y.kpx_notice == 0) & ~al).sum())
    tot = a + b + c
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.set_xlim(0, tot)
    ax.set_ylim(-1.5, 1.75)
    ax.axis("off")
    x = 0
    for v, col, tc, big, small in [(a, GRAY, INK, f"{a}일", "전력거래소가 전날 공지한 날"),
                                   (b, ACCENT, "#ffffff", f"{b}일", "공지는 없었지만 모델이 전날 알린 날"),
                                   (c, "#eef1f5", MUTED, f"{c}일", "둘 다 놓침")]:
        ax.add_patch(Rectangle((x + 0.15, 0), v - 0.3, 1, fc=col, ec="none"))
        ax.text(x + v / 2, 0.5, big, ha="center", va="center", fontsize=19 if v > 6 else 12, fontweight="bold", color=tc)
        ax.text(x + v / 2, -0.32, small, ha="center", va="top", fontsize=10.5 if v > 6 else 9, color=INK if v > 6 else MUTED)
        x += v
    ax.text(0, 1.42, f"2026년 출력제어 {tot}일, 누가 전날 알렸나", fontsize=15, fontweight="bold", color=INK)
    hit_n = int(((y.kpx_notice == 1) & al).sum())
    fa = int((d26.level.isin(["높음", "매우 높음"]) & (d26.y == 0)).sum())
    ax.text(0, -1.3, f"2026-01-01 ~ 10-31, 공개 자료 모델이 '높음' 이상으로 예보한 날 기준. 공지가 있던 {a}일 중 {hit_n}일은 모델도 알렸다. "
            f"공지는 낸 날의 97%가 맞았고, 모델은 헛경보가 더 많다({fa}번).", fontsize=8.5, color=MUTED)
    save(fig, "notice_vs_model.png")


# ---------- 5. 시험 설계 ----------
def design():
    fig, ax = plt.subplots(figsize=(12, 3.6))
    t = lambda s: pd.Timestamp(s).toordinal()
    ax.set_xlim(t("2022-12-01"), t("2026-12-31"))
    ax.set_ylim(-2.4, 3.2)
    ax.axis("off")
    segs = [("2023-01-01", "2024-12-31", "학습", "#eef1f5", INK, "2023 ~ 2024"),
            ("2025-01-01", "2025-06-30", "검증", ACCENT_SOFT, INK, "2025 상반기\n모델·설정 선택"),
            ("2025-07-01", "2025-12-31", "시험", ACCENT, "#ffffff", "2025 하반기\n출력제어 27일"),
            ("2026-01-01", "2026-10-31", "독립 시험", INK, "#ffffff", "2026년 1~10월\n출력제어 70일")]
    for a, b, name, fc, tc, sub in segs:
        ax.add_patch(Rectangle((t(a) + 4, 0), t(b) - t(a) - 8, 1, fc=fc, ec="none"))
        ax.text((t(a) + t(b)) / 2, 0.5, name, ha="center", va="center", fontsize=13, fontweight="bold", color=tc)
        ax.text((t(a) + t(b)) / 2, -0.3, sub, ha="center", va="top", fontsize=9.5, color=MUTED, linespacing=1.5)
    x = t("2026-11-11")
    ax.plot([x, x], [-0.1, 1.75], color=LV_INK["높음"], lw=1.6)
    ax.text(x, 1.9, "결과를 보기 전에\n시험 계획 공개", ha="center", va="bottom", fontsize=9.5, color=LV_INK["높음"],
            fontweight="bold", linespacing=1.4)
    ax.text(t("2023-01-01"), 2.75, "미래를 미리 보지 않는 시험 설계", fontsize=15, fontweight="bold", color=INK)
    ax.text(t("2023-01-01"), 1.45, "매달 1일, 그 전날까지의 자료로만 다시 학습해 그달을 예측한다", fontsize=10.5, color=INK)
    ax.text(t("2023-01-01"), -2.2, "입력은 전날 17시에 공개된 정보만 쓴다(누수 점검 9가지). 2026년 시험은 태양광·원전 실적이 미공개라 그 입력을 빼고 했다.",
            fontsize=8.5, color=MUTED)
    save(fig, "test_design.png")


if __name__ == "__main__":
    d25 = pd.read_csv(PUB / "demo_days.csv")
    d26 = pd.read_csv(PUB / "demo_days_2026.csv")
    yearly()
    pipeline()
    levels()
    calibration()
    notice(d26)
    design()
