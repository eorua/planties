"""시연 백업 영상 만들기 (대회 규정: 2분 이내, 핵심 기능이 작동하는 화면 녹화).

실행: python src/record_demo.py  → demo/backup_demo.mp4 (Playwright Chromium, ffmpeg 필요). 자막은 화면 위에 띄운다.
화면은 예보문 구성(2026-11 새 시연 화면). 자막의 숫자는 outputs/ 결과와 같아야 하므로, 숫자가 바뀌면 자막도 고친다.
"""
import subprocess, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
S = tempfile.mkdtemp()
CAP = """(t)=>{let c=document.getElementById('cap');if(!c){c=document.createElement('div');c.id='cap';
c.style.cssText='position:fixed;left:50%;bottom:16px;word-break:keep-all;transform:translateX(-50%);max-width:1120px;background:rgba(20,28,45,.92);color:#fff;font:600 21px/1.45 "Pretendard","Noto Sans CJK KR",sans-serif;padding:12px 22px;border-radius:12px;z-index:99;text-align:center;box-shadow:0 4px 18px rgba(0,0,0,.3)';document.body.appendChild(c)}c.textContent=t;c.style.display=t?'block':'none'}"""
GO = "([d,y,m])=>{sel=d;cur=new Date(y,m-1,1);reveal=false;cal();show()}"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=S + "/vid",
                        record_video_size={"width": 1280, "height": 800})
    pg = ctx.new_page(); pg.goto((ROOT / "demo" / "index.html").as_uri()); pg.wait_for_timeout(500)

    def cap(t, ms): pg.evaluate(CAP, t); pg.wait_for_timeout(ms)
    def to(sel_css): pg.evaluate(f"document.querySelector('{sel_css}').scrollIntoView({{behavior:'smooth',block:'start'}})"); pg.wait_for_timeout(800)
    def top(): pg.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); pg.wait_for_timeout(800)
    def go(d): pg.evaluate(GO, [d, int(d[:4]), int(d[5:7])]); pg.wait_for_timeout(300)

    go("2025-11-02")
    cap("출력제어 예보 AI 시연 — 전날 17시에 알 수 있던 정보만으로 낸 '내일 예보'를 보여 줍니다", 5000)
    cap("2025-11-02(일) 예보: 출력제어 확률 70% 이상, 위험도 4단계 중 '매우 높음'", 5000)
    cap("그래프 왼쪽은 지난 2주의 실제 기록: 출력제어(빨간 점·블록) 5일 중 4일이 쉬는 날(회색 띠)이었습니다", 6500)
    cap("오른쪽 칸이 내일 예보입니다. 내일도 일요일이고, 오늘도 출력제어가 있었습니다", 5500)
    pg.click("#reveal"); top()
    cap("'실제 결과 보기': 점선 예보 칸이 실제 기록(10~17시 출력제어)으로 바뀝니다. 전력거래소 전망 공지가 없던 날입니다", 6500)

    to(".mnav"); cap("달력에서 다른 날을 고를 수 있습니다. 틀린 날도 그대로 보여 줍니다", 4000)
    pg.click("#prev"); pg.wait_for_timeout(300); pg.click("#prev"); pg.wait_for_timeout(300)
    pg.click('button[data-d="2025-09-20"]'); top()
    cap("2025-09-20(토): 지난 2주 출력제어가 없어 확률 약 10%, '주의'로 봤는데", 5000)
    pg.click("#reveal"); top()
    cap("실제로는 출력제어 — 게시판 사유는 전력망 제약. 공개되지 않은 송전망 사정은 모델이 알 수 없습니다", 6500)

    go("2025-10-25"); to(".mnav"); pg.check("#showact")
    cap("달력에 실제 출력제어(●)를 켜면: 2025년 10월 출력제어 14일 중 13일이 '매우 높음'으로 예보한 날이었습니다", 6500)
    pg.uncheck("#showact")

    go("2026-10-02"); top()
    cap("2026년 독립 시험(개발에 쓰지 않은 1~10월): 2026-10-02(금) 예보는 확률 50% 안팎, '매우 높음'", 5500)
    pg.click("#reveal"); top()
    cap("이날의 정답은 모델을 정한 뒤인 11월 12일에야 게시판에 올라왔고, 실제로 출력제어가 있었습니다", 6000)

    to("#k26"); cap("2026년 1~10월: 출력제어 73일 중 63일을 전날 알렸고, '매우 높음'인 날의 68%에 실제 출력제어가 있었습니다", 6500)
    go("2025-11-02"); to("#k25")
    cap("2025년 7~12월: 27일 중 24일 알림, '낮음'이라 한 64일에는 한 번도 없었습니다. 헛경보 26번도 함께 밝힙니다", 6500)
    cap("가정: 출력제어를 하거나 지시받는 쪽은 전날까지의 출력제어 여부와 전력거래소 전날 전망을 안다", 5500)
    top(); cap("팀 플랜티즈 — 출력제어 예보 AI", 3000)
    v = pg.video.path(); ctx.close(); b.close()

subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", v, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(ROOT / "demo" / "backup_demo.mp4")], check=True)
print("demo/backup_demo.mp4")
