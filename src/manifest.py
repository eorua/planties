"""원본(raw)과 정리본(clean) 파일의 SHA-256 지문을 기록하고 검사한다.

    python src/manifest.py write    # 지문 새로 기록 (build_clean.py 실행 직후에만)
    python src/manifest.py verify   # 지금 파일이 기록된 지문과 같은지 확인

verify 가 하나라도 FAIL 이면 누군가 파일을 손으로 고쳤거나 다른 버전이 섞인 것이다.
그래프·PPT·학습에 쓰기 전에 verify 를 먼저 돌린다.
"""
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "MANIFEST.csv"
TARGETS = ["data/raw", "data/clean", "data/manual", "data/features"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files():
    for t in TARGETS:
        for p in sorted((ROOT / t).rglob("*")):
            if p.is_file():
                yield p


def write():
    rows = []
    for p in files():
        rel = p.relative_to(ROOT).as_posix()
        n = None
        if p.suffix == ".csv" and rel.startswith("data/clean"):
            with p.open(encoding="utf-8-sig") as f:
                n = sum(1 for _ in f) - 1
        rows.append({"path": rel, "layer": rel.split("/")[1], "bytes": p.stat().st_size,
                     "rows": n if n is not None else "", "sha256": sha256(p)})
    with MANIFEST.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["path", "layer", "bytes", "rows", "sha256"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)}개 파일 지문 기록 → {MANIFEST.relative_to(ROOT)}")


def verify() -> int:
    with MANIFEST.open(encoding="utf-8-sig") as f:
        recorded = {r["path"]: r["sha256"] for r in csv.DictReader(f)}
    now = {p.relative_to(ROOT).as_posix(): p for p in files()}
    bad = 0
    for path, h in recorded.items():
        if path not in now:
            print(f"FAIL 없어짐  {path}"); bad += 1
        elif sha256(now[path]) != h:
            print(f"FAIL 내용 바뀜 {path}"); bad += 1
    for path in now.keys() - recorded.keys():
        print(f"FAIL 기록에 없는 새 파일 {path}"); bad += 1
    print(f"검사 {len(recorded)}개, 문제 {bad}개")
    return bad


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "write":
        write()
    else:
        sys.exit(1 if verify() else 0)
