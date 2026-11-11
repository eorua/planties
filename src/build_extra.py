"""추가 정리본: EPSIS 실시간 전력수급(시간별), 전력거래소 출력제어 게시판(날짜별).

EPSIS (data/raw/epsis/*.csv, 5분 단위)
- 시간 맞추기: HH:05 ~ (HH+1):00 의 5분 값 평균 = 전력거래소 시간 번호 HH+1 (시간 끝 기준).
  2023~2025 기존 시간별 수요와 비교해 확인: 오차 중앙값 0.11%, 95% 0.36%.
- 한 시간에 5분 값이 6개(절반) 미만이면 그 시간은 빈칸.
- 값은 바꾸지 않는다 (평균만 낸다). 몇 개로 평균 냈는지 n_points 로 남긴다.

게시판 (data/raw/kpx_board/kpx_board_scraped_20261105.csv)
- 육지만. 날짜마다: 전날 전망 공지가 있었나, 실제 출력제어가 있었나, 시작·종료 시각, 사유(전력망·수급).
- 2024-10-12 ~ 2026-06-13 기간 출력제어 발생일은 공식 실적 파일과 모두 일치(149일)했다 (2026-11-05 점검).
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"


def epsis():
    files = sorted((RAW / "epsis").glob("epsis_realtime_load_*.csv"))
    e = pd.concat([pd.read_csv(f).assign(source_file=f.name) for f in files], ignore_index=True)
    e["t"] = pd.to_datetime(e["datetime_kst"])
    assert not e["t"].duplicated().any(), "같은 시각이 두 번 있음"
    shifted = e["t"] - pd.Timedelta(minutes=1)          # 00:00 은 전날 24시에 속한다
    e["date"] = shifted.dt.strftime("%Y-%m-%d")
    e["hour"] = shifted.dt.hour + 1
    h = e.groupby(["date", "hour"]).agg(supply_mw=("supply_capacity_mw", "mean"), load_mw=("load_mw", "mean"),
                                        reserve_mw=("reserve_mw", "mean"), n_points=("load_mw", "size")).reset_index()
    low = h["n_points"] < 6
    h.loc[low, ["supply_mw", "load_mw", "reserve_mw"]] = pd.NA
    h[["supply_mw", "load_mw", "reserve_mw"]] = h[["supply_mw", "load_mw", "reserve_mw"]].astype(float).round(1)
    h = h[(h.date >= "2022-12-01")]
    h.to_csv(CLEAN / "epsis_hourly.csv", index=False, encoding="utf-8-sig")
    print(f"epsis_hourly: {len(h)}시간, 5분 값 부족으로 빈 시간 {int(low.sum())}개, {h.date.min()} ~ {h.date.max()}")


def board():
    b = pd.read_csv(RAW / "kpx_board" / "kpx_board_scraped_20261105.csv")
    b = b[b.region == "육지"]
    occ = b[b.type == "실적"].set_index("date")
    fc = set(b[b.type.isin(["전망", "전망후미발생"])].date)
    days = sorted(set(occ.index) | fc)
    out = pd.DataFrame({"date": days})
    out["notice_forecast"] = out.date.isin(fc).astype(int)
    out["occurred"] = out.date.isin(occ.index).astype(int)
    for c in ("start_h", "end_h", "grid", "supply"):
        out[c] = out.date.map(occ[c]) if c in occ else pd.NA
    out = out.rename(columns={"grid": "reason_grid", "supply": "reason_supply"})
    out.to_csv(CLEAN / "kpx_board_daily.csv", index=False, encoding="utf-8-sig")
    print(f"kpx_board_daily: {len(out)}일, 발생 {out.occurred.sum()}일, 전망 공지 {out.notice_forecast.sum()}일, "
          f"{out.date.min()} ~ {out.date.max()}")

    # 공식 실적과 겹치는 기간 일치 확인
    c = pd.read_csv(CLEAN / "curtailment_daily.csv")
    off = set(c[(c.grid == "육지") & ((c.n_hours_controlled.fillna(0) > 0) | c.has_blank_hour)].date)
    a, z = "2024-10-12", "2026-06-13"
    o1 = {d for d in off if a <= d <= z}
    o2 = {d for d in out[out.occurred == 1].date if a <= d <= z}
    print(f"겹치는 기간 공식 {len(o1)}일 / 게시판 {len(o2)}일, 공식에만 {sorted(o1 - o2)}, 게시판에만 {sorted(o2 - o1)}")


if __name__ == "__main__":
    epsis()
    board()
