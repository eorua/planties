"""원본(data/raw) → 무손실 정리본(data/clean) 생성 스크립트.

원칙
1. 값은 바꾸지 않는다. 형식(가로→세로, 열 이름, 문자 인코딩)만 통일한다.
2. 원본 표기는 *_raw 열로 함께 남긴다. 표준화한 값은 별도 열(*_std)로 추가한다.
3. 빈칸은 0으로 채우지 않고 결측(NA)으로 둔다. 채우는 규칙은 features 단계에서만 정한다.
4. 오타·이상값은 고치지 않고 플래그 열로 표시한다. 보정이 필요한 경우 보정값을 별도 열로 둔다.
5. 모든 행에 source_file 을 남겨 원본까지 추적할 수 있게 한다.

실행: python src/build_clean.py   (저장소 최상위 폴더에서)
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

START, END = "2023-01-01", "2025-12-31"  # 학습·시험 기간 (출력제어 정답은 전체 보존)

REGION_STD = {  # 원본 표기 → 표준 시도명. 원본은 region_raw 로 그대로 남긴다.
    "강원도": "강원", "경기도": "경기", "경상남도": "경남", "경상북도": "경북",
    "광주시": "광주", "대구시": "대구", "대전시": "대전", "부산시": "부산",
    "서울시": "서울", "세종시": "세종", "울산시": "울산", "인천시": "인천",
    "전라남도": "전남", "전라북도": "전북", "제주도": "제주", "충청남도": "충남",
    "충청북도": "충북", "육지": "육지(합계)", "제주": "제주(합계)",
}
AGGREGATE_REGIONS = {"육지", "제주"}  # 시도가 아닌 권역 합계 행. 시도 행과 더하면 이중 집계됨.

CTRL_REGION_FIX = {"감원": "강원"}  # 출력제어 제어지역 표기 보정(보정값은 별도 열)


def read_csv_any(src) -> pd.DataFrame:
    """CP949/UTF-8 어느 쪽이든 읽고, 모든 값을 문자열로 보존한다."""
    data = src.read_bytes() if isinstance(src, Path) else src
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    return df


def to_num(s: pd.Series) -> pd.Series:
    """공백·빈 문자열은 NA. 숫자로 바꿀 수 없는 값도 NA(원본은 *_raw 로 보존)."""
    return pd.to_numeric(s.str.strip().replace("", pd.NA), errors="coerce")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


report: dict = {"files": {}, "checks": [], "sources": {}}


def source_id(name: str) -> str:
    """긴 원본 파일 이름 대신 짧은 ID 를 쓴다. 대응표는 data/clean/sources.csv."""
    if name not in report["sources"]:
        report["sources"][name] = f"S{len(report['sources']) + 1:02d}"
    return report["sources"][name]


def drop_raw_if_lossless(df: pd.DataFrame, pairs: dict, label: str) -> pd.DataFrame:
    """숫자 열이 원본 문자열을 손실 없이 담고 있을 때만 원본 문자열 열을 지운다.
    손실 기준: 원본이 공백이 아닌데 숫자로 바뀌지 않은 칸이 하나라도 있으면 지우지 않는다."""
    for raw_col, num_col in pairs.items():
        raw = df[raw_col].astype(str).str.strip()
        lost = (raw != "") & df[num_col].isna()
        check(f"{label}: '{raw_col}' → '{num_col}' 변환 손실 없음", lost.sum() == 0, f"손실 {lost.sum()}칸")
        if lost.sum() == 0:
            df = df.drop(columns=raw_col)
    return df


def check(name: str, ok: bool, detail: str = ""):
    report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
    print(("OK   " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


# ---------------------------------------------------------------- 전력수요
def build_demand():
    parts = []
    for f in sorted((RAW / "kpx_demand").glob("*.csv")):
        d = read_csv_any(f)
        d = d[d["날짜"].str.strip() != ""]  # 파일 끝 빈 행 제거(값 없음)
        hours = [c for c in d.columns if c.endswith("시")]
        long = d.melt(id_vars="날짜", value_vars=hours, var_name="hour_label", value_name="demand_raw")
        long["hour"] = long["hour_label"].str.replace("시", "").astype(int)
        long["demand"] = to_num(long["demand_raw"])
        long["source_file"] = f.name
        check(f"수요 {f.name}: 원본 셀 수 = 정리본 행 수", len(long) == len(d) * len(hours), f"{len(long)}행")
        parts.append(long)
    out = pd.concat(parts).rename(columns={"날짜": "date"})
    out["source_id"] = out["source_file"].map(source_id)
    out = out[["date", "hour", "hour_label", "demand", "demand_raw", "source_id"]].sort_values(["date", "hour"])
    out = drop_raw_if_lossless(out, {"demand_raw": "demand"}, "수요")
    dup = out.duplicated(["date", "hour"]).sum()
    check("수요: 날짜·시간 중복 없음", dup == 0, f"중복 {dup}")
    full = pd.date_range(START, END).strftime("%Y-%m-%d")
    missing = sorted(set(full) - set(out["date"]))
    check("수요: 2023~2025 빠진 날짜 없음", not missing, f"빠진 날짜 {len(missing)}")
    out.to_csv(CLEAN / "demand_hourly.csv", index=False, encoding="utf-8-sig")
    return out


# ---------------------------------------------------------------- 태양광·풍력
def _wide(df, f, region_col, solar_col, wind_col):
    rows = []
    for fuel, col in (("태양광", solar_col), ("풍력", wind_col)):
        x = df[["거래일자", "거래시간", region_col, col]].copy()
        x.columns = ["date", "hour_raw", "region_raw", "value_raw"]
        x["fuel"] = fuel
        rows.append(x)
    out = pd.concat(rows)
    out["source_file"] = f
    return out


def build_renewable():
    parts = []
    d = RAW / "kpx_renewable"
    # 2017-01 ~ 2023-02 묶음(zip): 2023년 1~2월만 사용
    zf = zipfile.ZipFile(d / "한국전력거래소_지역별 시간별 태양광 발전량_20230228.zip")
    for info in zf.infolist():
        z = read_csv_any(zf.read(info))
        z = z[(z["거래일자"] >= START) & (z["거래일자"] <= "2023-02-28")]
        parts.append(_wide(z, "한국전력거래소_지역별 시간별 태양광 발전량_20230228.zip", "지역",
                           "태양광 발전량(MWh)", "풍력 발전량(MWh)"))
    for name, rc, sc, wc in [
        ("20230531", "지역", "태양광 발전량(MWh)", "풍력 발전량(MWh)"),
        ("20230831", "지역", "태양광발전량(MWh)", "풍력발전량(MWh)"),
        ("20231130", "지역명", "태양광발전량(Mwh)", "풍력발전량(Mwh)"),
    ]:
        fn = f"한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_{name}.csv"
        parts.append(_wide(read_csv_any(d / fn), fn, rc, sc, wc))
    for name in ("20230610", "20241231", "20251231"):  # 세로형 (20230610 은 2023년 12월 자료)
        fn = f"한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_{name}.csv"
        x = read_csv_any(d / fn)
        x = x.rename(columns={"거래일자": "date", "거래일": "date", "거래시간": "hour_raw", "지역": "region_raw",
                              "연료원": "fuel", "발전량(MWh)": "value_raw", "전력거래량(MWh)": "value_raw"})
        x["source_file"] = fn
        parts.append(x[["date", "hour_raw", "region_raw", "fuel", "value_raw", "source_file"]])
    out = pd.concat(parts, ignore_index=True)
    out["region_raw"] = out["region_raw"].str.strip()
    out["region_std"] = out["region_raw"].map(REGION_STD)
    out["region_level"] = out["region_raw"].map(lambda r: "권역합계" if r in AGGREGATE_REGIONS else "시도")
    out["hour"] = out["hour_raw"].str.strip().astype(int)
    out["value_mwh"] = to_num(out["value_raw"].str.replace(",", ""))  # "1,028.44" 같은 천 단위 쉼표
    out["value_blank"] = out["value_raw"].str.strip() == ""
    out = out[(out["date"] >= START) & (out["date"] <= END)]
    check("태양광·풍력: 모든 지역명이 매핑됨", out["region_std"].notna().all(),
          ",".join(sorted(out.loc[out["region_std"].isna(), "region_raw"].unique())))
    key = ["date", "hour", "region_raw", "fuel"]
    dups = out[out.duplicated(key, keep=False)]
    conflict = dups.groupby(key)["value_raw"].nunique()
    check("태양광·풍력: 겹치는 파일 사이 값 충돌 없음", (conflict <= 1).all(),
          f"겹치는 키 {len(conflict)}개, 충돌 {(conflict > 1).sum()}개")
    out = out.drop_duplicates(key)
    full = set(pd.date_range(START, END).strftime("%Y-%m-%d"))
    sol = out[(out["fuel"] == "태양광") & (out["region_level"] == "시도")]
    missing = sorted(full - set(sol["date"]))
    check("태양광: 2023~2025 빠진 날짜 없음", not missing, f"빠진 날짜 {len(missing)}")
    out["source_id"] = out["source_file"].map(source_id)
    cols = ["date", "hour", "region_raw", "region_std", "region_level", "fuel",
            "value_mwh", "value_raw", "value_blank", "source_id"]
    out = drop_raw_if_lossless(out[cols], {"value_raw": "value_mwh"}, "태양광·풍력")
    out = out.sort_values(["date", "hour", "fuel", "region_raw"])
    out.to_csv(CLEAN / "renewable_hourly.csv", index=False, encoding="utf-8-sig")
    return out


# ---------------------------------------------------------------- 연료원별 설비용량·거래량
def build_fuel():
    parts = []
    for f in sorted((RAW / "kpx_fuel").glob("*.csv")):
        x = read_csv_any(f)
        x = x.rename(columns={"거래일자": "date", "시간": "hour_raw", "거래시간": "hour_raw",
                              "연료원": "fuel_raw", "원료원": "fuel_raw", "연료원별": "fuel_raw",
                              "설비용량(MW)": "capacity_raw", "전력거래량(MWh)": "generation_raw"})
        x["source_file"] = f.name
        parts.append(x[["date", "hour_raw", "fuel_raw", "capacity_raw", "generation_raw", "source_file"]])
    out = pd.concat(parts, ignore_index=True)
    out["fuel_raw"] = out["fuel_raw"].str.strip()
    out["hour"] = out["hour_raw"].str.strip().astype(int)
    out["capacity_mw"] = to_num(out["capacity_raw"].str.replace(",", ""))
    out["generation_mwh"] = to_num(out["generation_raw"].str.replace(",", ""))
    cover = out.groupby(out["date"].str[:4])["fuel_raw"].apply(lambda s: sorted(s.unique()))
    report["fuel_coverage"] = {y: v for y, v in cover.items()}
    has_nuc = {y: ("원자력" in v) for y, v in cover.items()}
    check("연료원: 연도별 원자력 포함 여부 기록", True, json.dumps(has_nuc, ensure_ascii=False))
    out = out[(out["date"] >= START) & (out["date"] <= END)]
    out["source_id"] = out["source_file"].map(source_id)
    out = out[["date", "hour", "fuel_raw", "capacity_mw", "generation_mwh",
               "capacity_raw", "generation_raw", "source_id"]]
    out = drop_raw_if_lossless(out, {"capacity_raw": "capacity_mw", "generation_raw": "generation_mwh"}, "연료원")
    out = out.sort_values(["date", "hour", "fuel_raw"])
    out.to_csv(CLEAN / "fuel_hourly.csv", index=False, encoding="utf-8-sig")
    return out


# ---------------------------------------------------------------- 기상 관측
def build_weather():
    parts = []
    for f in sorted((RAW / "kma_asos").glob("*.csv")):
        x = read_csv_any(f)
        x["source_file"] = f.name
        parts.append(x)
    out = pd.concat(parts, ignore_index=True)
    rename = {"지점": "station_id", "지점명": "station_name", "일시": "datetime_kst",
              "기온(°C)": "temp_c", "풍속(m/s)": "wind_ms", "일조(hr)": "sunshine_hr",
              "일사(MJ/m2)": "radiation_mj_m2", "전운량(10분위)": "cloud_10"}
    out = out.rename(columns=rename)
    for c in ("temp_c", "wind_ms", "sunshine_hr", "radiation_mj_m2", "cloud_10"):
        out[c] = to_num(out[c])  # 빈칸 = 결측(밤 시간 일사·일조는 관측값 없음)
    out["station_excluded"] = out["station_name"].eq("북부산")  # 2023-01-11 시작·낮 결측 많음. 삭제하지 않고 표시만.
    dup = out.duplicated(["station_id", "datetime_kst"]).sum()
    check("기상: 지점·시각 중복 없음", dup == 0, f"중복 {dup}")
    out["source_id"] = out["source_file"].map(source_id)
    cols = ["station_id", "station_name", "datetime_kst", "temp_c", "wind_ms", "sunshine_hr",
            "radiation_mj_m2", "cloud_10", "station_excluded", "source_id"]
    out[cols].sort_values(["station_id", "datetime_kst"]).to_csv(
        CLEAN / "weather_obs_hourly.csv", index=False, encoding="utf-8-sig")
    return out


# ---------------------------------------------------------------- 출력제어 (정답)
def build_curtailment():
    zf = zipfile.ZipFile(RAW / "kpx_curtailment" / "한국전력거래소_전국 태양광 풍력 제어횟수 및 제주 풍력 제어량_20260930.zip")
    rows = []
    for info in zf.infolist():
        name = info.filename
        x = read_csv_any(zf.read(info))
        grid = "육지" if "육지" in name else "제주"
        fuel = "태양광" if "태양광" in name else "풍력"
        hours = [c for c in x.columns if c.endswith("시") and c[:-1].isdigit()]
        other = [c for c in x.columns if c not in hours]
        y = pd.DataFrame({"date": x["일자"].str.strip(), "grid": grid, "fuel": fuel})
        if "제어지역" in x.columns:
            y["control_regions_raw"] = x["제어지역"]
        for c in other:
            if c not in ("일자", "제어지역"):
                y[f"extra_{c}"] = x[c]
        for h in hours:
            y[f"h{int(h[:-1]):02d}_raw"] = x[h]
        y["source_file"] = Path(zf.filename).name + "/" + name
        rows.append(y)
    out = pd.concat(rows, ignore_index=True)
    hcols = sorted(c for c in out.columns if c.startswith("h") and c.endswith("_raw"))
    vals = out[hcols].fillna("").apply(lambda s: s.str.strip())
    # 제주 풍력 파일은 시간 칸에 제어량(MWh) 숫자가 들어 있음. 같은 열 이름이라도 의미가 다르므로 구분한다.
    is_amount = out["source_file"].str.split("/").str[-1].str.contains("제어량")  # zip 이름이 아니라 안쪽 파일 이름으로 판단
    out["hour_value_type"] = is_amount.map({True: "제어량_MWh", False: "제어여부(출력제어/0)"})
    flag_vals = vals[~is_amount]
    amt_vals = vals[is_amount].apply(pd.to_numeric, errors="coerce")
    out["n_hours_controlled"] = pd.concat([
        (flag_vals == "출력제어").sum(axis=1),
        (amt_vals > 0).sum(axis=1),
    ]).sort_index()
    out["has_blank_hour"] = (vals == "").any(axis=1)
    known = flag_vals.isin(["출력제어", "0", ""]).all(axis=1)
    check("출력제어(제어여부 파일): 시간 칸 값이 '출력제어'/'0'/빈칸 중 하나", known.all(),
          f"예외 행 {(~known).sum()}")
    numeric_ok = vals[is_amount].apply(lambda s: s.eq("") | pd.to_numeric(s, errors="coerce").notna()).all(axis=1)
    check("출력제어(제주 풍력 제어량 파일): 시간 칸이 모두 숫자 또는 빈칸", numeric_ok.all(),
          f"예외 행 {(~numeric_ok).sum()}")

    def std_regions(s):
        if pd.isna(s) or not str(s).strip():
            return "", ""
        raw = str(s)
        notes = []
        toks = [t.strip() for t in raw.replace("  ", ",").split(",")]
        fixed = []
        for t in toks:
            if not t:
                notes.append("빈 항목(끝 쉼표)")
                continue
            for part in t.split(" "):  # 쉼표 누락('충북 부산') 분리
                if not part:
                    continue
                if " " in t:
                    notes.append(f"쉼표 누락 추정: '{t}'")
                if part in CTRL_REGION_FIX:
                    notes.append(f"표기 보정: {part}→{CTRL_REGION_FIX[part]}")
                    part = CTRL_REGION_FIX[part]
                fixed.append(part)
        return ",".join(dict.fromkeys(fixed)), "; ".join(dict.fromkeys(notes))

    if "control_regions_raw" in out:
        r = out["control_regions_raw"].apply(std_regions)
        out["control_regions_std"] = [a for a, _ in r]
        out["region_fix_note"] = [b for _, b in r]
    out = out.sort_values(["grid", "fuel", "date"])
    out.to_csv(CLEAN / "curtailment_daily.csv", index=False, encoding="utf-8-sig")
    lab = out[out["grid"] == "육지"].groupby("date").size()
    report["curtailment_days_by_year"] = lab.groupby(lab.index.str[:4]).size().to_dict()
    check("출력제어: 육지 연도별 발생일 기록", True, json.dumps(report["curtailment_days_by_year"]))
    return out


# ---------------------------------------------------------------- 실행
if __name__ == "__main__":
    for f in sorted(RAW.rglob("*")):
        if f.is_file():
            report["files"][str(f.relative_to(ROOT))] = {"sha256": sha256(f), "bytes": f.stat().st_size}
    build_demand()
    build_renewable()
    build_fuel()
    build_weather()
    build_curtailment()
    pd.DataFrame([{"source_id": v, "source_file": k} for k, v in report["sources"].items()]).to_csv(
        CLEAN / "sources.csv", index=False, encoding="utf-8-sig")
    (ROOT / "data" / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [c for c in report["checks"] if not c["ok"]]
    print(f"\n검증 {len(report['checks'])}개 중 실패 {len(failed)}개")
