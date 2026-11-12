"""실험: 출력제어 이력을 "예보 시점까지 게시판에 올라온 만큼만" 쓰면 나아지는가 (2026-11-12, 결과: docs/MODEL_RESULTS.md 14장).

- 공개된 이력 특징 4개: 등록일이 D-2 이전인 실적 글만으로 센 최근 90일·365일 횟수, 마지막 출력제어 뒤 지난 날, 작년 같은 시기(±15일) 횟수
- "공개된 정답만 학습": 매달 1일에 아직 게시판에 올라오지 않은 기간(마지막으로 공개된 사건일 이후, 최대 80일)은 학습에서 뺀다
- 게시판 이전(2024-09까지) 사건은 관측된 최대 지연 80일 뒤에 알려진 것으로 가정
결론: 채택하지 않음 (엄격하게 하면 이득이 엇갈림). 본 모델은 바꾸지 않았다.

실행: python src/exp_asof_history.py  (약 3분, 파일을 만들지 않고 표만 출력)
"""
import os, json, sys, warnings
warnings.filterwarnings("ignore")
os.environ["PLANTIES_VARIANT"]="public"
import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
import train as T, experiments as E
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","")
df, feats = T.load()
params = json.loads((T.OUT/"metrics.json").read_text(encoding="utf-8"))["chosen_params"]["hgb"]
lag = pd.read_csv(ROOT+"data/manual/kpx_board_result_post_lag.csv").drop_duplicates("event_date").set_index("event_date").post_date
ev = df[df.y==1][["date"]].copy()
ev["known"] = pd.to_datetime(ev.date.map(lag))
ev["e"] = pd.to_datetime(ev.date)
ev.loc[ev.known.isna(),"known"] = ev.e + pd.Timedelta(days=80)   # 게시판 이전: 관측된 최대 지연 80일로 가정
D = pd.to_datetime(df.date)
def hist(d):
    cut = d - pd.Timedelta(days=2)             # 전날 17시 이전에 올라온 글만: 등록일 <= D-2
    k = ev[(ev.known <= cut) & (ev.e < d)]
    age = (d - k.e).dt.days
    ly = ((d - ev.e).dt.days.between(365-15, 365+15) & (ev.known <= cut)).sum()
    return pd.Series({"pub_cnt90": int((age<=90).sum()), "pub_cnt365": int((age<=365).sum()),
                      "pub_days_since": float(min(age.min(),365)) if len(age) else 365.0, "pub_ly31": int(ly)})
H = pd.DataFrame([hist(d) for d in D], index=df.index)
df = pd.concat([df, H], axis=1)
PUB = list(H.columns)
def frontier(m0):
    m0 = pd.Timestamp(m0)
    k = ev[ev.known < m0]
    f = k.e.max() if len(k) else pd.Timestamp("1900-01-01")
    return max(f, m0 - pd.Timedelta(days=80))
def bt(make, cols, a, b, asof):
    out=[]
    for m0 in pd.date_range(a,b,freq="MS"):
        m1=(m0+pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"); s=m0.strftime("%Y-%m-%d")
        trn,tst=df[df.date<s],df[(df.date>=s)&(df.date<=m1)]
        if asof: trn = trn[pd.to_datetime(trn.date) <= frontier(m0)]
        use=[c for c in cols if trn[c].notna().any()]
        out.append(pd.Series(make().fit(trn[use],trn.y).predict_proba(tst[use])[:,1],index=tst.index))
    return pd.concat(out)
def p_at_r(y,s,r=0.8):
    o=np.argsort(-s); cy=np.cumsum(y[o]); k=np.argmax(cy>=np.ceil(r*y.sum())); return cy[k]/(k+1)
def ev_(p,a,b):
    i=df.index[(df.date>=a)&(df.date<=b)]; y=df.y[i].values; s=p[i].values
    return f"PR-AUC {average_precision_score(y,s):.3f}  재현율80% 정밀도 {p_at_r(y,s):.2f}"
n=[c for c in feats if not c.startswith("sol_") and c!="nuc_lag1"]
res={}
for name, cols25, cols26, asof in [("A 지금(이력 없음)", feats, n+E.NEW, False), ("A' 지금+공개된 정답만 학습", feats, n+E.NEW, True),
                                  ("B +공개된 이력", feats+PUB, n+E.NEW+PUB, False), ("C +공개된 이력+공개된 정답만 학습", feats+PUB, n+E.NEW+PUB, True)]:
    p25=bt(lambda:T.make("hgb",**params),cols25,T.OOT_START,"2025-12-31",asof)
    p26=bt(lambda:E.hgb(cols26,False),cols26,"2023-07-01","2026-10-31",asof)
    res[name]=(p25,p26)
    print(name); print("   2025 상반기(검증):",ev_(p25,"2025-01-01","2025-06-30")); print("   2025 하반기(시험):",ev_(p25,"2025-07-01","2025-12-31"))
    print("   2026 1~10월      :",ev_(p26,"2026-01-01","2026-10-31")); print("   2026 1/1~6/13    :",ev_(p26,"2026-01-01","2026-06-13"), flush=True)
print(df[df.date.isin(["2025-05-05","2025-10-12","2026-04-20"])][["date"]+PUB].to_string())
