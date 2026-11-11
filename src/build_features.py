"""정리본(data/clean, data/manual) → 학습용 특징 표 (data/features/daily_features.csv).

예측 상황: 전날(D-1) 17시(한국 시간)에 "내일(D) 육지 출력제어가 있을까?"를 묻는다.
그래서 모든 특징은 D-1 17시까지 알 수 있는 값만 쓴다. 열마다 언제 알 수 있는지(available_at)를
data/features/FEATURES.md 에 적는다. 정답(y)과 설명용 사후값(post_*)은 입력에 쓰지 않는다.

시간 맞추기 (2026-11-10 관측과 대조해 확인)
- 단기예보 발표 시각은 UTC. D-1 17시 KST 발표 = D-1 08:00 UTC.
- SKY·POP 의 lead_h 는 "발표 후 몇 시간 뒤". D 11~14시 KST = 발표 + 18~21시간.
  (관측 운량과 상관이 시차 0에서 가장 큼)
- TMX 의 lead_h 는 날짜 코드. 6 = 발표일(KST) 다음 날, 7 = 그다음 날 …
  (lead 6 과 다음 날 관측 최고기온: 상관 0.99, 평균 오차 1.1°C)
- 08:00 UTC 발표분이 빠진 날은 05:00 UTC(14시 KST) 발표분으로 대신하고 fcst_fallback=1 로 표시.

빈칸은 채우지 않는다 (NA). 모델이 직접 처리하거나, 학습 코드에서 처리 방법을 정한다.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "data" / "features"
START, END = "2023-01-01", "2026-10-31"
OFFICIAL_LABEL_END = "2026-06-13"   # 공식 실적 파일의 마지막 날. 그 뒤는 게시판 실적으로 정답을 만든다.
MID = [11, 12, 13, 14]                      # 한낮 시간대 (전력 자료 시간 번호, 관측 시각 모두 같은 숫자로 맞춤)
SW = ["광주", "목포", "전주"]                # 태양광이 많은 남서부


def labels():
    c = pd.read_csv(CLEAN / "curtailment_daily.csv")
    m = c[(c.grid == "육지") & ((c.n_hours_controlled.fillna(0) > 0) | c.has_blank_hour)]
    b = pd.read_csv(CLEAN / "kpx_board_daily.csv")
    board = set(b[(b.occurred == 1) & (b.date > OFFICIAL_LABEL_END)].date)
    return set(m.date) | board


def offday_series(dates):
    h = pd.read_csv(ROOT / "data" / "manual" / "holidays_kr.csv")
    hol = set(h[h.official_holiday == "Y"].date)
    d = pd.to_datetime(pd.Index(dates))
    return pd.Series(((d.dayofweek >= 5) | pd.Index(dates).isin(hol)), index=pd.Index(dates))


def calendar(days):
    h = pd.read_csv(ROOT / "data" / "manual" / "holidays_kr.csv")
    hol = set(h[h.official_holiday == "Y"].date)
    workers = set(h[h.kind == "근로자의날"].date)
    df = pd.DataFrame({"date": days})
    d = pd.to_datetime(df.date)
    df["month"] = d.dt.month
    df["doy_sin"] = np.sin(2 * np.pi * d.dt.dayofyear / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * d.dt.dayofyear / 365.25)
    df["dow"] = d.dt.dayofweek
    df["is_holiday"] = df.date.isin(hol).astype(int)
    df["is_workers_day"] = df.date.isin(workers).astype(int)
    off = (d.dt.dayofweek >= 5) | df.is_holiday.astype(bool)
    df["is_offday"] = off.astype(int)
    # 쉬는 날이 몇 일 이어지는 묶음 안에 있는지 (연휴 길이)
    run = (off != off.shift()).cumsum()
    df["offday_run_len"] = np.where(off, off.groupby(run).transform("size"), 0)
    df["prev_offday"] = off.shift(1, fill_value=False).astype(int)
    df["next_offday"] = off.shift(-1, fill_value=False).astype(int)
    return df


def forecast(days):
    parts = [pd.read_csv(p) for p in sorted(CLEAN.glob("kma_forecast_20*.csv.gz"))]
    f = pd.concat(parts)
    f["issue_date"] = pd.to_datetime(f.issue_date_utc)
    index = pd.Index(days, name="date")

    def pick(issue_hhmm, days_ahead, leads_sky, tmx_lead):
        """발표일 + days_ahead = 목표일(D). 그 발표분에서 D 11~14시 SKY·POP 과 D 의 TMX 를 고른다."""
        g = f[f.issue_hhmm_utc == issue_hhmm].copy()
        g["target"] = (g.issue_date + pd.Timedelta(days=days_ahead)).dt.strftime("%Y-%m-%d")
        sp = g[g.element.isin(["SKY", "POP"]) & g.lead_h.isin(leads_sky)]
        tx = g[(g.element == "TMX") & (g.lead_h == tmx_lead)]
        return sp, tx

    def summarize(sp, tx):
        sky = sp[sp.element == "SKY"]
        pop = sp[sp.element == "POP"]
        res = pd.DataFrame(index=sorted(set(sp.target) | set(tx.target)))
        res["fc_sky_mean"] = sky.groupby("target").value.mean()
        res["fc_clear_share"] = sky.assign(c=(sky.value == 1).astype(float).where(sky.value.notna())).groupby("target").c.mean()
        res["fc_pop_mean"] = pop.groupby("target").value.mean()
        res["fc_pop_max"] = pop.groupby("target").value.max()
        sws = sky[sky.station_area.isin(SW)]
        res["fc_sw_sky_mean"] = sws.groupby("target").value.mean()
        res["fc_sw_pop_mean"] = pop[pop.station_area.isin(SW)].groupby("target").value.mean()
        res["fc_tmx_mean"] = tx.groupby("target").value.mean()
        res["fc_n_areas"] = sky.groupby("target").station_area.nunique()  # 5곳 중 몇 곳 예보가 있었나
        return res.reindex(index)

    # 기본: D-1 17시 KST(08:00 UTC) 발표, 없으면 D-1 14시 KST(05:00 UTC) 발표
    a = summarize(*pick(800, 1, [18, 19, 20, 21], 6))
    b = summarize(*pick(500, 1, [21, 22, 23, 24], 6))
    use_b = a["fc_sky_mean"].isna() & b["fc_sky_mean"].notna()
    res = a.copy()
    res.loc[use_b] = b.loc[use_b]
    res["fc_fallback"] = use_b.astype(int)

    # 예보 변화: 하루 전(D-2 17시) 발표분과 비교. 예보가 많이 바뀐 날은 그만큼 불확실하다.
    c = summarize(*pick(800, 2, [42, 43, 44, 45], 7))
    res["fc_clear_share_d2"] = c["fc_clear_share"]
    res["fc_clear_delta"] = res["fc_clear_share"] - c["fc_clear_share"]
    res["fc_pop_delta"] = res["fc_pop_mean"] - c["fc_pop_mean"]

    # 더위·추위: 냉난방 수요가 늘어나는 정도 (낮 최고기온 기준)
    res["fc_cool_deg"] = (res["fc_tmx_mean"] - 28).clip(lower=0)
    res["fc_heat_deg"] = (10 - res["fc_tmx_mean"]).clip(lower=0)
    return res.reset_index()


def power(days):
    d = pd.read_csv(CLEAN / "demand_hourly.csv")
    dm = d[d.hour.isin(MID)].groupby("date").demand.mean()
    dmin = d.groupby("date").demand.min()

    r = pd.read_csv(CLEAN / "renewable_hourly.csv")
    r = r[(r.region_level == "시도") & (r.fuel == "태양광") & r.hour.isin(MID)]
    sol = r.groupby(["date", "hour"]).value_mwh.sum().groupby("date").mean()

    fu = pd.read_csv(CLEAN / "fuel_hourly.csv")
    # 원전: 예측 시각(전날 17시)에 끝난 시간만 쓴다 → 어제 1~16시(시간 끝 기준 16시까지) 평균 (2026-11-11 수정, 이전은 하루 전체 평균)
    nuc = fu[(fu.fuel_raw == "원자력") & (fu.hour <= 16)].groupby("date").generation_mwh.mean()
    cap = fu[fu.fuel_raw == "태양광"].groupby("date").capacity_mw.max()

    idx = pd.date_range(pd.Timestamp(START) - pd.Timedelta(days=14), END).strftime("%Y-%m-%d")
    # EPSIS 실시간 수급: 공공데이터 수요 파일이 없는 2026년은 EPSIS 부하로 수요를 채운다 (오차 중앙값 0.11%).
    ep = pd.read_csv(CLEAN / "epsis_hourly.csv")
    ep_dm = ep[ep.hour.isin(MID)].groupby("date").load_mw.mean()
    ep_dmin = ep.groupby("date").load_mw.min()
    ep_sup = ep[ep.hour.isin(MID)].groupby("date").supply_mw.mean()
    ep_res = (ep[ep.hour.isin(MID)].assign(r=lambda x: x.reserve_mw / x.load_mw).groupby("date").r.mean())
    s = pd.DataFrame(index=idx)
    s["dm"], s["dmin"], s["sol"], s["nuc"], s["cap"] = dm, dmin, sol, nuc, cap
    s["dm"] = s["dm"].combine_first(ep_dm.reindex(s.index))
    s["dmin"] = s["dmin"].combine_first(ep_dmin.reindex(s.index))
    s["sup"], s["res"] = ep_sup, ep_res
    out = pd.DataFrame(index=pd.Index(days, name="date"))
    lag = lambda col, k: s[col].shift(k).reindex(out.index)
    out["dem_mid_lag7"] = lag("dm", 7) / 1000          # 지난주 같은 요일 한낮 수요 (GW)
    out["dem_mid_lag1"] = lag("dm", 1) / 1000          # 어제 한낮 수요
    out["dem_min_lag7"] = lag("dmin", 7) / 1000
    # 같은 종류 날(쉬는 날↔쉬는 날, 평일↔평일) 중 가장 최근 날의 한낮 수요.
    # 평일에 낀 공휴일은 지난주 같은 요일(평일)과 수요가 크게 달라서, 지난주 값만으로는 과대평가된다.
    off = offday_series(s.index)
    last_same = []
    for d in out.index:
        i = s.index.get_loc(d)
        j = i - 1
        while j >= 0 and off.iloc[j] != off.loc[d]:
            j -= 1
        last_same.append(s["dm"].iloc[j] if j >= 0 else np.nan)
    out["dem_mid_lastsame"] = np.array(last_same) / 1000
    out["sol_mid_lag1"] = lag("sol", 1) / 1000         # 어제 한낮 시장 태양광 (GW)
    out["sol_mid_mean7"] = s["sol"].shift(1).rolling(7, min_periods=5).mean().reindex(out.index) / 1000
    out["sol_share_lag1"] = out.sol_mid_lag1 / out.dem_mid_lag1
    out["nuc_lag1"] = lag("nuc", 1) / 1000             # 어제 1~16시 원전 평균 출력 (GW), 2024년 없음
    out["sol_cap_lag1"] = lag("cap", 1) / 1000         # 어제 시장 태양광 설비용량 (GW)
    out["sup_mid_lag1"] = lag("sup", 1) / 1000         # 어제 한낮 공급능력 (GW, EPSIS) — 켜져 있는 발전기 규모
    out["res_rate_mid_lag1"] = lag("res", 1)           # 어제 한낮 공급예비율 (예비력 ÷ 부하)
    # 설명용 사후값: 입력에 쓰지 않는다
    out["post_dem_mid"] = s["dm"].reindex(out.index) / 1000
    out["post_sol_mid"] = s["sol"].reindex(out.index) / 1000
    return out.reset_index()


def history(days, pos):
    idx = pd.date_range("2021-01-01", END)
    y = pd.Series(idx.strftime("%Y-%m-%d").isin(pos).astype(int), index=idx.strftime("%Y-%m-%d"))
    out = pd.DataFrame(index=pd.Index(days, name="date"))
    prev = y.shift(1)
    out["curt_lag1"] = prev.reindex(out.index)
    out["curt_cnt7"] = prev.rolling(7).sum().reindex(out.index)
    out["curt_cnt30"] = prev.rolling(30).sum().reindex(out.index)
    out["curt_cnt90"] = prev.rolling(90).sum().reindex(out.index)
    last = pd.Series(np.where(y.values == 1, np.arange(len(y)), np.nan), index=y.index).ffill().shift(1)
    out["days_since_curt"] = (pd.Series(np.arange(len(y)), index=y.index) - last).clip(upper=365).reindex(out.index)
    return out.reset_index()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(START, END).strftime("%Y-%m-%d")
    pos = labels()
    df = calendar(days)
    for part in (forecast(days), power(days), history(days, pos)):
        df = df.merge(part, on="date", how="left")
    df.insert(1, "y", df.date.isin(pos).astype(int))
    df.insert(2, "label_source", np.where(df.date <= OFFICIAL_LABEL_END, "공식", "게시판"))
    df.to_csv(OUT / "daily_features.csv", index=False, encoding="utf-8-sig")
    print(df.shape, "출력제어일", df.y.sum())
    print(df.isna().sum()[df.isna().sum() > 0].to_string())


if __name__ == "__main__":
    main()
