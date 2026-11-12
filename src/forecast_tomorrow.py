"""실시간 예보: 지금 공개된 자료로 "내일 육지 출력제어가 있을까?"를 예측한다.

쓰는 모델: 2026년 독립 시험의 주 모델 N+C (공개 자료 변형). 태양광·원전 실적과 출력제어 이력은
전날 17시에 공개되지 않으므로 쓰지 않는다. 입력은 세 가지뿐이다.
- 기상청 단기예보 (공공데이터포털 "기상청_단기예보 조회서비스", 인증키 필요, 자동 승인·무료)
  5개 지역(광주·목포·전주·대구·부산) 격자의 하늘상태·강수확률·최고기온
- 전력거래소 EPSIS 실시간 전력수급 (5분 단위 수요, 인증키 없음)
- 공휴일 (data/manual/holidays_kr.csv)

실행 (인터넷 되는 노트북에서):
    1) 인증키를 환경변수 KMA_SERVICE_KEY 에 넣거나, 저장소 맨 위에 secrets_kma_key.txt 파일로 둔다
       (.gitignore 에 secrets* 가 있어 저장소에 올라가지 않는다). 공공데이터포털의 "일반 인증키(Decoding)" 값.
    2) python src/forecast_tomorrow.py            # 내일 예보 → outputs/public/live_days.csv 에 한 줄 추가
       python src/build_demo.py                   # 시연 화면에 "내일 예보" 단추가 생긴다
    3) (선택) python src/forecast_tomorrow.py --offline 2026-10-10   # 인터넷 없이 과거 자료로 같은 계산 재현

시각 규칙 (학습 때와 같음, src/build_features.py)
- 내일(D) 예보는 오늘(D-1) 17시 발표분을 쓴다. 17시 15분 전이면 14시 발표분으로 대신한다(학습 때의 대체 규칙과 같음).
  14시 15분 전에는 예측하지 않는다.
- SKY·POP: D 11~14시, TMX: D 최고기온. 예보 변화 항목은 D-2 17시 발표분과 비교 (못 받으면 빈칸).
- 수요: EPSIS 5분 값 → 시간 평균 (HH:05~HH+1:00 = HH+1시). 한낮 = 11~14시.

받은 원본은 data/live/ 에 날짜별로 그대로 저장한다(나중에 확인용).
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("PLANTIES_VARIANT", "public")   # 실시간 예보는 공개 자료 모델만 가능
import build_features as BF  # noqa: E402
import explain as X
import explain_2026 as X26
import train as T
import experiments as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "public"
LIVE = ROOT / "data" / "live"
KST = timezone(timedelta(hours=9))
GRIDS = {"광주": (59, 75), "목포": (50, 67), "전주": (63, 90), "대구": (89, 91), "부산": (97, 74)}
KMA_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
EPSIS_PAGE = "https://epsis.kpx.or.kr/epsisnew/selectEkgeEpsMepRealChart.do?menuId=030300"
EPSIS_URL = "https://epsis.kpx.or.kr/epsisnew/selectEkgeEpsMepRealGridAjax.ajax"
HOURS = ["1100", "1200", "1300", "1400"]   # D 11~14시 KST


# ---------- 자료 받기 (인터넷) ----------

def kma_key():
    k = os.environ.get("KMA_SERVICE_KEY", "").strip()
    f = ROOT / "secrets_kma_key.txt"
    if not k and f.exists():
        k = f.read_text(encoding="utf-8").strip()
    if not k:
        sys.exit("기상청 인증키가 없습니다. 환경변수 KMA_SERVICE_KEY 또는 secrets_kma_key.txt 에 넣어 주세요.")
    return k


def fetch_kma(base_date, base_time):
    """5개 격자의 단기예보 → [{area, category, fcstDate, fcstTime, fcstValue}] (못 받으면 None)."""
    import requests
    key, items = kma_key(), []
    for area, (nx, ny) in GRIDS.items():
        params = {"serviceKey": key, "pageNo": 1, "numOfRows": 1500, "dataType": "JSON",
                  "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny}
        for attempt in range(3):
            try:
                r = requests.get(KMA_URL, params=params, timeout=20)
                body = r.json()["response"]
                if body["header"]["resultCode"] != "00":
                    print(f"  기상청 {area} {base_date} {base_time}: {body['header']['resultMsg']}")
                    return None
                got = body["body"]["items"]["item"]
                break
            except Exception as e:  # 네트워크·형식 오류는 두 번 더 시도
                if attempt == 2:
                    print(f"  기상청 {area} {base_date} {base_time} 받기 실패: {e}")
                    return None
                time.sleep(2)
        items += [{"area": area, **{k: it[k] for k in ("category", "fcstDate", "fcstTime", "fcstValue")}}
                  for it in got if it["category"] in ("SKY", "POP", "TMX")]
    LIVE.mkdir(parents=True, exist_ok=True)
    (LIVE / f"kma_{base_date}_{base_time}.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


def fetch_epsis(days):
    """EPSIS 실시간 전력수급 5분 값 (하루씩 요청) → DataFrame(datetime_kst, load_mw)."""
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    s.get(EPSIS_PAGE, timeout=20)
    rows = []
    for d in days:
        ymd = d.replace("-", "")
        for attempt in range(3):
            r = s.post(EPSIS_URL, data={"beginDate": ymd, "endDate": ymd, "editYn": "N"},
                       headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30)
            got = parse_epsis(r.text)
            if got:
                break
            time.sleep(2)
        rows += got
    e = pd.DataFrame(rows, columns=["datetime_kst", "supply_capacity_mw", "load_mw"]).drop_duplicates("datetime_kst")
    LIVE.mkdir(parents=True, exist_ok=True)
    e.sort_values("datetime_kst").to_csv(LIVE / f"epsis_{days[0]}_{days[-1]}.csv", index=False, encoding="utf-8-sig")
    return e


def parse_epsis(text):
    """EPSIS 응답(자바스크립트 조각)에서 시각·공급능력·수요를 꺼낸다. c1 = 공급능력, c2 = 현재 수요."""
    out = []
    pat = re.compile(r'c1 = textFormmat\("([\d.]*)".*?c2 = textFormmat\("([\d.]*)".*?"year":"([\d\- :]+)"', re.S)
    for c1, c2, t in pat.findall(text):
        out.append((t, float(c1) if c1 else np.nan, float(c2) if c2 else np.nan))
    return out


# ---------- 특징 만들기 (학습 때와 같은 계산) ----------

def fc_summary(items, target):
    """build_features.forecast 의 summarize 와 같은 계산. items 가 없으면 빈칸."""
    keys = ["fc_sky_mean", "fc_clear_share", "fc_pop_mean", "fc_pop_max", "fc_sw_sky_mean", "fc_sw_pop_mean",
            "fc_tmx_mean"]
    if not items:
        return {k: np.nan for k in keys}
    f = pd.DataFrame(items)
    f["value"] = pd.to_numeric(f.fcstValue, errors="coerce")
    f.loc[f.value <= -99, "value"] = np.nan
    t = target.replace("-", "")
    sp = f[(f.fcstDate == t) & f.fcstTime.isin(HOURS)]
    sky, pop = sp[sp.category == "SKY"], sp[sp.category == "POP"]
    tx = f[(f.fcstDate == t) & (f.category == "TMX")]
    sw = list(BF.SW)
    return {"fc_sky_mean": sky.value.mean(), "fc_clear_share": (sky.value == 1).astype(float).where(sky.value.notna()).mean(),
            "fc_pop_mean": pop.value.mean(), "fc_pop_max": pop.value.max(),
            "fc_sw_sky_mean": sky[sky.area.isin(sw)].value.mean(), "fc_sw_pop_mean": pop[pop.area.isin(sw)].value.mean(),
            "fc_tmx_mean": tx.groupby("area").value.first().mean() if len(tx) else np.nan}


def hourly_load(e):
    """build_extra.epsis 와 같은 시간 맞추기: HH:05 ~ (HH+1):00 평균 = HH+1시, 5분 값 6개 미만이면 빈칸."""
    e = e.copy()
    e["t"] = pd.to_datetime(e.datetime_kst)
    sh = e.t - pd.Timedelta(minutes=1)
    e["date"], e["hour"] = sh.dt.strftime("%Y-%m-%d"), sh.dt.hour + 1
    h = e.groupby(["date", "hour"]).agg(load_mw=("load_mw", "mean"), n=("load_mw", "count")).reset_index()
    h.loc[h.n < 6, "load_mw"] = np.nan
    h["load_mw"] = h["load_mw"].round(1)   # build_extra 와 같이 0.1MW 단위로
    return h


def build_row(target, items_main, items_d2, load_5min, fallback):
    days = pd.date_range(pd.Timestamp(target) - pd.Timedelta(days=30), pd.Timestamp(target) + pd.Timedelta(days=10))
    cal = BF.calendar(days.strftime("%Y-%m-%d")).set_index("date").loc[target].to_dict()
    fc = fc_summary(items_main, target)
    d2 = fc_summary(items_d2, target)
    fc["fc_clear_share_d2"] = d2["fc_clear_share"]
    fc["fc_clear_delta"] = fc["fc_clear_share"] - d2["fc_clear_share"]
    fc["fc_pop_delta"] = fc["fc_pop_mean"] - d2["fc_pop_mean"]
    fc["fc_cool_deg"] = max(fc["fc_tmx_mean"] - 28, 0) if pd.notna(fc["fc_tmx_mean"]) else np.nan
    fc["fc_heat_deg"] = max(10 - fc["fc_tmx_mean"], 0) if pd.notna(fc["fc_tmx_mean"]) else np.nan

    h = hourly_load(load_5min)
    dm = h[h.hour.isin(BF.MID)].groupby("date").load_mw.mean()
    dmin = h.groupby("date").load_mw.min()
    T0 = pd.Timestamp(target)
    day = lambda k: (T0 - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
    pw = {"dem_mid_lag7": dm.get(day(7), np.nan) / 1000, "dem_mid_lag1": dm.get(day(1), np.nan) / 1000,
          "dem_min_lag7": dmin.get(day(7), np.nan) / 1000}
    off = BF.offday_series(days.strftime("%Y-%m-%d"))
    k = 1
    while k <= 30 and off.loc[day(k)] != off.loc[target]:
        k += 1
    pw["dem_mid_lastsame"] = dm.get(day(k), np.nan) / 1000 if k <= 30 else np.nan
    row = {"date": target, **cal, **fc, **pw, "fc_fallback": int(fallback)}
    return row


# ---------- 예측 ----------

def predict(row, issued):
    live = json.loads((OUT / "live_thresholds.json").read_text(encoding="utf-8"))
    feats = live["features"]
    df, _ = T.load()
    trn = df[df.date < row["date"]]
    use = [c for c in feats if trn[c].notna().any()]
    model = E.hgb(use, False).fit(trn[use], trn.y)
    x = pd.DataFrame([row])[use].astype(float)
    p = float(model.predict_proba(x)[:, 1][0])
    med = trn[use].median()
    attr = {}
    for g, cols in X26.GROUPS.items():
        cols = [c for c in cols if c in use]
        if not cols:
            continue
        x2 = x.copy()
        for c in cols:
            x2[c] = med[c]
        attr[g] = p - float(model.predict_proba(x2)[:, 1][0])
    a = pd.Series(attr).sort_values(ascending=False)
    hol = pd.read_csv(ROOT / "data" / "manual" / "holidays_kr.csv").set_index("date")["name"].to_dict()
    r = pd.Series(row)
    up = [g for g, v in a.items() if v > 0.005][:3]
    down = [g for g, v in a.sort_values().items() if v < -0.005][:2]
    hi, wa = live["thr_high"], live["thr_watch"]
    return {"date": row["date"], "dow": X.DOW[pd.Timestamp(row["date"]).dayofweek], "holiday": hol.get(row["date"], ""),
            "y": "", "p": round(p, 4), "thr_high": hi, "thr_watch": wa,
            "level": "높음" if p >= hi else "주의" if p >= wa else "낮음",
            "up": " | ".join(f"{X.reason_text(g, r, hol)}:{a[g]:+.3f}" for g in up),
            "down": " | ".join(f"{X.reason_text(g, r, hol)}:{a[g]:+.3f}" for g in down),
            "trend": "", "kpx_notice": "", "board_reason": "", "board_hours": "",
            "label": "아직 모름", "period": "live", "issued": issued,
            "train_until": trn.date.max(), "fc_fallback": row["fc_fallback"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", metavar="YYYY-MM-DD", help="인터넷 없이 저장소의 과거 자료로 그 날짜 예보를 재현")
    args = ap.parse_args()

    if args.offline:
        target = args.offline
        items_main, items_d2, load = offline_sources(target)
        row = build_row(target, items_main, items_d2, load, False)
        issued = f"{(pd.Timestamp(target) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')} 17:00 (과거 자료 재현)"
    else:
        now = datetime.now(KST)
        if now.hour * 60 + now.minute < 14 * 60 + 15:
            sys.exit("14시 15분 이후에 실행해 주세요 (내일 예보에 쓰는 기상청 14시·17시 발표분이 아직 없습니다).")
        today = now.strftime("%Y%m%d")
        target = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        fallback = now.hour * 60 + now.minute < 17 * 60 + 15
        base_time = "1400" if fallback else "1700"
        print(f"내일({target}) 예보: 기상청 {today} {base_time} 발표분")
        items_main = fetch_kma(today, base_time)
        if items_main is None:
            sys.exit("기상청 예보를 받지 못했습니다. 인증키와 인터넷 연결을 확인해 주세요.")
        d2 = (now - timedelta(days=1)).strftime("%Y%m%d")
        cache = LIVE / f"kma_{d2}_1700.json"
        items_d2 = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else fetch_kma(d2, "1700")
        if items_d2 is None:
            print("  어제 17시 발표분을 받지 못해 '예보 변화' 항목은 빈칸으로 둡니다.")
        days = [(now - timedelta(days=k)).strftime("%Y-%m-%d") for k in range(14, -1, -1)]
        print(f"전력수요: EPSIS {days[0]} ~ {days[-1]}")
        load = fetch_epsis(days)
        row = build_row(target, items_main, items_d2, load, fallback)
        issued = now.strftime("%Y-%m-%d %H:%M") + f" (기상청 {base_time[:2]}시 발표분)"

    res = predict(row, issued)
    path = OUT / "live_days.csv"
    old = pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame()
    if args.offline:
        print(json.dumps({**res, "features": {k: (None if pd.isna(v) else v) for k, v in row.items()}},
                         ensure_ascii=False, indent=1, default=str))
        return res, row
    new = pd.concat([old[old.get("date", pd.Series(dtype=str)) != res["date"]] if len(old) else old,
                     pd.DataFrame([res])]).sort_values("date")
    new.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n{res['date']} ({res['dow']}) 위험 {res['level']}  점수 {res['p']:.3f} "
          f"(주의 {res['thr_watch']} · 높음 {res['thr_high']} 이상)")
    print("  올린 원인:", res["up"] or "뚜렷한 원인 없음")
    print("  낮춘 원인:", res["down"] or "없음")
    print(f"→ {path.relative_to(ROOT)} 저장. 시연 화면에 넣으려면: python src/build_demo.py")
    return res, row


def offline_sources(target):
    """저장소의 과거 자료(정리본·EPSIS 원본)를 API 응답과 같은 모양으로 바꾼다. 실시간 계산이 학습 때와 같은지 확인용."""
    f = pd.read_csv(ROOT / "data" / "clean" / f"kma_forecast_{target[:4]}.csv.gz")
    T0 = pd.Timestamp(target)

    def items(issue_day):
        g = f[(f.issue_date_utc == issue_day.strftime("%Y-%m-%d")) & (f.issue_hhmm_utc == 800)]
        out = []
        for r in g.itertuples():
            base = pd.Timestamp(r.issue_date_utc) + pd.Timedelta(hours=17)   # 08:00 UTC = 17:00 KST
            if r.element == "TMX":
                fd, ft = (pd.Timestamp(r.issue_date_utc) + pd.Timedelta(days=r.lead_h - 5)), pd.Timestamp("1900-01-01 15:00")
            else:
                fd = ft = base + pd.Timedelta(hours=r.lead_h)
            v = "" if pd.isna(r.value) else str(r.value)
            out.append({"area": r.station_area, "category": r.element, "fcstDate": fd.strftime("%Y%m%d"),
                        "fcstTime": ft.strftime("%H%M"), "fcstValue": v})
        return out or None
    e = pd.concat([pd.read_csv(p) for p in sorted((ROOT / "data" / "raw" / "epsis").glob("*.csv"))])
    lo, hi = (T0 - pd.Timedelta(days=31)).strftime("%Y-%m-%d"), T0.strftime("%Y-%m-%d")
    e = e[(e.datetime_kst >= lo) & (e.datetime_kst <= hi + " 00:00")][["datetime_kst", "supply_capacity_mw", "load_mw"]]
    return items(T0 - pd.Timedelta(days=1)), items(T0 - pd.Timedelta(days=2)), e


if __name__ == "__main__":
    main()
