// 본선 발표자료 (A안 색감: 종이색·검정·주황 한 색). 숫자 출처: docs/MODEL_RESULTS.md 17장, outputs/*.json, outputs/live_record.csv
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const F = "Pretendard", FB = "Pretendard Black";
const K = { bg: "F6F4EF", ink: "15161A", sub: "3A3B40", mute: "6B6B70", line: "D9D5CC", card: "ECE8DF", sig: "E4572E", sigSoft: "F6D3C6",
  tier: ["E4572E", "F2994A", "E2C25F", "7FAF7A"] };
const DEMO = require("path").join(__dirname, "../../docs/slides/captures/final_demo_2025-11-02.png");
const ASSUME = "출력제어를 지시받는 쪽은 전날까지의 출력제어 여부와 전력거래소의 전날 전망을 안다고 가정. 미리 보지 않은 기간을 전날 17시 기준으로 예측한 결과.";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; p.title = "출력제어 예보 AI — 본선 발표자료"; p.author = "플랜티즈";
p.theme = { headFontFace: F, bodyFontFace: F };
const W = 13.333;

const T = (s, txt, o) => s.addText(txt, Object.assign({ fontFace: F, isTextBox: true, margin: 0, color: K.ink, valign: "top" }, o));
const line = (s, x, y, w, h, color, width) => s.addShape(p.shapes.LINE, { x, y, w, h, line: { color: color || K.line, width: width || 1 } });
const box = (s, x, y, w, h, fill, o) => s.addShape(p.shapes.RECTANGLE, Object.assign({ x, y, w, h, fill: { color: fill }, line: { type: "none" } }, o || {}));

let page = 0;
function slide(sec, title, opts = {}) {
  const s = p.addSlide(); s.background = { color: K.bg }; page++;
  T(s, sec, { x: 0.7, y: 0.45, w: 6, h: 0.3, fontSize: 13, bold: true, color: K.sig });
  T(s, "출력제어 예보 AI", { x: 8.6, y: 0.45, w: 4.03, h: 0.3, fontSize: 12, color: K.mute, align: "right" });
  line(s, 0.7, 0.85, W - 1.4, 0, K.ink, 1.25);
  T(s, title, { x: 0.7, y: 1.05, w: opts.tw || 11.9, h: opts.th || 1.2, fontFace: FB, fontSize: opts.ts || 30, lineSpacingMultiple: 1.05 });
  T(s, String(page), { x: 12.13, y: 7.0, w: 0.5, h: 0.25, fontSize: 11, color: K.mute, align: "right" });
  if (opts.note) T(s, "* " + opts.note, { x: 0.7, y: 6.92, w: 11.2, h: 0.4, fontSize: 10, color: K.mute, valign: "bottom" });
  return s;
}

// ───────────── 1. 표지
{
  const s = p.addSlide(); s.background = { color: K.bg }; page++;
  T(s, "2026 안양대학교 AI 경진대회 · 본선", { x: 0.7, y: 0.55, w: 6, h: 0.3, fontSize: 13, color: K.mute });
  T(s, "플랜티즈  AI26-014", { x: 8.6, y: 0.55, w: 4.03, h: 0.3, fontSize: 13, color: K.mute, align: "right" });
  line(s, 0.7, 0.95, W - 1.4, 0, K.ink, 1.25);
  T(s, "재생에너지가\n멈출 날을,\n전날 알려 드립니다", { x: 0.7, y: 1.4, w: 7.4, h: 3.4, fontFace: FB, fontSize: 52, lineSpacingMultiple: 0.98 });
  T(s, "출력제어 예보 AI", { x: 0.7, y: 4.95, w: 6, h: 0.5, fontSize: 22, bold: true, color: K.sig });
  line(s, 8.55, 1.5, 0, 4.6);
  T(s, "2026년 출력제어 82일 중", { x: 8.95, y: 1.5, w: 3.8, h: 0.4, fontSize: 18, color: K.mute });
  T(s, "69일", { x: 8.85, y: 1.95, w: 3.9, h: 1.6, fontFace: FB, fontSize: 100 });
  T(s, "전날 ‘높음’ 이상으로 알렸습니다", { x: 8.95, y: 3.65, w: 3.8, h: 0.4, fontSize: 16 });
  T(s, "출력제어가 걸린 시간 기준으로는 88%", { x: 8.95, y: 4.15, w: 3.8, h: 0.4, fontSize: 14, bold: true, color: K.sig });
  T(s, "2026년 1~10월, 미리 보지 않은 기간을 전날 예측", { x: 8.95, y: 5.55, w: 3.8, h: 0.5, fontSize: 11, color: K.mute });
  line(s, 0.7, 6.45, W - 1.4, 0);
  T(s, "정대겸 · 안성준 · 양성우    정보전기전자공학과", { x: 0.7, y: 6.62, w: 8, h: 0.35, fontSize: 14 });
  s.addNotes("재생에너지가 멈출 날을 전날 알려 주는 AI, 출력제어 예보 AI입니다. 올해 1~10월 출력제어가 난 82일 중 69일을 전날 미리 알렸습니다.");
}

// ───────────── 2. 문제
{
  const s = slide("01  문제", "전기가 남아 태양광을 강제로 끄는 날,\n3년 만에 40배", { th: 1.3 });
  T(s, "육지 출력제어가 있었던 날 수", { x: 0.7, y: 2.55, w: 6, h: 0.3, fontSize: 13, color: K.mute });
  s.addChart(p.charts.BAR, [{ name: "출력제어일", labels: ["2023", "2024", "2025", "2026 (1~10월)"], values: [2, 27, 82, 82] }], {
    x: 0.55, y: 2.85, w: 7.0, h: 3.85, barDir: "col", barGapWidthPct: 55,
    chartColors: ["BDB7AA", "BDB7AA", K.sig, K.sig],
    showValue: true, dataLabelFormatCode: '0"일"', dataLabelFontSize: 20, dataLabelFontBold: true, dataLabelColor: K.ink, dataLabelFontFace: F,
    catAxisLabelFontFace: F, catAxisLabelFontSize: 14, catAxisLabelColor: K.ink, catAxisLineShow: true,
    valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 95, showLegend: false });
  line(s, 8.1, 2.6, 0, 4.0);
  T(s, "출력제어란", { x: 8.5, y: 2.55, w: 4.1, h: 0.35, fontSize: 14, bold: true, color: K.sig });
  T(s, "쓰는 전기보다 만드는 전기가 많아 전력망이 위험해질 때, 발전소 출력을 강제로 줄이거나 멈추는 조치", { x: 8.5, y: 2.95, w: 4.1, h: 1.2, fontSize: 16, lineSpacingMultiple: 1.25 });
  T(s, "한 번에 얼마나 버려지나", { x: 8.5, y: 4.4, w: 4.1, h: 0.35, fontSize: 14, bold: true, color: K.sig });
  T(s, [{ text: "2024년 4월 7일, 4시간\n", options: { fontSize: 16 } }, { text: "약 1.6GWh · 1.5억 원어치", options: { fontSize: 22, bold: true } }],
    { x: 8.5, y: 4.8, w: 4.1, h: 1.0, lineSpacingMultiple: 1.2 });
  T(s, "봄·가을 쉬는 날 한낮에 집중", { x: 8.5, y: 5.95, w: 4.1, h: 0.4, fontSize: 14, color: K.sub });
  s.addNotes("출력제어는 전기가 남을 때 발전소를 강제로 끄는 조치입니다. 육지에서 2023년 2일이던 것이 2025년 82일로 늘었고, 올해는 10월까지 이미 82일입니다.");
  T(s, "* 한국전력거래소 출력제어 실적·게시판(2026년 6/14~10월). 2024.4.7 규모는 전기신문 보도의 업계 추산(시간당 약 400MWh, SMP 약 95원/kWh).", { x: 0.7, y: 6.92, w: 11.2, h: 0.4, fontSize: 10, color: K.mute, valign: "bottom" });
}

// ───────────── 3. 누구의 하루 (대상 구체화)
{
  const s = slide("02  누구의 문제인가", "출력제어 지시를 받아 발전소를 운영하는 사람의 하루");
  T(s, "예선: 태양광 발전사업자  →  본선: 지시를 직접 받아 여러 발전소를 묶어 운영하는 회사(중개사업자, VPP)까지 좁힘", { x: 0.7, y: 1.7, w: 11.9, h: 0.35, fontSize: 14, color: K.sub });
  const rows = ["전날 17시", "전날 밤", "당일 한낮"];
  const now = ["공식 전날 예고는 82일 중 28일뿐\n나머지는 날씨·요일로 짐작", "짐작이 빗나가면 ESS·정비 계획이 어긋남", "출력제어 지시 → 발전 중단, 버려지는 전기"];
  const ours = ["“내일 출력제어 확률 70% 이상, 매우 높음”\n이유: 쉬는 날 · 최근 출력제어 · 낮은 수요", "ESS를 비워 두고, 정비를 그날 한낮으로", "지시가 와도 미리 준비된 상태"];
  const x0 = 0.7, cL = 2.1, cW = 4.55, y0 = 2.45;
  T(s, "지금", { x: x0 + cL, y: y0, w: cW, h: 0.4, fontSize: 16, bold: true, color: K.mute });
  T(s, "우리 예보가 있으면", { x: x0 + cL + cW + 0.25, y: y0, w: cW, h: 0.4, fontSize: 16, bold: true, color: K.sig });
  rows.forEach((r, i) => {
    const y = y0 + 0.55 + i * 1.04;
    line(s, x0, y, cL + cW * 2 + 0.25, 0);
    T(s, r, { x: x0, y: y + 0.18, w: cL - 0.2, h: 0.4, fontSize: 16, bold: true });
    T(s, now[i], { x: x0 + cL, y: y + 0.18, w: cW - 0.2, h: 0.9, fontSize: 15, color: K.sub, lineSpacingMultiple: 1.2 });
    box(s, x0 + cL + cW + 0.25, y + 0.08, cW, 0.88, i === 0 ? K.sigSoft : K.card);
    T(s, ours[i], { x: x0 + cL + cW + 0.45, y: y + 0.18, w: cW - 0.4, h: 0.85, fontSize: 15, bold: i === 0, lineSpacingMultiple: 1.2 });
  });
  line(s, x0, y0 + 0.55 + 3 * 1.04, cL + cW * 2 + 0.25, 0);
  box(s, 0.7, 6.15, 11.93, 0.62, K.ink);
  T(s, "왜 이 사람인가 — 자기 발전소에 온 지시로 전날까지의 출력제어를 안다. 우리 모델의 가정에 가장 가까운 사용자.", { x: 0.95, y: 6.15, w: 11.5, h: 0.62, fontSize: 15, bold: true, color: "FFFFFF", valign: "middle" });
  s.addNotes("예선에서는 대상을 발전사업자 전체로 잡았는데, 본선에서는 출력제어 지시를 직접 받아 여러 발전소를 묶어 운영하는 회사로 좁혔습니다. 이 사람은 자기 발전소에 온 지시로 전날까지 출력제어가 있었는지를 알기 때문에, 우리 모델의 가정에 가장 가까운 사용자입니다. 이 사람이 원한다고 조사한 것은 아니고, 이런 사람에게 맞게 설계했다는 뜻입니다.");
}

// ───────────── 4. 지금의 빈칸
{
  const s = slide("03  지금의 빈칸", "2026년 출력제어 82일 중 54일은\n전날 전망 공지 없이 왔다", { th: 1.3 });
  // 82칸: 28 전망 있음(검정), 54 없음(주황)
  const cols = 14, sz = 0.36, g = 0.08, x0 = 0.75, y0 = 2.75;
  for (let i = 0; i < 82; i++) {
    const c = i % cols, r = Math.floor(i / cols);
    box(s, x0 + c * (sz + g), y0 + r * (sz + g), sz, sz, i < 28 ? K.ink : K.sig);
  }
  T(s, [{ text: "■ ", options: { color: K.ink } }, { text: "전력거래소 전날 전망이 있던 날 28일     ", options: {} }, { text: "■ ", options: { color: K.sig } }, { text: "전망 없이 온 날 54일", options: {} }],
    { x: 0.75, y: 5.5, w: 6.5, h: 0.35, fontSize: 13 });
  line(s, 7.6, 2.75, 0, 3.6);
  T(s, "54 / 82일", { x: 8.0, y: 2.65, w: 4.6, h: 1.0, fontFace: FB, fontSize: 54, color: K.sig });
  T(s, "출력제어 3번 중 2번은 예고가 없었다", { x: 8.0, y: 3.7, w: 4.6, h: 0.4, fontSize: 16, bold: true });
  T(s, "전망이 틀린 건 아니다. 낸 날은 정확하다\n(29일 중 28일 실제 출력제어). 다만 다루는 날이 적다.", { x: 8.0, y: 4.35, w: 4.6, h: 0.9, fontSize: 14, color: K.sub, lineSpacingMultiple: 1.25 });
  T(s, "게시판 전망 글 73건 중 51건만 전날까지 올라왔다\n(나머지는 당일·사후 게시)", { x: 8.0, y: 5.4, w: 4.6, h: 0.8, fontSize: 14, color: K.sub, lineSpacingMultiple: 1.25 });
  s.addNotes("지금은 전력거래소 게시판의 전날 전망을 보는 게 거의 유일한 방법입니다. 그런데 올해 82일 중 54일은 전망 없이 왔습니다. 전망은 낸 날엔 거의 맞지만, 다루는 날이 적습니다.");
  T(s, "* 한국전력거래소 비중앙 출력제어 정보 게시판, 글 등록일 전수 확인(2026년 1~10월).", { x: 0.7, y: 6.92, w: 11.2, h: 0.4, fontSize: 10, color: K.mute, valign: "bottom" });
}

// ───────────── 5. 해결
{
  const s = slide("04  해결", "전날 17시, 내일의 출력제어를 예보문으로");
  const iw = 7.9, ih = iw * 1330 / 2440;
  box(s, 0.62, 1.92, iw + 0.16, ih + 0.16, K.line);
  s.addImage({ path: DEMO, x: 0.7, y: 2.0, w: iw, h: ih });
  T(s, "시연 화면 · 2025년 11월 2일(일)을 하루 전 17시에 예보한 장면", { x: 0.7, y: 2.0 + ih + 0.2, w: iw, h: 0.3, fontSize: 11, color: K.mute });
  const items = [["확률", "10% 단위, 70% 이상은 ‘70% 이상’"], ["위험도 4단계", ""], ["원인 3가지", "확률을 올린 입력을 날마다 이름으로"], ["대비 안내", "위험도별로 미리 정해 둔 행동 문구"]];
  const x = 9.0; let y = 2.0;
  items.forEach((it, i) => {
    T(s, String(i + 1).padStart(2, "0"), { x, y, w: 0.6, h: 0.4, fontSize: 16, bold: true, color: K.sig });
    T(s, it[0], { x: x + 0.6, y, w: 3.0, h: 0.4, fontSize: 18, bold: true });
    if (i === 1) {
      ["매우 높음", "높음", "주의", "낮음"].forEach((t, j) => { box(s, x + 0.6 + j * 0.9, y + 0.5, 0.82, 0.12, K.tier[j]); T(s, t, { x: x + 0.6 + j * 0.9, y: y + 0.68, w: 0.85, h: 0.3, fontSize: 11, color: K.sub }); });
    } else T(s, it[1], { x: x + 0.6, y: y + 0.45, w: 3.0, h: 0.5, fontSize: 13, color: K.sub });
    y += 1.12;
  });
  line(s, x, 6.45, 3.63, 0);
  T(s, "확률·위험도·원인은 모델이 계산하고, 대비 문구는 위험도에 따라 고정", { x, y: 6.5, w: 3.63, h: 0.45, fontSize: 11, color: K.mute });
  s.addNotes("화면은 일기예보처럼 생겼습니다. 내일 출력제어 확률, 위험도 4단계, 확률을 올린 원인 3가지, 그리고 위험도별 대비 안내를 보여 줍니다. 대비 문구는 AI가 만드는 것이 아니라 위험도에 따라 정해 둔 문구입니다.");
}

// ───────────── 6. AI 구조
{
  const s = slide("05  AI 활용", "외부 자료는 입력만, 판단은 우리가 학습시킨 모델이");
  const cy = 2.1, ch = 3.75;
  const col = (x, w, head, lines, kind) => {
    const team = kind === "team";
    box(s, x, cy, w, ch, team ? "FFFFFF" : K.card, team ? { line: { color: K.sig, width: 2 } } : {});
    T(s, head, { x: x + 0.3, y: cy + 0.25, w: w - 0.6, h: 0.4, fontSize: 16, bold: true, color: team ? K.sig : K.ink });
    T(s, lines.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < lines.length - 1 } })),
      { x: x + 0.3, y: cy + 0.8, w: w - 0.6, h: ch - 1.0, fontSize: 14, color: K.sub, paraSpaceAfter: 7, lineSpacingMultiple: 1.15 });
  };
  col(0.7, 3.55, "입력 (공개 자료)", ["기상청 단기예보: 맑음·강수확률·최고기온, 5개 지역", "전력수요·실시간 수급 (EPSIS)", "공휴일·요일", "어제 태양광·원전 발전 (2025년 모델)", "전날까지 출력제어 여부, 전력거래소 전날 전망"], "in");
  col(4.75, 4.3, "우리가 설계·구현한 것", ["전날 17시에 알 수 있는 값만 고른 특징 표", "트리 모델(그래디언트 부스팅), 매달 1일 다시 학습", "확률 보정과 위험도 4단계 기준 (직전 12개월로만)", "원인 3가지 계산, 예보 화면, 매일 자동 실행"], "team");
  col(9.55, 3.08, "출력", ["내일 출력제어 확률", "위험도 4단계", "원인 3가지·대비 안내", "실제 결과와 대조"], "out");
  [4.25, 9.05].forEach((x) => T(s, "→", { x, y: cy + ch / 2 - 0.3, w: 0.5, h: 0.6, fontSize: 26, bold: true, align: "center", valign: "middle" }));
  T(s, [{ text: "왜 이 모델인가  ", options: { bold: true, color: K.sig } }, { text: "출력제어가 난 날이 백여 일뿐인 표 자료라, 모델 종류는 10가지를 같은 조건에서 비교해 정했다(전망 입력을 넣기 전 비교). 도구는 Python·scikit-learn(무료).", options: {} }],
    { x: 0.7, y: 6.1, w: 11.9, h: 0.65, fontSize: 14, lineSpacingMultiple: 1.2 });
  s.addNotes("기상청과 전력통계 API는 자료만 줍니다. 무엇을 입력으로 쓸지, 어떻게 학습하고 시험할지, 확률을 어떻게 단계로 나눌지, 원인을 어떻게 계산할지는 저희가 설계하고 구현했습니다.");
}

// ───────────── 7. 공정한 시험
{
  const s = slide("06  공정한 시험", "미래 자료를 보지 않고, 시간 순서대로만 시험했다");
  // 2023-01 ~ 2026-10 : 46개월
  const x0 = 0.9, x1 = 12.4, m = (y, mo) => x0 + ((y - 2023) * 12 + (mo - 1)) / 46 * (x1 - x0);
  const ty = 2.35;
  [2023, 2024, 2025, 2026].forEach((y) => { line(s, m(y, 1), ty, 0, 2.55, K.line, 0.75); T(s, String(y), { x: m(y, 1) + 0.06, y: ty, w: 1, h: 0.3, fontSize: 12, color: K.mute }); });
  const bars = [
    [2023, 1, 2026, 10, 2.85, "BDB7AA", "학습 자료 — 매달 1일, 그 전날까지 자료로만 다시 학습", K.ink],
    [2025, 1, 2025, 7, 3.55, "8F8A80", "검증 — 설정은 여기서만 정함", "FFFFFF"],
    [2025, 7, 2026, 1, 4.25, K.ink, "시험 — 설정을 정한 뒤 평가", "FFFFFF"],
    [2026, 1, 2026, 11, 4.95, K.sig, "독립 시험 — 시험 계획 먼저 공개", "FFFFFF"],
  ];
  bars.forEach(([y1, m1, y2, m2, y, c, t, tc]) => {
    const xa = m(y1, m1), xb = Math.min(m(y2, m2), x1 + 0.25);
    box(s, xa, y, xb - xa, 0.5, c);
    const inside = xb - xa > 3.2;
    T(s, t, { x: inside ? xa + 0.15 : xa - 4.3, y, w: inside ? xb - xa - 0.2 : 4.15, h: 0.5, fontSize: 13, bold: true, color: inside ? tc : K.ink, valign: "middle", align: inside ? "left" : "right" });
  });
  const checks = [["입력은 전날 17시까지 알 수 있는 값만", "열마다 언제 알 수 있는지 문서로 확인"], ["정답이 입력으로 새는 통로 점검", "원자료에서 다시 계산해 대조, 통로 없음"], ["파일 309개 지문 관리", "자동 검증 675개 통과, 처음부터 다시 돌려 같은 결과"]];
  checks.forEach((c, i) => {
    const x = 0.7 + i * 4.05;
    line(s, x, 5.75, 3.8, 0, K.ink, 1);
    T(s, c[0], { x, y: 5.85, w: 3.8, h: 0.4, fontSize: 14, bold: true });
    T(s, c[1], { x, y: 6.25, w: 3.8, h: 0.4, fontSize: 12, color: K.sub });
  });
  s.addNotes("시간 순서대로만 학습하고 예측했습니다. 설정은 2025년 상반기 검증에서만 정했고, 하반기 시험은 한 번만 봤습니다. 2026년은 결과를 보기 전에 시험 계획을 저장소에 먼저 올렸습니다. 그 계획의 모델 결과도 비교 장에서 함께 보여 드립니다.");
}

// ───────────── 8. 결과 ① 계단
{
  const s = slide("07  검증 결과 1", "위험도가 높다고 한 날일수록,\n실제로 출력제어가 더 많이 일어났다", { th: 1.3, note: "2026년 1~10월 304일. " + ASSUME });
  T(s, "각 위험도로 예보한 날 중 실제로 출력제어가 난 비율 · 2026년 1~10월", { x: 0.7, y: 2.5, w: 8, h: 0.3, fontSize: 13, color: K.mute });
  s.addChart(p.charts.BAR, [{ name: "2026", labels: ["매우 높음", "높음", "주의", "낮음"], values: [67, 26, 12, 5] }], {
    x: 0.55, y: 2.85, w: 7.7, h: 3.85, barDir: "col", barGapWidthPct: 45, chartColors: K.tier,
    showValue: true, dataLabelFormatCode: '0"%"', dataLabelFontSize: 22, dataLabelFontBold: true, dataLabelColor: K.ink, dataLabelFontFace: F,
    catAxisLabelFontFace: F, catAxisLabelFontSize: 15, catAxisLabelColor: K.ink, catAxisLineShow: true,
    valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 80, valAxisMinVal: 0, showLegend: false });
  line(s, 8.75, 2.6, 0, 4.0);
  const rows = [["매우 높음", "86일 중 58일"], ["높음", "42일 중 11일"], ["주의", "69일 중 8일"], ["낮음", "107일 중 5일"]];
  rows.forEach((r, i) => {
    box(s, 9.1, 2.78 + i * 0.55, 0.12, 0.3, K.tier[i]);
    T(s, r[0], { x: 9.35, y: 2.75 + i * 0.55, w: 1.6, h: 0.4, fontSize: 15 });
    T(s, r[1], { x: 10.7, y: 2.75 + i * 0.55, w: 1.93, h: 0.4, fontSize: 15, bold: true, align: "right" });
  });
  line(s, 9.1, 5.05, 3.53, 0);
  T(s, "다른 기간(2025년 하반기)도 같은 계단", { x: 9.1, y: 5.15, w: 3.6, h: 0.35, fontSize: 13, color: K.mute });
  T(s, "70% → 6% → 4% → 0%", { x: 9.1, y: 5.5, w: 3.6, h: 0.45, fontSize: 18, bold: true });
  s.addNotes("가장 중요한 그림입니다. 매우 높음이라고 한 날은 67%가 실제로 출력제어가 났고, 낮음이라고 한 날은 5%뿐이었습니다. 미리 보지 않은 두 기간 모두 같은 계단 모양입니다. 그래서 위험도를 그대로 믿고 계획에 쓸 수 있습니다.");
}

// ───────────── 9. 결과 ② 대표 숫자
{
  const s = slide("08  검증 결과 2", "2026년 출력제어 82일 중 69일을 전날 알렸다", { note: "‘알림’ = 전날 위험도 ‘높음’ 이상. " + ASSUME });
  T(s, "69", { x: 0.6, y: 2.2, w: 3.6, h: 2.2, fontFace: FB, fontSize: 150, color: K.sig });
  T(s, "/ 82일", { x: 3.5, y: 3.45, w: 2.0, h: 0.7, fontSize: 30, bold: true });
  T(s, "출력제어가 난 날 중\n전날 ‘높음’ 이상으로 알린 날", { x: 0.75, y: 4.55, w: 4.5, h: 0.8, fontSize: 15, color: K.sub, lineSpacingMultiple: 1.25 });
  line(s, 5.75, 2.4, 0, 4.1);
  // 분해 막대
  const bx = 6.2, bw = 6.4, sc = bw / 54;
  T(s, "전력거래소 전망이 있던 28일", { x: bx, y: 2.3, w: 6.4, h: 0.35, fontSize: 14, bold: true });
  box(s, bx, 2.72, 28 * sc, 0.42, K.ink);
  T(s, "28일 모두 알림", { x: bx + 28 * sc + 0.15, y: 2.72, w: 3, h: 0.42, fontSize: 14, valign: "middle" });
  T(s, "전망 없이 온 54일", { x: bx, y: 3.45, w: 6.4, h: 0.35, fontSize: 14, bold: true });
  box(s, bx, 3.87, 41 * sc, 0.42, K.sig); box(s, bx + 41 * sc, 3.87, 13 * sc, 0.42, K.line);
  T(s, "41일 알림", { x: bx + 0.12, y: 3.87, w: 2.5, h: 0.42, fontSize: 14, bold: true, color: "FFFFFF", valign: "middle" });
  T(s, "13일 놓침", { x: bx + 41 * sc + 0.08, y: 3.87, w: 1.6, h: 0.42, fontSize: 12, valign: "middle" });
  line(s, bx, 4.75, bw, 0);
  const st = [["88%", "출력제어가 걸린 391시간 중 345시간이\n전날 알린 날에 있었다"], ["59번", "헛경보 (304일 중)\n절반 이상이 6월 14일 이후"]];
  st.forEach((t, i) => {
    const x = bx + i * 3.3;
    T(s, t[0], { x, y: 4.9, w: 3.1, h: 0.75, fontFace: FB, fontSize: 36 });
    T(s, t[1], { x, y: 5.7, w: 3.1, h: 0.8, fontSize: 13, color: K.sub, lineSpacingMultiple: 1.2 });
  });
  s.addNotes("올해 출력제어가 난 82일 중 69일을 전날 알렸습니다. 전력거래소 전망이 있던 28일은 모두 알렸고, 전망이 없던 54일 중 41일을 더 알렸습니다. 시간으로 보면 88%입니다. 헛경보는 59번 있었고 절반 이상이 6월 14일 이후입니다.");
}

// ───────────── 10. 정직한 비교
{
  const s = slide("09  비교", "더 많이 잡는 규칙도 있다. 그래도 모델을 쓰는 이유", { note: "2026년 1~10월. 간단한 규칙 = 봄·가을 + 쉬는 날 + 맑음 예보 + 최근 출력제어(학습 없음). PR-AUC 무작위 기준 0.27." });
  const head = ["", "우리 모델", "간단한 규칙", "전력거래소 전망"];
  const rows = [
    ["출력제어 82일 중 잡은 날", "69일", "73일", "28일"],
    ["헛경보", "59번", "69번", "1번"],
    ["위험한 날을 위로 올리는 능력 (PR-AUC)", "0.73", "0.57", "—"],
    ["확률과 이유를 주는가", "확률 · 4단계 · 원인 3가지", "예 / 아니오만", "공지 문구"],
  ];
  const cx = [0.7, 5.3, 7.75, 10.2], cw = [4.6, 2.45, 2.45, 2.43], y0 = 2.2, rh = 0.78;
  box(s, cx[1], y0 - 0.05, cw[1], rh * 5 + 0.1, "FFFFFF", { line: { color: K.sig, width: 2 } });
  head.forEach((h, j) => T(s, h, { x: cx[j] + 0.15, y: y0, w: cw[j] - 0.3, h: rh, fontSize: 15, bold: true, color: j === 1 ? K.sig : K.mute, valign: "middle", align: j ? "center" : "left" }));
  rows.forEach((r, i) => {
    const y = y0 + rh * (i + 1);
    line(s, 0.7, y, 11.93, 0);
    r.forEach((v, j) => T(s, v, { x: cx[j] + 0.15, y, w: cw[j] - 0.3, h: rh, fontSize: j === 0 ? 15 : (i === 3 ? 13 : 20), bold: j === 1, valign: "middle", align: j ? "center" : "left", color: j === 0 ? K.ink : K.ink }));
  });
  line(s, 0.7, y0 + rh * 5, 11.93, 0);
  T(s, [{ text: "결과를 보기 전에 공개한 계획의 모델  ", options: { bold: true, color: K.sig } }, { text: "70일 중 60일, 헛경보 67번, PR-AUC 0.64 (당시 정답 기준). 전망 입력은 그 뒤에 더했고, 두 결과를 모두 공개한다.", options: {} }],
    { x: 0.7, y: 6.3, w: 11.9, h: 0.45, fontSize: 13 });
  s.addNotes("숨기지 않고 말씀드립니다. 간단한 규칙은 잡은 날이 73일로 저희보다 많습니다. 대신 헛경보가 더 많고, 위험한 날을 위로 올리는 능력이 0.57로 낮습니다. 무엇보다 확률과 이유를 주지 못합니다. 전력거래소 전망은 정확하지만 28일만 다룹니다.");
}

// ───────────── 11. 실시간 예보
{
  const live = [["11/20", "금", "7%", 3], ["11/21", "토", "7%", 3], ["11/22", "일", "35%", 1], ["11/23", "월", "0%", 3], ["11/24", "화", "0%", 3], ["11/25", "수", "2%", 3], ["11/26", "목", "7%", 3]];
  const tierName = ["매우 높음", "높음", "주의", "낮음"];
  const s = slide("10  실시간 예보", "11월 19일부터 매일,\n내일을 실제로 예보하고 있다", { th: 1.3, note: "실제 결과는 전력거래소 게시판에 1일~11주 뒤 올라와, 올라오는 대로 대조한다. 11~2월은 출력제어가 드문 계절이라 ‘낮음’이 많은 것이 정상. 확률은 기록 그대로(1% 단위), 11/25 이전은 보정 곡선 갱신 전 값." });
  const cx = [0.7, 2.3, 3.6, 5.6], y0 = 2.55, rh = 0.5;
  ["예보한 날", "확률", "위험도", "실제"].forEach((h, j) => T(s, h, { x: cx[j], y: y0, w: 1.9, h: 0.4, fontSize: 13, bold: true, color: K.mute }));
  live.forEach((r, i) => {
    const y = y0 + 0.45 + i * rh;
    line(s, 0.7, y, 6.6, 0);
    const hi = r[3] < 2;
    if (hi) box(s, 0.7, y, 6.6, rh, K.sigSoft);
    T(s, `${r[0]} (${r[1]})`, { x: cx[0], y, w: 1.6, h: rh, fontSize: 15, valign: "middle", bold: hi });
    T(s, r[2], { x: cx[1], y, w: 1.2, h: rh, fontSize: 15, valign: "middle", bold: hi });
    box(s, cx[2], y + 0.17, 0.12, 0.16, K.tier[r[3]]);
    T(s, tierName[r[3]], { x: cx[2] + 0.22, y, w: 1.7, h: rh, fontSize: 15, valign: "middle", bold: hi });
    T(s, "게시판 공개 대기", { x: cx[3], y, w: 1.7, h: rh, fontSize: 13, color: K.mute, valign: "middle" });
  });
  line(s, 0.7, y0 + 0.45 + 7 * rh, 6.6, 0);
  line(s, 7.85, 2.55, 0, 3.95);
  T(s, "10월 실적(과거)으로 고정 모델 확인", { x: 8.25, y: 2.5, w: 4.4, h: 0.4, fontSize: 14, bold: true, color: K.sig });
  T(s, [{ text: "12일 중 9일", options: { fontFace: FB, fontSize: 40 } }], { x: 8.25, y: 2.9, w: 4.4, h: 0.85 });
  T(s, "모델을 고정한 11월 12일 뒤 게시판에 올라온 10월 출력제어 12일 중, 전날 알린 날", { x: 8.25, y: 3.8, w: 4.4, h: 0.8, fontSize: 13, color: K.sub, lineSpacingMultiple: 1.2 });
  line(s, 8.25, 4.8, 4.38, 0);
  T(s, "어떻게 도나", { x: 8.25, y: 4.95, w: 4.4, h: 0.35, fontSize: 14, bold: true });
  T(s, "노트북 작업 스케줄러가 매일 17:20에 기상청 17시 예보와 EPSIS 수요를 받아 계산하고 기록을 쌓는다", { x: 8.25, y: 5.3, w: 4.4, h: 0.9, fontSize: 13, color: K.sub, lineSpacingMultiple: 1.2 });
  s.addNotes("과거 재현만이 아니라 지금도 매일 내일을 예보하고 있습니다. 11월 22일 일요일은 높음으로 예보했습니다. 실제 결과는 게시판에 늦게 올라와서 올라오는 대로 맞춰 보겠습니다. 그리고 모델을 고정한 뒤 올라온 10월 실적 12일 중 9일을 전날 알렸습니다. 이제 실제 화면을 보여 드리겠습니다.");
}

// ───────────── 12. 예선 이후
{
  const s = slide("11  예선 이후", "예선 이후 달라진 것");
  const cards = [
    ["대상", "발전사업자 전체 → 지시를 직접 받아 여러 발전소를 운영하는 회사로 좁혀, 모델의 가정에 가장 가까운 사용자로"],
    ["새 정답으로 재확인", "모델을 고정한 11월 12일 뒤 올라온 10월 실적으로 확인 (12일 중 9일). 모든 숫자를 82일 기준으로 갱신"],
    ["실시간 예보 운영", "계산 코드 완성 → 11월 19일부터 매일 자동 실행, 기록 누적"],
    ["시연 화면 완성", "예보문 화면, 지난 2주 그래프, ‘실제 결과 보기’로 예보와 실제를 바로 대조"],
  ];
  cards.forEach((c, i) => {
    const x = 0.7 + (i % 2) * 6.05, y = 2.1 + Math.floor(i / 2) * 2.2;
    line(s, x, y, 5.85, 0, K.ink, 1.25);
    T(s, String(i + 1).padStart(2, "0"), { x, y: y + 0.2, w: 0.7, h: 0.5, fontSize: 22, bold: true, color: K.sig });
    T(s, c[0], { x: x + 0.75, y: y + 0.2, w: 5.0, h: 0.5, fontSize: 20, bold: true });
    T(s, c[1], { x: x + 0.75, y: y + 0.8, w: 5.0, h: 1.2, fontSize: 15, color: K.sub, lineSpacingMultiple: 1.25 });
  });
  s.addNotes("예선 이후에 네 가지가 달라졌습니다. 대상을 좁혔고, 새로 올라온 정답으로 고정한 모델을 다시 확인했고, 실시간 예보를 매일 돌리고 있고, 시연 화면을 완성했습니다.");
}

// ───────────── 13. 한계
{
  const s = slide("12  한계", "가정과 약점을 그대로 밝힌다");
  const rows = [
    ["가정이 필요하다", "전날까지의 출력제어 여부와 전날 전망을 안다고 가정했다", "게시판에 전날까지 올라온 전망만 쓰면 65/82일(헛경보 51번), 두 정보가 없으면 74/82일에 헛경보 94번"],
    ["여름·가을 헛경보", "2026년 헛경보 59번 중 33번이 6월 14일 이후", "단정하지 않고 확률과 4단계로 보여 주고, 최종 판단은 사람이 한다"],
    ["공개되지 않는 원인", "송전망 제약, 원전 정비, 양수·ESS 운전 계획은 공개 자료가 없다", "게시판 제어 사유 대부분이 ‘전력망 제약’ — 이것이 성능의 상한"],
  ];
  const y0 = 2.0, rh = 1.2;
  ["약점", "내용", "어떻게 다루나"].forEach((h, j) => T(s, h, { x: [0.7, 3.6, 7.9][j], y: y0, w: 3, h: 0.35, fontSize: 13, bold: true, color: K.mute }));
  rows.forEach((r, i) => {
    const y = y0 + 0.45 + i * rh;
    line(s, 0.7, y, 11.93, 0, i === 0 ? K.ink : K.line, i === 0 ? 1.25 : 1);
    T(s, r[0], { x: 0.7, y: y + 0.2, w: 2.7, h: 0.8, fontSize: 17, bold: true });
    T(s, r[1], { x: 3.6, y: y + 0.2, w: 4.0, h: 0.9, fontSize: 14, color: K.sub, lineSpacingMultiple: 1.2 });
    T(s, r[2], { x: 7.9, y: y + 0.2, w: 4.7, h: 0.9, fontSize: 14, lineSpacingMultiple: 1.2 });
  });
  box(s, 0.7, 6.15, 11.93, 0.62, K.ink);
  T(s, "다음 단계 — 출력제어 실적과 전망이 당일 공개되면, 누구나 이 수준의 예보를 쓸 수 있다 (정책 제안)", { x: 0.95, y: 6.15, w: 11.5, h: 0.62, fontSize: 15, bold: true, color: "FFFFFF", valign: "middle" });
  s.addNotes("한계도 말씀드립니다. 두 정보를 안다는 가정이 필요하고, 그 정보가 없을 때의 결과도 함께 공개했습니다. 여름·가을에는 헛경보가 많고, 송전망 제약처럼 공개되지 않는 원인은 예측할 수 없습니다.");
}

// ───────────── 14. 팀
{
  const s = slide("13  팀", "각자 만든 부분을 각자 설명합니다");
  const team = [
    ["정대겸", "기획 · 시험 설계 · 발표", "문제 정의, 시험 계획과 결과 해석, 전력거래소 게시판 등록일 확인", "docs/ (시험 계획, 결과, 누설 점검)"],
    ["안성준", "AI 모델 · 공정한 시험", "특징 표, 매달 재학습, 모델 10가지 비교, 확률·4단계·원인 계산", "build_features.py · train.py · compare_models.py · test_2026.py · explain.py · explain_2026.py"],
    ["양성우", "데이터 · 실시간 예보 · 화면", "공개 데이터 8종 정리와 지문 검사, 내일 예보 자동 실행, 시연 화면", "build_clean.py · build_extra.py · build_forecast.py · manifest.py · forecast_tomorrow.py · check_forecast_tomorrow.py · build_demo.py"],
  ];
  team.forEach((t, i) => {
    const x = 0.7 + i * 4.05;
    line(s, x, 2.1, 3.8, 0, K.ink, 1.25);
    T(s, t[0], { x, y: 2.3, w: 3.8, h: 0.6, fontFace: FB, fontSize: 28 });
    T(s, t[1], { x, y: 2.95, w: 3.8, h: 0.4, fontSize: 15, bold: true, color: K.sig });
    T(s, t[2], { x, y: 3.5, w: 3.8, h: 1.3, fontSize: 14, color: K.sub, lineSpacingMultiple: 1.25 });
    box(s, x, 4.85, 3.8, 1.5, K.card);
    T(s, "설명할 코드", { x: x + 0.2, y: 4.95, w: 3.4, h: 0.3, fontSize: 11, bold: true, color: K.mute });
    T(s, t[3], { x: x + 0.2, y: 5.25, w: 3.4, h: 1.05, fontSize: 11.5, lineSpacingMultiple: 1.2 });
  });
  T(s, "정보전기전자공학과 3학년 · 전력공학·제어공학·전력전자·회로이론 수강", { x: 0.7, y: 6.5, w: 11.9, h: 0.35, fontSize: 13, color: K.mute });
}

// ───────────── 15. 도구와 출처
{
  const s = slide("14  도구와 출처", "AI 도구 · 외부 API · 데이터 출처");
  const col = (x, w, head, lines) => {
    line(s, x, 2.0, w, 0, K.ink, 1.25);
    T(s, head, { x, y: 2.15, w, h: 0.4, fontSize: 16, bold: true, color: K.sig });
    T(s, lines.map((t, i) => ({ text: t, options: { breakLine: i < lines.length - 1 } })), { x, y: 2.7, w, h: 3.6, fontSize: 13, color: K.sub, paraSpaceAfter: 9, lineSpacingMultiple: 1.2 });
  };
  col(0.7, 3.75, "생성형 AI (사용 범위)", ["Claude: 데이터 수집·정리, 모델·검증, 시연 화면 코드 작성, 문서와 발표자료 정리", "Gemini: 예선 발표자료 디자인 기획, 문구 정돈", "ChatGPT: 주제 아이디어 탐색, 배경 자료 조사", "코드는 팀원이 검토하고, 각자 맡은 부분을 직접 설명한다"]);
  col(4.8, 3.75, "외부 API (자료만 받음)", ["기상청 단기예보 API (공공데이터포털): 내일 날씨 예보", "전력통계정보시스템(EPSIS): 실시간 전력수요·공급", "예측·판단은 하지 않는다. 판단은 전부 우리가 학습시킨 모델", "모두 무료, 유료 API 없음"]);
  col(8.9, 3.73, "데이터 (공개 자료 8종)", ["한국전력거래소: 시간별 전력수요, 지역별 태양광·풍력 발전량, 설비용량·거래량, 출력제어 실적, 비중앙 출력제어 게시판", "EPSIS 실시간 수급 · 기상청 관측(ASOS)·단기예보 · 관공서 공휴일 규정", "개인정보 없음, 출처·이용 조건은 README에"]);
  box(s, 0.7, 6.25, 11.93, 0.55, K.card);
  T(s, [{ text: "기존 작업  ", options: { bold: true } }, { text: "없음, 이번 대회로 새로 시작        ", options: {} }, { text: "코드·실행 방법  ", options: { bold: true } }, { text: "github.com/eorua/planties", options: {} }],
    { x: 0.95, y: 6.25, w: 11.5, h: 0.55, fontSize: 14, valign: "middle" });
}

p.writeFile({ fileName: require("path").join(__dirname, "../../docs/slides/본선발표.pptx") }).then(() => console.log("ok", page));
