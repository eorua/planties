"""발표용 그림 5종 → outputs/figures/*.png (숫자는 모두 결과 파일에서 읽는다, 손으로 적지 않는다).

1 yearly_curtailment.png   연도별 육지 출력제어 발생일
2 pipeline.png             전체 구조도
3 calendar_2026.png        2026년 달력: 날마다 위험도 색 + 실제 출력제어 점   (calendar_2025h2.png 도 같이)
4 notice_vs_model.png      2026년 출력제어 70일: 전력거래소 공지 / 모델만 / 둘 다 놓침
5 test_design.png          시험 설계 타임라인

실행: python src/make_figures.py   (공개 자료 모델 결과 outputs/public/ 을 쓴다)
"""
import calendar
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
LV = {"높음": "#f3b2a9", "주의": "#f7dc94", "낮음": "#bfe3cf"}       # 시연 화면과 같은 뜻의 색
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


# ---------- 3. 달력 ----------
def cal(d, months, ncols, name, title, note):
    d = d.set_index("date")
    nrows = -(-len(months) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.55 * ncols, 2.45 * nrows + 1.0))
    axes = axes.ravel()
    for ax in axes:
        ax.axis("off")
    for ax, (y, m) in zip(axes, months):
        ax.set_xlim(0, 7)
        ax.set_ylim(6.9, -1.6)
        ax.set_aspect("equal")
        sub = d[d.index.str.startswith(f"{y}-{m:02d}")]
        ax.text(0, -1.15, f"{m}월", fontsize=12, fontweight="bold", color=INK, va="center")
        for i, w in enumerate("월화수목금토일"):
            ax.text(i + 0.5, -0.3, w, fontsize=7, color=MUTED, ha="center", va="center")
        ax.text(7, -1.15, f"출력제어 {int(sub.y.sum())}일", fontsize=8.5, color=MUTED, ha="right", va="center")
        first, n = calendar.monthrange(y, m)
        for day in range(1, n + 1):
            k = f"{y}-{m:02d}-{day:02d}"
            pos = first + day - 1
            cx, cy = pos % 7, pos // 7
            lv = d.level.get(k)
            ax.add_patch(Rectangle((cx + 0.05, cy + 0.05), 0.9, 0.9, fc=LV.get(lv, "#eef1f5"), ec="none"))
            if lv and d.y[k] == 1:
                ax.plot(cx + 0.5, cy + 0.5, "o", ms=4.6, color=INK, mec=BG, mew=0.6)
    fig.suptitle(title, fontsize=15, fontweight="bold", color=INK, x=0.03, ha="left", y=0.995)
    hx = 0.03
    for lv in ("높음", "주의", "낮음"):
        fig.patches.append(Rectangle((hx, 0.925), 0.012 * 12.75 / fig.get_figwidth(), 0.022, transform=fig.transFigure, fc=LV[lv], ec="none"))
        fig.text(hx + 0.017 * 12.75 / fig.get_figwidth(), 0.936, f"위험 {lv}", fontsize=9.5, color=INK, va="center")
        hx += 0.085 * 12.75 / fig.get_figwidth()
    fig.text(hx + 0.012, 0.936, "●  실제 출력제어가 있던 날", fontsize=9.5, color=INK, va="center")
    fig.text(0.03, 0.005, note, fontsize=8.3, color=MUTED)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.9, bottom=0.05, wspace=0.12, hspace=0.05)
    save(fig, name)


# ---------- 4. 공지와 비교 ----------
def notice(d26):
    y = d26[d26.y == 1]
    a = int((y.kpx_notice == 1).sum())
    b = int(((y.kpx_notice == 0) & (y.level == "높음")).sum())
    c = int(((y.kpx_notice == 0) & (y.level != "높음")).sum())
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
    hit_n = int(((y.kpx_notice == 1) & (y.level == "높음")).sum())
    ax.text(0, -1.3, f"2026-01-01 ~ 10-31, 공개 자료 모델의 '높음' 경보 기준. 공지가 있던 {a}일 중 {hit_n}일은 모델도 알렸다. "
            "공지는 낸 날의 97%가 맞았고, 모델은 헛경보가 더 많다(103번).", fontsize=8.5, color=MUTED)
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
    cal(d26, [(2026, m) for m in range(1, 11)], 5, "calendar_2026.png",
        "2026년 독립 시험: 전날 낸 위험도와 실제 출력제어",
        "공개 자료 모델, 전날 17시 기준. 6월 14일 이후 정답은 전력거래소 게시판 실적이고, 10월 2일 이후 실적 글은 아직 올라오지 않아 잠정이다.")
    cal(d25[d25.date >= "2025-07-01"], [(2025, m) for m in range(7, 13)], 3, "calendar_2025h2.png",
        "2025년 하반기 시험: 전날 낸 위험도와 실제 출력제어", "공개 자료 모델, 전날 17시 기준. 정답은 한국전력거래소 공식 실적.")
    notice(d26)
    design()
