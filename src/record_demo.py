"""시연 백업 영상 만들기 (대회 규정: 2분 이내, 핵심 기능이 작동하는 화면 녹화).

실행: python src/record_demo.py  → demo/backup_demo.mp4 (Playwright Chromium, ffmpeg 필요). 자막은 화면 위에 띄운다.
"""
import subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
S = tempfile.mkdtemp()
CAP="""(t)=>{let c=document.getElementById('cap');if(!c){c=document.createElement('div');c.id='cap';
c.style.cssText='position:fixed;left:50%;top:10px;word-break:keep-all;transform:translateX(-50%);max-width:1100px;background:rgba(20,28,45,.92);color:#fff;font:600 21px/1.45 "Noto Sans CJK KR",sans-serif;padding:12px 22px;border-radius:12px;z-index:99;text-align:center;box-shadow:0 4px 18px rgba(0,0,0,.3)';document.body.appendChild(c)}c.textContent=t;c.style.display=t?'block':'none'}"""
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={"width":1280,"height":800},record_video_dir=S+"/vid",record_video_size={"width":1280,"height":800})
    pg=ctx.new_page(); pg.goto((ROOT / "demo" / "index.html").as_uri()); pg.wait_for_timeout(500)
    def cap(t,ms): pg.evaluate(CAP,t); pg.wait_for_timeout(ms)
    def scroll(y): pg.evaluate(f"window.scrollTo({{top:{y},behavior:'smooth'}})"); pg.wait_for_timeout(700)
    cap("출력제어 예보 AI 시연 — 날짜를 고르면, 그 전날 17시에 공개된 정보만으로 낸 예보를 보여 줍니다",5000)
    cap("2025-11-02(일): 위험 높음. 원인 1위는 쉬는 날, 2위는 낮은 전력수요",6000)
    cap("상황에 맞는 대비 방법과 전력거래소 전날 공지 여부(이날은 공지 없음)를 함께 보여 줍니다",5000)
    pg.click("#reveal"); cap("실제 결과: 10~17시 출력제어 — 공지가 없던 날을 전날 미리 알렸습니다",6000)
    pg.click('button[data-d="2025-11-25"]'); cap("2025-11-25(화): 위험 낮음 — 평일이고, 위험을 올린 원인이 뚜렷하지 않습니다",5000)
    pg.click("#reveal"); cap("실제로 출력제어가 없었습니다. 시험 기간 '낮음' 44일 중 출력제어는 0일",5000)
    pg.click("#prev");pg.wait_for_timeout(300);pg.click("#prev");pg.wait_for_timeout(300)
    pg.click('button[data-d="2025-09-20"]'); cap("틀린 날도 보여 줍니다. 2025-09-20(토): 위험 '주의'로 봤는데",5000)
    pg.click("#reveal"); cap("실제로는 출력제어 — 게시판 사유는 전력망 제약. 공개되지 않은 송전망 정보는 모델이 알 수 없습니다",6500)
    pg.click("#next"); pg.wait_for_timeout(300); pg.check("#showact")
    cap("달력에 실제 출력제어(●)를 켜면: 2025년 10월 출력제어 14일 대부분이 빨간 날(높음)에 있습니다",6500)
    scroll(600); cap("2025년 7~12월 시험 성적: 출력제어 27일 중 23일을 전날 '높음'으로 알렸습니다",5500); scroll(0)
    pg.uncheck("#showact"); pg.click("#go26"); cap("2026년 독립 시험: 결과를 보기 전에 계획을 공개하고, 2026년 1~10월로 다시 확인했습니다",5500)
    cap("2026-05-05 어린이날: 위험 높음 — 맑음 예보 100%, 낮은 전력수요",5500)
    pg.click("#reveal"); cap("실제 결과: 9~17시 출력제어",4000)
    pg.check("#showact"); cap("2026년 봄(3~5월) 출력제어 48일 중 46일을 전날 '높음'으로 알렸습니다",6000)
    scroll(900); cap("한계도 그대로 밝힙니다: 여름·가을 헛경보가 많고, 공개 자료만으로는 간단한 규칙과 비슷한 순위 정확도",6500); scroll(0)
    cap("팀 플랜티즈 — 출력제어 예보 AI",3000)
    v=pg.video.path(); ctx.close(); b.close()
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", v, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(ROOT / "demo" / "backup_demo.mp4")], check=True)
print("demo/backup_demo.mp4")
