# RoadWatch — 자율주행 취약도로 탐지 및 도로환경 개선 지원 서비스

판교 제로시티 자율주행 개방데이터를 분석해 **자율주행차가 반복적으로 어려움을 겪는
도로 구간**을 찾아내고, 도로관리자에게 현장점검을 권고하는 서비스입니다.

2026 ICT 표준 챌린지 공모전 출품작.

```
843,734건 적재  →  표준 코드체계 정규화  →  40m 격자 집계  →  세션 교차 반복성 판정
                    (오판 15,585건 보정)                        →  취약구간 24곳
```

---

## 지금 어디까지 되어 있나

| 영역 | 상태 |
|---|---|
| 분석 파이프라인 (①적재 → ⑧도로명 매핑) | **완료 · 검증됨** — 인수 19항목 통과 |
| 데이터베이스 스키마 · 시드 | **완료** — 원본 없이 기동 가능 |
| 조회 API (`backend/app/`) | **완료** — NGSI-LD · Part3 인터페이스 · 인증 · 계약 테스트 39항목 |
| 화면 (`frontend/`) | 작업 중 — KRDS 디자인 토큰 적용 |

**`docker compose up` 으로 `db` 와 `api` 가 뜹니다.** API 문서는
<http://localhost:8000/docs> 입니다. `web` 서비스는 화면 작업이 끝나면 함께 뜹니다.

---

## 실행

원본 데이터(685MB)는 저장소에 없지만, 집계 결과가 시드에 들어 있어 그대로 확인할 수
있습니다.

```bash
cp .env.example .env
docker compose up -d db api
make verify       # 인수 기준 검사
make test         # 회귀 테스트
```

원본 데이터를 직접 넣고 전 과정을 재현하려면 `data/raw/` 에 16개 JSON 을 두고:

```bash
make ingest       # ①→⑨ 전 단계 무인 실행 (약 3분)
make verify       # 이번엔 원본 기준 항목까지 22개 전부 검사
```

### 새 주행 데이터가 공개되면

**파일을 `data/raw/` 에 넣고 `make ingest` 만 하면 됩니다.** 코드를 고칠 필요가
없습니다.

등록되지 않은 파일은 자동으로 인식합니다. 데이터셋 종류는 필드 구성으로
판별하고(BSM 은 `mnl_emg_flg`, GPS 는 `gps_srvc_dvsn_cd`, 상태정보는
`auto_sttus` …), 세션은 파일명이 아니라 `ss_num` 에서 복원한 실제 수집시각으로
정합니다. 코드 체계가 반대인 세션이 또 들어와도 `codebook.detect()` 가
데이터에서 추론하므로 사람이 개입하지 않습니다.

```
data/raw/새파일.json  →  make ingest
    종류 판별 → 세션 복원 → 코드북 추론 → 품질검증 → 격자 → 반복성 → 도로명
```

기존 16개 파일은 명시 목록으로 관리해 **기대 건수까지 대조**합니다. 파일이
잘리거나 바뀌면 경고가 뜹니다. 새 파일은 그 대조를 건너뛰고 적재하며, 자동
인식으로 들어왔다는 사실이 적재 보고에 남습니다. 두 경로가 공존하는 이유는
검증 강도와 확장성을 함께 가져가기 위해서입니다.

> 파일 크기가 개당 최대 154MB(전체 685MB)라 웹 업로드는 두지 않았습니다.
> 공간데이터마켓에서 받아 서버에 두고 배치를 도는 것이 실제 운영 흐름입니다.

`make verify` 는 DB 상태를 감지합니다. 시드만 있는 경우 원본 레코드를 세는 3개
항목을 자동으로 건너뛰므로, 원본 없이도 그대로 돌아갑니다.

| 명령 | 설명 |
|---|---|
| `make up` | 전체 기동 |
| `make ingest` | 원본에서 파이프라인 전체 재실행 |
| `make verify` | 인수 기준 검사 (실패 시 종료코드 1) |
| `make test` | 회귀 테스트 |
| `make seed` | 현재 DB 를 `02_seed.sql` 로 덤프 |
| `make reset` | DB 볼륨까지 초기화 |

---

## 검증 결과

```
$ make verify
✓ 4종 적재 합계        843,734    ✓ 이벤트초 21:4/05-16      52
✓ 세션 수                    8    ✓ 이벤트초 21:4/08-05     116
✓ 라벨 불일치 세션            4    ✓ 이벤트초 1:13/05-16      47
✓ BSM 좌표 유효         39,546    ✓ 이벤트초 1:13/08-05      37
✓ BSM 전체              40,010    ✓ 취약구간 후보            24
✓ 정규화 오판 보정      15,585    ✓ 낮음                     18
✓ 잔존 emergency             3    ✓ 도로망 밖(>50m)           0
✓ 관측초 21:4/05-16         64    ✓ 링크 매핑된 셀           89
✓ 관측초 21:4/08-05        133    ✓ 도로명 있는 셀           76
✓ 관측초 1:13/05-16         60
                                   1차 인수 기준 전부 통과
```

**핵심 결과** — 약 3개월 간격의 두 독립 주행에서 같은 격자(대왕판교로, 3차로,
제한속도 60km/h)가 **81.3% 와 87.2%** 의 이상 이벤트율로 재현되었습니다.

---

## 표준 적용 현황

과장 없이 적습니다. 코드에 실제로 구현된 것과 설계 근거로만 참조한 것을 구분합니다.

| 표준 | 적용 |
|---|---|
| **TTAK.KO-10.1331-Part4/R1** (데이터 모델) | 스키마가 `TrafficEvent` 구조를 관계형으로 이식하고, API 가 **NGSI-LD 정규 표현법으로 직렬화**합니다 (`app/ngsild.py`). 속성마다 `Property`/`GeoProperty`/`Relationship` 을 밝히고 `observedAt` 을 싣습니다 |
| **세션별 코드체계 정규화** | 구현·검증 완료. 같은 표준 필드인데 세션마다 코드가 반대여서, 정규화 없이는 15,585건이 오판됩니다. 이 프로젝트에서 표준이 결과를 바꾸는 지점 |
| **TTAK.KO-10.1331-Part3** (인터페이스) | **구현 완료.** 6.1 데이터 인터페이스 · 6.2 데이터셋 인터페이스 · 5장 응답 코드 체계(ProblemDetails). `/ngsi-ld/v1/*` |
| **TTAK.KO-10.1398** (데이터셋 메타데이터) | **구현 완료.** 8개 주행 세션을 DCAT 기반 데이터세트로 등록. 라벨 연도 불일치·측정 가능 지표 같은 실측 품질 문제를 메타데이터로 드러냅니다 |
| **TTAK.KO-06.0580** (V2N) | BSM 원본 필드를 실제로 파싱. 메시지 규격 자체의 구현은 없음 |

### 실제 응답

`GET /ngsi-ld/v1/entities/urn:ngsi-ld:TrafficEvent:roadwatch:21:4`

```json
{
  "id": "urn:ngsi-ld:TrafficEvent:roadwatch:21:4",
  "type": "TrafficEvent",
  "name":     { "type": "Property", "value": "대왕판교로" },
  "address":  { "type": "Property", "value": "경기도 성남시 분당구 대왕판교로" },
  "location": { "type": "GeoProperty",
                "value": { "type": "Point", "coordinates": [127.1047865, 37.4035015] } },
  "category":     { "type": "Property", "value": "roadCondition" },
  "subCategory":  { "type": "Property", "value": "intermittent" },
  "minEventRate": { "type": "Property", "value": 0.0 },
  "maxEventRate": { "type": "Property", "value": 1.0 },
  "sessionCount": { "type": "Property", "value": 6 },
  "laneCount":    { "type": "Property", "value": 3 },
  "maximumAllowedSpeed": { "type": "Property", "value": 60, "unitCode": "KMH" },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://localhost:8000/ngsi-ld/v1/context.jsonld"
  ]
}
```

`severity` 를 싣지 않고 `category` 를 `roadCondition` 으로 고정한 것은 의도한
선택입니다. 이 서비스는 원인을 단정하지 않으므로 위험도를 매기지 않고 관측된
이벤트율만 제공합니다. 확정은 도로관리자의 현장점검이 합니다.

단수 `eventRate` 도 쓰지 않습니다. 한 구간이 여러 세션에서 관측되고 분석 갈래마다
이벤트 정의가 달라, 최댓값 하나를 "이 구간의 이벤트율"이라 부르면 81.3~87.2% 인
구간이 100% 로 읽힙니다.

주요 경로:

| 경로 | 내용 |
|---|---|
| `GET /ngsi-ld/v1/entities?type=TrafficEvent` | 취약구간 (`options=keyValues` 로 축약형) |
| `GET /ngsi-ld/v1/entities?type=VehicleTraffic` | 세션×격자 관측 — 이벤트율의 근거 |
| `GET /ngsi-ld/v1/datasets` | 데이터세트 메타데이터 8건 |
| `GET /ngsi-ld/v1/context.jsonld` | 확장 컨텍스트 |
| `GET /api/dashboard` · `/api/cells` · `/api/cells/{key}` | 화면용 집계 |
| `GET /api/geo/cells` · `/api/geo/roadlinks` | 지도 레이어 (GeoJSON) |
| `POST /api/auth/login` · `/api/auth/demo-login` | 로그인 |
| `POST /api/inspections` | 현장점검 등록 — 유일한 쓰기 경로 (인증 필요) |
| `POST /api/cells/{key}/report` | AI 점검 리포트 초안 |

전체 목록은 <http://localhost:8000/docs> 에 있습니다.

### 인증

**조회는 인증 없이 열려 있고, 현장점검 등록만 로그인이 필요합니다.**

다루는 데이터가 전부 무료 개방데이터이므로 도로가 어디서 어려운지는 누구나 볼 수
있어야 합니다. 반대로 현장점검 등록은 시스템 판정을 사람이 확정하거나 번복하는
지점이라, 누가 뒤집었는지가 기록으로 남아야 의미가 있습니다. 그래서 `inspector`
필드는 요청 본문이 아니라 **토큰에서 채웁니다.**

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/demo-login | jq -r .access_token)
curl -X POST localhost:8000/api/inspections \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"cell_key":"21:4","findings":["차선 마모"],"action":"재도색 요청"}'
```

| 계정 | 비밀번호 | 용도 |
|---|---|---|
| `demo` | `roadwatch2026` | 화면의 `테스트 로그인` 버튼 |
| `admin` | `roadwatch2026!` | 관리자 |

`테스트 로그인`은 인증을 건너뛰는 게 아니라 데모 계정으로 정상 발급받습니다.
권한도 일반 사용자와 같습니다.

비밀번호는 PBKDF2-HMAC-SHA256(20만 회)으로 해싱하고, 토큰은 JWT(HS256)입니다.
`JWT_SECRET` 을 설정하지 않으면 공개된 개발용 기본값을 쓰며,
`GET /api/auth/config` 가 그 사실을 숨기지 않고 알려줍니다. **운영 배포 시에는
반드시 바꿔야 합니다.**

---

## 구조

```
backend/
├── db/01_schema.sql        8테이블 · TrafficEvent 관계형 이식
├── db/02_seed.sql          생성물 · 결정적 재현
├── pipeline/               ①→⑧ 14모듈
│   ├── sources.py          16파일 레지스트리 · 시간축 복원
│   ├── codebook.py         세션별 코드 체계 정규화
│   ├── ingest.py           ① 적재 · 세션 식별
│   ├── quality.py          ③ 품질검증 5종
│   ├── join.py events.py   ④ 초 단위 조인 · ⑤ 이벤트 추출
│   ├── grid.py             ⑥ 40m 격자 집계
│   ├── repeat.py           ⑦ 반복성 3단계 분류
│   ├── nodelink.py         ⑧ 도로명 매핑
│   └── run.py              CLI · 인수검증 · 시드덤프
├── tests/                  인수 기준 19항목 + API 계약 39항목
└── app/                    조회 API
    ├── ngsild.py           NGSI-LD 정규 표현법 직렬화
    ├── errors.py           Part3 5장 응답 코드 체계
    ├── auth.py             로그인 · 토큰 · 비밀번호 해싱
    └── routers/            entities · datasets · screens · geo ·
                            inspections · report · standards · auth

data/nodelink/              ITS 전국표준노드링크 판교 추출본 1,087링크
docs/thresholds.md          임계값 결정 기록 A~G — 왜 그 숫자인지
docs/pipeline-plan.md       8단계 계획과 실행 결과
```

**임계값이 왜 그 값인지 궁금하면 [`docs/thresholds.md`](docs/thresholds.md) 를 보세요.**
격자 규약과 이벤트 정의를 어떻게 좁혀갔는지, 무엇을 시도했다 버렸는지(과적합이라
버린 앵커 미세조정 포함) 전 과정이 남아 있습니다.

---

## 데이터 출처

- 판교 제로시티 자율주행 데이터 — [공간정보 오픈플랫폼 공간데이터마켓](https://data.nsdi.go.kr)
- 전국표준노드링크 (2026-08-12판) — [국가교통정보센터](https://www.its.go.kr)

둘 다 무료 개방데이터입니다. 센서를 새로 설치하지 않으므로 도입 비용이 없습니다.
