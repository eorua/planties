"""시연 화면 만들기: outputs/demo_days.csv (src/explain.py) → demo/index.html (파일 하나, 인터넷 연결 없이 열림)."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
d = pd.read_csv(ROOT / "outputs" / "demo_days.csv").fillna("")
rows = d.to_dict(orient="records")
tpl = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
html = tpl.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
head = '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
(ROOT / "demo" / "index.html").write_text(head + html.replace("<style>", "</head><body>\n<style>", 1) + "\n</body></html>\n", encoding="utf-8")
print("demo/index.html", len(rows), "일")
