"""기상청 단기예보(과거 자료) 원본 zip → 정리본.

원칙 (build_clean.py 와 같음)
- 원본(data/raw/kma_forecast/zips)은 그대로 둔다.
- 값은 바꾸지 않는다. 깨진 행은 고치지 않고 빼되, 뺀 이유와 개수를 모두 기록한다.
- 같은 (발표일·발표시각·선행시간) 이 두 번 나오면 값이 같을 때만 하나로 합친다.
  값이 다르면 둘 다 빼고 충돌로 기록한다.

원본 형식 (기상자료개방포털 단기예보 CSV, CP949)
- 첫 줄: "format: day(UTC),hour(UTC),forecast,value[,day(KST),hour(KST)] location:59_75 Start : YYYYMMDD"
- 날짜마다 "Start : YYYYMMDD" 줄 뒤에 그 날 발표분이 이어진다.
- 행: 일, 발표시각(HHMM, UTC), 선행시간(+h), 값 [, KST 일, KST 시각 (2025 파일만)]

2026년분 (k26_*.zip, 2026-11-11 수집): 2026-01-01 ~ 2026-10-31, 한 달 단위 요청 + 깨진 날 하루 단위 재요청.
- 2026년 시험(독립 시험)용. 기간 끝은 YEAR_END 에 적는다.

보충분 (refill_*.zip)
- 결함 때문에 빠진 날을 하루 단위로 다시 요청해 받은 것. 기존 행과 같은 키면 값이 같을 때만 합친다.
- 하루 단위로 다시 받아도 깨져 오는 날은 원본 손상으로 보고 빈칸으로 둔다.

알려진 원본 결함 (2023~2024 파일)
- 일(day) 칸이 -971917344 같은 깨진 값이고 값이 모두 0인 블록 → 제외 (bad_day)
- 일 칸이 Start 날짜와 다른 블록 (다른 날 자료가 섞인 것으로 보임) → 제외 (day_mismatch)
"""
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "kma_forecast" / "zips"
CLEAN = ROOT / "data" / "clean"

LOC = {"운암1동": ("광주", "59_75"), "연산동": ("목포", "50_67"), "송천1동": ("전주", "63_90"),
       "신암1동": ("대구", "89_91"), "대청동": ("부산", "97_74")}
ELEM = {"하늘상태": "SKY", "강수확률": "POP", "일최고기온": "TMX"}
YEAR_END = {"2026": "20261031"}   # 다 받지 않은 해의 마지막 날
NAME_RE = re.compile(r"(.+?)_(.+?)_(\d{8})_(\d{8})\.csv$")

checks, excluded = [], []


def check(name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("OK  " if ok else "FAIL"), name, detail)


def entries():
    for z in sorted(RAW.glob("*.zip")):
        zf = zipfile.ZipFile(z)
        for info in zf.infolist():
            name = info.filename.encode("cp437").decode("cp949")  # zip 안 이름이 CP949
            yield z.name, name, zf.read(info).decode("cp949")


def parse(zipname, name, text):
    m = NAME_RE.match(name)
    dong, elem_kr, f, t = m.groups()
    grid_in_header = re.search(r"location:(\d+_\d+)", text.splitlines()[0]).group(1)
    rows, reasons = [], Counter()
    start = None
    for line in text.splitlines():
        if "Start" in line:
            start = re.search(r"Start : (\d{8})", line).group(1)
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) < 4 or not p[0]:
            continue
        day = int(p[0])
        if not 1 <= day <= 31:
            reasons["bad_day"] += 1
            continue
        if day != int(start[6:]):
            reasons["day_mismatch"] += 1
            continue
        rows.append((start, p[1], int(p[2]), p[3]))
    for r, n in reasons.items():
        excluded.append({"zip": zipname, "file": name, "reason": r, "rows": n})
    return dong, elem_kr, f, t, grid_in_header, rows


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    acc = defaultdict(dict)        # (dong, elem, year) -> {(date, hhmm, lead): value_raw}
    conflicts = defaultdict(set)
    coverage = defaultdict(list)
    n_files = 0
    for zipname, name, text in entries():
        n_files += 1
        dong, elem_kr, f, t, grid, rows = parse(zipname, name, text)
        check(f"{name}: 머리말 격자 = 지점 격자", grid == LOC[dong][1], f"{grid} vs {LOC[dong][1]}")
        key = (dong, elem_kr, f[:4])
        if not zipname.startswith("refill_") and f != t:  # 보충분(빠진 날 하루 단위로 다시 받은 것)은 기간 점검에서 뺀다
            coverage[key].append((f, t))
        d = acc[key]
        for date, hhmm, lead, val in rows:
            k = (date, hhmm, lead)
            if k in d and d[k] != val:
                conflicts[key].add(k)
            d[k] = val

    check("원본 파일 수", n_files > 0, f"{n_files}개")
    n_years = len({k[2] for k in acc})
    check(f"지점·요소·연도 조합 {15 * n_years}개", len(acc) == 15 * n_years, f"{len(acc)}개")
    for key, ranges in coverage.items():
        rs = sorted(ranges)
        y = key[2]
        cont = rs[0][0] == y + "0101" and rs[-1][1] == YEAR_END.get(y, y + "1231") and all(
            (pd.Timestamp(a[1]) + pd.Timedelta(days=1)) == pd.Timestamp(b[0]) for a, b in zip(rs, rs[1:]))
        if not cont:
            check(f"{key}: 요청 기간이 1년을 빈틈없이 덮음", False, str(rs))
    check("모든 조합의 요청 기간이 1년을 빈틈없이 덮음", True)

    total_conf = sum(len(v) for v in conflicts.values())
    check("같은 발표·선행시간 값 충돌", True, f"충돌 {total_conf}건 (충돌 키는 제외)")

    by_year = defaultdict(list)
    summary = []
    for (dong, elem_kr, y), d in sorted(acc.items()):
        bad = conflicts[(dong, elem_kr, y)]
        df = pd.DataFrame([(k[0], k[1], k[2], v) for k, v in d.items() if k not in bad],
                          columns=["issue_date_utc", "issue_hhmm_utc", "lead_h", "value_raw"])
        df["value"] = pd.to_numeric(df["value_raw"], errors="coerce")
        lost = df["value"].isna().sum()
        if lost:
            check(f"{dong} {elem_kr} {y}: 값 숫자 변환", False, f"{lost}칸")
        df = df.drop(columns="value_raw")
        # 기상청 결측 표시값 -999.9 (원본에는 -999.900024 로 저장) → 숫자가 아니라 빈칸. 표시 열로 남긴다.
        df["value_missing_code"] = df["value"] <= -999
        df.loc[df["value_missing_code"], "value"] = pd.NA
        n_miss = int(df["value_missing_code"].sum())
        if n_miss:
            excluded.append({"zip": "(여러 파일)", "file": f"{dong}_{elem_kr}_{y}", "reason": "missing_code_-999.9",
                             "rows": n_miss})
        df.insert(0, "element", ELEM[elem_kr])
        df.insert(0, "grid", LOC[dong][1])
        df.insert(0, "dong", dong)
        df.insert(0, "station_area", LOC[dong][0])
        days_expected = (pd.Timestamp(YEAR_END.get(y, y + "1231")) - pd.Timestamp(y + "0101")).days + 1
        days = df.loc[~df["value_missing_code"], "issue_date_utc"].nunique()  # 결측 표시값만 있는 날은 빠진 날로 셈
        summary.append({"area": LOC[dong][0], "dong": dong, "element": ELEM[elem_kr], "year": y,
                        "issue_days": days, "days_in_year": days_expected,
                        "missing_days": days_expected - days, "rows": len(df), "conflicts": len(bad)})
        by_year[y].append(df)

    for y, parts in by_year.items():
        out = pd.concat(parts).sort_values(["station_area", "element", "issue_date_utc", "issue_hhmm_utc", "lead_h"])
        out["issue_date_utc"] = pd.to_datetime(out["issue_date_utc"]).dt.strftime("%Y-%m-%d")
        out.to_csv(CLEAN / f"kma_forecast_{y}.csv.gz", index=False,
                   compression={"method": "gzip", "mtime": 0})  # 시각 고정 → 다시 만들어도 같은 파일
    pd.DataFrame(summary).to_csv(CLEAN / "kma_forecast_coverage.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(excluded).to_csv(CLEAN / "kma_forecast_excluded.csv", index=False, encoding="utf-8-sig")

    s = pd.DataFrame(summary)
    print(s.groupby("year")[["missing_days"]].agg(["min", "max", "sum"]))
    ex = pd.DataFrame(excluded).groupby("reason")["rows"].sum().to_dict()
    check("제외한 원본 행 기록", True, json.dumps(ex, ensure_ascii=False))
    (ROOT / "data" / "build_report_forecast.json").write_text(
        json.dumps({"checks": checks, "excluded_rows": ex}, ensure_ascii=False, indent=1), encoding="utf-8")
    n_fail = sum(not c["ok"] for c in checks)
    print(f"\n검증 {len(checks)}개 중 실패 {n_fail}개")


if __name__ == "__main__":
    main()
