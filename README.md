# 재생에너지 출력제어 예보 AI

**팀 플랜티즈(Planties)** · 2026 안양대학교 AI+X 경진대회 출품작

내일 육지(제주 제외)에서 태양광·풍력 출력제어가 일어날지 **전날 미리 예측**하고, 그 이유와 대응을 설명한다.

- 시연 방식: 2025년의 실제 날짜를 골라 "그 전날 17시에 알 수 있던 정보만으로" 예측을 재현한다.
- 정답 자료: 전력거래소 출력제어 실적 (육지 출력제어 발생일 2023년 2일 → 2024년 27일 → 2025년 82일)

현재 결과: 2025년 하반기 시험에서 출력제어 27일 중 25일을 전날 예측, 놓침 2일, 헛경보 31번, 경보 정확도 45% (PR-AUC 0.78) → [docs/MODEL_RESULTS.md](docs/MODEL_RESULTS.md) · 답을 미리 본 입력이 없는지 점검한 결과는 [docs/LEAKAGE_AUDIT.md](docs/LEAKAGE_AUDIT.md)

처음 보는 팀원은 **[인수인계 문서(docs/HANDOVER.md)](docs/HANDOVER.md)**부터 읽는다. 어떤 자료가 있고 없는지는 [자료 현황(docs/DATA_STATUS.md)](docs/DATA_STATUS.md).

## 폴더

```
data/raw/            원본 (읽기 전용, 받은 이름 그대로)
  kpx_*              전력거래소: 수요, 태양광·풍력, 연료원, 출력제어 실적, 게시판 공지
  epsis/             전력통계정보시스템 실시간 전력수급 (5분 단위, 2022-12 ~ 2026-11)
  kma_asos/          기상청 종관기상관측 시간자료
  kma_forecast/zips/ 기상청 단기예보 과거 발표분 (5개 지역 × 3개 요소 × 2023~2025)
data/clean/          정리본 (형식만 통일, 값은 그대로)  ← src/build_*.py가 만듦
data/manual/         손으로 입력한 자료 (공휴일, 출처 열 포함)
data/features/       학습용 특징 표 (날짜마다 1행, 설명은 FEATURES.md)
data/MANIFEST.csv    raw·clean·manual 파일 지문(SHA-256)
data/DATA_DICTIONARY.md  열의 뜻·단위·시간 기준·알려진 결함
docs/templates/      대회 발표 템플릿
src/                 처리·학습 코드
outputs/             그래프·표 (코드로만 생성)
```

## 다시 만들기

Python 3.11 이상. `pip install -r requirements.txt` (pandas, numpy, scikit-learn, matplotlib). 그래프 한글 글꼴은 Noto Sans CJK KR.

```bash
python src/build_clean.py      # 전력·기상 관측 raw → clean (검증 17개)
python src/build_forecast.py   # 기상 예보 raw → clean (검증 489개)
python src/build_extra.py      # EPSIS 실시간 수급(시간별), 게시판(날짜별) 정리본
python src/build_features.py   # clean → 특징 표 (data/features)
python src/train.py            # 모델 평가·학습 곡선·그래프 (outputs/, 약 1분 40초)
python src/test_2026.py        # 2026년 독립 시험 (계획: docs/TEST_2026_PLAN.md, 2026년 예보를 받은 뒤 실행)
python src/manifest.py write   # 지문 기록 (build 직후에만)
python src/manifest.py verify  # 쓰기 전 매번 확인 → "문제 0개"
```

## 데이터 다루는 규칙

| 누가 | 무엇을 쓰나 | 규칙 |
| --- | --- | --- |
| 모델 학습 | data/features | 전날(D-1) 17시까지 알 수 있는 열만 입력. 학습/시험 기간은 코드에 고정하고, 시험 결과를 본 뒤 설정을 바꾸지 않음 |
| 그래프 | data/clean, data/features | 코드로만 그림. 엑셀에서 손으로 숫자를 고치지 않음 |
| 발표자료 | outputs/ | 숫자는 한 파일에서만 가져오고 단위·출처·기간을 각주로 단다 |
| AI 설명 | 모델 출력 + features | 계산된 값만 인용하고, 원인은 "가능성"으로 표현 |

원본은 고치지 않는다. 바꿀 것이 있으면 코드를 고치고 다시 실행한 뒤 CHANGELOG.md에 적는다.

## 데이터 출처와 이용 조건

모두 공공 자료이며, 출처 표시 조건으로 이용한다.

- 공공데이터포털 · 한국전력거래소: 시간별 전국 전력수요량, 지역별 시간별 태양광 및 풍력 발전량, 연료원별 시간대별 설비용량 및 전력거래량, 전국 태양광 풍력 제어횟수 및 제주 풍력 제어량
- 기상청 기상자료개방포털: 종관기상관측(ASOS) 시간자료, 단기예보 과거 자료
- 전력통계정보시스템(EPSIS): 실시간 전력수급 (5분 단위)
- 한국전력거래소 비중앙 출력제어 정보 게시판 (https://kpx.or.kr/menu.es?mid=a10109050000)
- 공휴일: 관공서의 공휴일에 관한 규정 및 정부 발표 (data/manual/holidays_kr.csv에 날짜별 출처)

자세한 내용과 알려진 결함은 [data/DATA_DICTIONARY.md](data/DATA_DICTIONARY.md) 참고.

## 한계

전력망(송전선) 제약, 원전 정비 일정, 양수·ESS 운전 계획은 공개 자료가 없어 입력에 넣지 못했다. 출력제어 사유 중 "전력망 제약"이 많아, 이 부분이 예측 성능의 상한을 정한다.
