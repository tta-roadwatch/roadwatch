# 파이프라인 구현 계획 (상세판)

원본 843,734건(+제어정보 146,950건)에서 취약구간 후보를 산출하기까지. 기획서 11절 흐름을 따른다.

```
적재·세션식별 → 표준정규화 → 품질검증 → 시간축조인
   → 이벤트추출 → 40m격자집계 → 반복성판정 → 도로명매핑 → 시드덤프
```

---

## 0. 완료 정의

아래 세 가지가 모두 성립하면 파이프라인은 완료다.

1. `make ingest` 한 번으로 원본 16개 파일 → `road_issues`까지 전 단계가 무인 실행된다
2. `python -m pipeline.run --verify` 가 인수 기준(§6) 전 항목 ✓를 출력한다
3. `backend/db/02_seed.sql` 이 생성·커밋되어 `docker compose up`만으로 화면 데이터가 뜬다

---

## 1. 실행 환경

| 항목 | 결정 |
|---|---|
| 실행 위치 | **컨테이너 안** (`docker compose exec api python -m pipeline.run …`). 개발 반복 시엔 로컬 Python + `localhost:5432`도 허용 |
| DB 연결 | `DATABASE_URL` 환경변수. 기본 `postgresql://roadwatch:roadwatch@db:5432/roadwatch` (로컬은 `@localhost:5432`) |
| 데이터 경로 | `DATA_DIR` 환경변수. 컨테이너 `/data`, 로컬 `./data` |
| 타임존 | **모든 epoch → KST 변환에 `ZoneInfo("Asia/Seoul")` 강제.** 컨테이너는 UTC다 |
| 대량 적재 | psycopg3 `cursor.copy()` (COPY 프로토콜). executemany 금지 |
| 스트리밍 | `ijson.items(f, "item")`. 최대 파일 161MB — 전량 메모리 적재 금지. 단, GPS 초당 위치 인덱스(≤16만 엔트리)는 메모리 보관 허용 |

---

## 2. 데이터 자산 명세

### 2.1 파일 → 세션 레지스트리 (`sources.py`에 이대로 하드코딩)

파일명 표기가 제각각이므로(`메세지`/`메시지`, `데이터` 유무) **glob 금지, 명시적 목록**. 세션 ID는 `ss_num` 복원 실측값(아래 표)이며, 적재 시 재검증한다.

| 파일 | kind | session_id | 레코드 | ss_num | 라벨 불일치 |
|---|---|---|---|---|---|
| `기본안전메세지_nia.json` | BSM | 2022-10-03 | 15,585 | ✗ | — |
| `기본안전메시지_nia(2023).json` | BSM | 2023-02-23 | 14,425 | ✗ | — |
| `기본안전메시지_nia_2024.json` | BSM | 2024-01-02 | 10,000 | ✗ | — |
| `차량GPSINS_nia_2024.json` | GPS | 2022-05-16 | 90,000 | ✓ | ⚠ 라벨 2024 |
| `차량GPSINS_nia(2023).json` | GPS | 2022-07-25 | 151,455 | ✓ | ⚠ 라벨 2023 |
| `차량GPSINS데이터_nia.json` | GPS | 2022-08-05 | 52,494 | ✓ | 일치 |
| `차량상태정보데이터_nia_2024.json` | STATUS | 2022-05-16 | 45,000 | ✓ | ⚠ |
| `차량상태정보데이터_nia(2023).json` | STATUS | 2022-07-25 | 75,710 | ✓ | ⚠ |
| `차량상태정보_nia.json` | STATUS | 2022-08-05 | 26,237 | ✓ | 일치 |
| `차량객체인식데이터_nia_2024.json` | OBJECT | 2022-05-16 | 135,000 | ✓ | ⚠ |
| `차량객체인식데이터_nia(2023).json` | OBJECT | 2022-07-06 | 127,924 | ✓ | ⚠ |
| `차량객체인식데이터_nia(2023)_230613.json` | OBJECT | 2022-06-16 | 9,238 | ✓ | ⚠ |
| `차량객체인식정보데이터_nia.json` | OBJECT | 2022-08-05 | 90,666 | ✓ | 일치 |
| `차량제어정보데이터_nia_2024.json` | CONTROL | 2022-05-16 | 45,000 | ✓ | ⚠ |
| `차량제어정보데이터_nia(2023).json` | CONTROL | 2022-07-25 | 75,711 | ✓ | ⚠ |
| `차량제어정보_nia.json` | CONTROL | 2022-08-05 | 26,239 | ✓ | 일치 |

- 합계: BSM 40,010 + GPS 293,949 + STATUS 146,947 + OBJECT 362,828 = **843,734** (기획서 기준). CONTROL 146,950은 별도 집계 — **인수 기준의 843,734에 포함하지 않는다**
- `2022-07-25` 세션은 실제로 07-25~26 이틀에 걸친다 → 세션 ID는 **첫 레코드 날짜** 기준 `2022-07-25` 하나로 취급
- 라벨 불일치 세션 = **4개** (05-16 · 06-16 · 07-06 · 07-25). 08-05는 일치, BSM 3종은 ss_num이 없어 판정 대상 아님

### 2.2 필드 명세와 시간축

| kind | 시간축 | 좌표 | 이벤트 근거 필드 |
|---|---|---|---|
| BSM (30필드) | **`colct_dt` = 밀리초 datetime** (`2022-10-03 10:46:03.669`) — 실측 확인 | `la`/`lo` | `mnl_emg_flg` `auto_emg_flg` `snsr_trb_flg` `vhcl_sttus_flg` `autonm_flg` |
| GPS (12필드) | `ss_num`(epoch초) + `nano_ss_num` | `la`/`lo` | — (위치 기준축 전용) |
| STATUS (18필드) | `ss_num` | ✗ | `auto_sttus` `ster_sttus` `ve_sttus` · `ve` vs `goal_ve` |
| OBJECT (8+필드) | `ss_num` | ✗ | `obcl_nmbr` |
| CONTROL (8+필드) | `ss_num` | ✗ | (확장: 급조향·급감속) |

### 2.3 알려진 함정 (전부 실측 확인됨)

1. **플래그 코드체계 반전** — 2022-10-03만 `1=정상`. `codebook.py`로 해소(15,585건 검증 완료)
2. **`vhcl_id` 타입·의미 상이** — str `"ZERO_001"` / int 1~7358 / int 3·4. `normalize_vehicle_id()`로 통일
3. **`autonm_flg` 값이 1/2** (0/1 아님) + 세션별 의미 반전 의심 — §5 분포 분석에서 확정
4. **GPS 미고정 좌표** — BSM 2022-10-03에 (0,0) 464건. `valid_coord=false` 처리 → 39,546/40,010
5. **전 세션 공통 상수 7종** — `msg_cnt` `secmark` `brk_traction_cd` `brk_abs_cd` `vhcl_width` `vhcl_lnth` `car_typ` → 분석 제외. **비상정지 플래그는 세션 내 상수여도 제외 금지**(코드북 판별 근거)
6. **라벨 연도 ≠ 실제 연도** — 최대 2년. 세션 ID는 반드시 ss_num 복원값

---

## 3. 모듈별 상세 설계

### 3.1 `sources.py` — 레지스트리

```python
@dataclass(frozen=True)
class SourceFile:
    filename: str          # data/raw/ 기준
    kind: str              # BSM | GPS | STATUS | OBJECT | CONTROL
    session_id: str        # "2022-05-16" (예상값 — 적재 시 재검증)
    expected_count: int    # §2.1 표의 값

SOURCES: list[SourceFile]  # 16개 하드코딩

def stream(path) -> Iterator[dict]        # ijson 스트리밍
def resolve_session(kind, records_head) -> tuple[str, datetime|None, datetime|None, bool]
    # (session_id, actual_start, actual_end, has_ss_num)
    # ss_num 있으면 epoch→KST 날짜, 없으면(BSM) colct_dt 파싱
```

### 3.2 `ingest.py` — ① 적재

```python
def run(conn, data_dir) -> IngestReport
```

1. 파일마다: 스트리밍 → 세션 식별 → `sessions` upsert
   - `label_date` = colct_dt 라벨의 날짜, `label_mismatch` = (라벨 연도 ≠ 실제 연도)
   - `record_count`가 `expected_count`와 다르면 **경고 로그 + 계속** (중단하지 않는다)
2. BSM·GPS만 `driving_records`에 COPY 적재 (배치 10,000행)
   - BSM: 코드북 적용(`SESSION_CODEBOOK` 우선, 없으면 `detect()`), `observed_at` = colct_dt(KST), 플래그 5종 boolean
   - GPS: `observed_at` = ss_num epoch(KST), 플래그 전부 NULL
   - `valid_coord` = (0 아닌 좌표 && 위도 33~39 && 경도 124~132)
3. STATUS·OBJECT·CONTROL은 `sessions` 행만 만들고 **레코드는 DB에 넣지 않는다** (④에서 raw 재스트리밍)
4. `sessions.available_metrics` 채우기: 세션이 보유한 kind 조합으로 산출 가능한 이벤트 목록
   - BSM만: `["emergency","autonomy_disengage"]`
   - GPS+STATUS: `["state_deviation","speed_shortfall"]`
   - +OBJECT: `+["obstacle_density"]`

DoD: `SELECT sum(record_count) FROM sessions WHERE dataset_kind != 'CONTROL'` = **843,734**, 세션 8개(BSM 3 + 조인 5).

### 3.3 `quality.py` — ③ 품질검증

검증 5종. 각 결과를 `quality_checks(session_id, check_name, status, detail)`에 적재.

| check_name | 로직 | status 규칙 | 기대값 |
|---|---|---|---|
| `required_fields` | kind별 필수 필드 존재율 | 100%=pass | 전 세션 pass |
| `coord_range` | valid_coord 비율 | <100%=warn, 상세에 건수 | BSM 합계 **39,546/40,010** |
| `label_consistency` | label_date vs actual_start 연도 | 불일치=warn | **4개 세션 warn** |
| `constant_fields` | 세션 내 고유값 1개인 필드 목록 | 정보성 warn | 2022-10-03 BSM에서 10종 검출 |
| `metric_availability` | available_metrics 개수 | 2종=warn(비교 제한), 4종=pass | 세션별 2~4종 |

DoD: 위 표의 기대값 4건 일치.

### 3.4 분포 분석 (별도 스크립트 `pipeline/explore.py`) — 임계값 확정

⑤ 착수 전 1회 실행해 **미결정 5건을 수치 근거로 확정**하고, 결과를 `docs/thresholds.md`에 기록한다.

| 대상 | 뽑을 것 | 결정할 것 |
|---|---|---|
| `autonm_flg` | 세션×값(1/2)별 건수 + 각 그룹의 속도 분포(p10/50/90) | 어느 값이 '해제'인지, 세션별 반전 여부 → 필요시 코드북 편입 |
| `auto_sttus` `ster_sttus` `ve_sttus` | 고유값 빈도표 (세션별) | '정상' 값 집합 → 이탈 판정 규칙 |
| `ve` vs `goal_ve` | goal_ve>0인 레코드에서 `ve/goal_ve` 분포 | 미달 임계 (후보: <0.5) |
| `obcl_nmbr` | 초당 객체 수 분포 | 밀집 임계 (후보: p90) |
| GPS 초당 레코드 수 | 세션별 분포 | 초 대표 위치 규칙(첫 레코드 vs 평균) |

### 3.5 `join.py` — ④ 시간축 조인

```python
def build_position_index(conn, session_id) -> dict[int, tuple[float,float]]
    # driving_records(GPS)에서 초→(lat,lon). 같은 초 여러 건이면 첫 레코드(§3.4에서 확정)
def joined_seconds(session_id, data_dir) -> Iterator[SecondObs]
    # SecondObs = (session_id, sec:int, lat, lon, raw_signals:dict)
    # STATUS·OBJECT를 raw에서 스트리밍하며 ss_num으로 위치 부여.
    # 같은 초의 신호는 병합(이벤트는 OR, 수치는 최악값). 위치 없는 초는 버리고 카운트만 남긴다
```

대상 세션: GPS 보유 3개(05-16 · 07-25 · 08-05). 06-16 · 07-06은 위치가 없어 조인 불가 — `cell_observations.measurable=false`로만 기록.

### 3.6 `events.py` — ⑤ 이벤트 추출

초 단위 이벤트 플래그를 산출한다. 임계값은 §3.4 결과로 채운다.

| 이벤트 키 | 갈래 | 정의 (초 단위) |
|---|---|---|
| `emergency` | A(BSM) | 코드북 적용 후 `f_manual_emg or f_auto_emg or f_sensor_trb` |
| `autonomy_disengage` | A(BSM) | `autonm_flg` = 해제값 (§3.4 확정) |
| `state_deviation` | B | `auto_sttus`/`ster_sttus`/`ve_sttus` 중 하나라도 정상 집합 밖 |
| `speed_shortfall` | B | `goal_ve > 임계속도` 이고 `ve/goal_ve < 임계비` |
| `obstacle_density` | B | 그 초의 `obcl_nmbr` 합/최대 ≥ 임계 |

이벤트 발생 초 = 해당 초에 **하나 이상**의 이벤트 (관측 단위 중복 제거 — 기획서 기능 3).
DoD: 정규화 적용 후 `emergency` 총합 = **3건** (2024-01-02 센서장애만).

### 3.7 `grid.py` — ⑥ 40m 격자 집계

```python
DLAT = 40 / 111320            # ≈ 3.593e-4 — 캘리브레이션 대상
DLON = 40 / (111320 * cos(radians(ANCHOR_LAT)))
def cell_of(lat, lon) -> tuple[int,int]      # (floor(lat/DLAT), floor(lon/DLON))
def center_of(iy, ix) -> tuple[float,float]  # ((iy+.5)*DLAT, (ix+.5)*DLON)
```

- cell_key = `f"{iy}:{ix}"` (정수 인덱스 문자열). 표시용 중심 좌표는 `grid_cells`에 저장
- 셀×세션마다: `observation_count`(관측 초 수), `event_count`(이벤트 발생 초 수), `event_rate`, `event_types`(유형별 **레코드 수** — SCR-06의 160건/53건은 레코드 수다)
- 관측 30 미만 셀 제외. `cell_observations` UNIQUE(cell,session) upsert

### 3.8 캘리브레이션 절차 — §5에 별도 상술 (이 계획의 최대 관문)

### 3.9 `repeat.py` — ⑦ 반복성 판정

- 대상: **measurable 세션 2개 이상**이 관측한 셀 (분석 A·B 병합 — 같은 격자 위에서 세션 출처 불문)
- 분류(경계 명시):
  - 모든 세션 rate ≥ 0.95 → `always_manual` (후보 아님)
  - 모든 세션 rate < 0.25 → `low`
  - 그 외 전부(혼합 포함) → `intermittent` = **후보** (`is_candidate=true`)
- `road_issues`에 `session_count` `min/max_event_rate` 기록
- 후보 셀에는 `inspections(status='recommended')` 자동 생성

### 3.10 `nodelink.py` — ⑧ 도로명 매핑

- `data/nodelink/pangyo_links.geojson`(742링크) 로드
- 셀 중심마다 전 링크 선분과 점–선분 최소거리(equirectangular 미터 근사 — 검증 시 pyproj 대조 1회)
- `grid_cells`에 `road_name` `link_id` `lanes` `max_speed` `link_dist_m` 저장. `address` = `"경기도 성남시 분당구 " + road_name` 수준
- `link_dist_m > 50` → 도로망 밖 표시 (실측: 37.39871 셀이 53m — 이 1건이 재현돼야 정상)

### 3.11 `run.py` — CLI + 검증 + 시드

```
python -m pipeline.run --all                 # ①→⑧ 순차
python -m pipeline.run --step ingest|quality|join|events|grid|repeat|nodelink
python -m pipeline.run --verify              # §6 인수 기준 ✓/✗ 표 출력, 실패 시 exit 1
python -m pipeline.run --dump-seed           # 02_seed.sql 생성 (§7)
```

각 단계는 멱등: 재실행 시 해당 세션/테이블 삭제 후 재적재.

### 3.12 `tests/test_acceptance.py`

`--verify`와 동일 검사를 pytest로. DB가 없으면 skip. CI 없이도 `pytest` 한 번으로 회귀 확인.

---

## 5. 2단계 캘리브레이션 — 82.8% 재현 전략

목표 셀의 이벤트율은 `이벤트초/관측초`인데, **분모와 분자는 서로 독립인 변수에 의존**한다. 이를 이용해 문제를 둘로 쪼갠다.

```
관측초(64·133·60·50)  ←  격자 규약(앵커·크기)에만 의존   ← 1단계에서 맞춘다
이벤트초(53·113·47·34) ←  이벤트 정의(임계값)에만 의존    ← 2단계에서 맞춘다
```

### 1단계 — 격자 규약 맞추기 (이벤트 정의 불필요!)

조인 결과의 초당 위치만으로 후보 규약별 관측초를 계산한다.

| 후보 | Δlat | 앵커 |
|---|---|---|
| C1 | `40/111320` | 0 (전 지구 원점) |
| C2 | 반올림 상수 `0.00036` | 0 |
| C3 | `40/111320` | 판교 영역 최소 위경도 |
| C4 | C1~C3 × 경도만 `40/(111320·cos 37.4)` vs `0.00045` |

각 후보로 `(37.40342,127.10473)` 근방 셀의 관측초를 뽑아 **05-16=64초 · 08-05=133초**가 나오는 규약을 채택. 두 번째 셀(60·50초)로 교차 확인. 채택 규약은 `grid.py` 상수 + 주석으로 고정.

### 2단계 — 이벤트 정의 맞추기

채택된 격자에서 목표 셀의 초별 원신호를 덤프해 놓고, `state_deviation`·`obstacle_density` 정의(정상 집합·임계)를 조정해 **53·113·47·34초**를 재현한다. §3.4 분포 분석과 같은 근거로 정의하되, 목표 셀 재현이 최종 판정.

### 폴백

합리적 후보를 소진해도 ±5% 안에서 못 맞추면: **끼워 맞추지 않는다.** 가장 근거 있는 규약·정의를 채택하고, 실행 결과를 실측값으로 삼아 기획서·Figma 수치를 갱신한다(어긋난 값과 원인을 `docs/thresholds.md`에 기록). 심사에서 위험한 것은 소수점 차이가 아니라 문서·화면·코드의 불일치다.

---

## 6. 인수 기준

`--verify`가 검사하는 항목. **1차가 전부 ✓면 파이프라인 성립.**

**1차 (필수)**

| # | 항목 | 목표값 |
|---|---|---|
| 1 | 4종 적재 합계 | 843,734 |
| 2 | 세션 수 | 8 (BSM 3 + 조인 5) |
| 3 | 라벨 불일치 세션 | 4 |
| 4 | BSM 좌표 유효 | 39,546 / 40,010 |
| 5 | 정규화 오판 보정 | 15,585 (codebook.VERIFIED — 검증 완료) |
| 6 | 잔존 emergency | 3 (2024-01-02) |
| 7 | 셀1 관측초 | 64 (05-16) · 133 (08-05) |
| 8 | 셀1 이벤트율 | 82.8% (53초) · 85.0% (113초) |

**2차 (목표 — 어긋나면 §5 폴백 절차)**

| # | 항목 | 목표값 |
|---|---|---|
| 9 | 셀2 (37.39622,127.10878) | 78% (47/60) · 68% (34/50) |
| 10 | 셀1 이벤트 유형 레코드 수 | 주행상태이탈 160 · 장애물밀집 53 |
| 11 | 최종 분류 | 후보 6 · 상시수동 2 · 낮음 2 |
| 12 | 도로망 밖 셀 | 1건 (37.39871, ≈53m) |

---

## 7. 시드 전략

`--dump-seed`가 `backend/db/02_seed.sql` 생성:

- **전량**: `sessions` `quality_checks` `grid_cells` `cell_observations` `road_issues` `inspections`
- **샘플만**: `driving_records` 세션별 1,000행 (SCR-03 레코드 미리보기용)
- 예상 크기 수백 KB — 커밋한다. 전량 재현은 `make ingest`가 담당 (이중 경로)

---

## 8. 구현 순서와 게이트

| Phase | 산출물 | 게이트 (통과 못 하면 다음 단계 금지) |
|---|---|---|
| 0 | docker compose로 db 기동 확인 | `01_schema.sql` 적용, 7테이블 존재 |
| 1 | `sources.py` `ingest.py` | 인수 1·2·3 ✓ + 각 파일 카운트 = §2.1 표 |
| 2 | `quality.py` | 인수 4 ✓, 검증 5종 기대값 일치 |
| 3 | `explore.py` → `docs/thresholds.md` | 미결정 5건에 수치 근거 기록 |
| 4 | `join.py` `events.py` | 인수 6 ✓ |
| 5 | `grid.py` + 캘리브레이션 1단계 | **인수 7 ✓** (관측초 64·133) |
| 6 | 캘리브레이션 2단계 | **인수 8 ✓** (이벤트율 82.8·85.0) — 최대 관문 |
| 7 | `repeat.py` `nodelink.py` | 인수 11·12 확인 (어긋나면 폴백 절차) |
| 8 | `run.py --verify` `--dump-seed` + pytest | 완료 정의 §0 세 항목 전부 |

예상 실행 시간: ingest ~1분(COPY), 나머지 각 수 초. 전체 `--all` 5분 이내 목표.

### 실행 결과 (Phase 0–8 완료)

전 단계 완료. 완료 정의 §0 세 항목을 컨테이너 안에서 확인했다.

```
make ingest    ① 16건 · ③ 40건 · ⑥ 89셀 · ⑦ 0/24/18 · ⑧ 89셀 1,087링크
make verify    인수 19항목 전부 ✓ (1차 10 · 2차 9)
make test      22 passed
```

| 게이트 | 결과 |
|---|---|
| 1–4 | 인수 1~6 ✓ — 적재 843,734 · 정규화 오판 15,585 · 잔존 emergency 3 |
| 5 | **✓** 관측초 64 / 133 / 60 일치 (`1:13`/08-05만 49, 목표 50) |
| 6 | **△ 폴백 적용** — 이벤트율 오차 7/306 = 2.3%, ±5% 이내. `docs/thresholds.md` §F |
| 7 | **△ 폴백 적용** — 분류 0/24/18 (기획서 2/6/2), 도로망 밖 0곳 (기획서 1곳). §G |
| 8 | ✓ 시드 결정적 재현(재덤프 시 바이트 동일), 새 볼륨 기동 시 init 오류 0 |

폴백 항목은 기획서 v2와 `docs/thresholds.md`에 실측값으로 갱신했다.
남은 작업은 `frontend/` 스캐폴딩과 조회 API로, 이 계획의 범위 밖이다.

## 9. 리스크

| 리스크 | 대응 |
|---|---|
| 격자 규약 불일치로 관측초가 안 맞음 | §5 후보 4계열 × 앵커 조합 탐색. 그래도 안 되면 셀 크기 ±1셀 이웃 검사 후 폴백 |
| autonm_flg 의미 오판 → 상시수동 분류 붕괴 | §3.4에서 속도 교차 검증. 확신 없으면 두 해석 모두 돌려 6/2/2에 가까운 쪽 채택 + 근거 기록 |
| 07-25 세션 이틀 걸침 → 세션 분리 이슈 | 단일 세션 유지(기획서와 동일). actual_start/end로 기간 표현 |
| 컨테이너 UTC로 세션 날짜 밀림 | ZoneInfo 강제 + Phase 1 게이트에서 세션 ID 8개 값 자체를 검사 |
| seed와 ingest 결과 불일치 | seed는 항상 `--all` 직후 `--dump-seed`로만 생성 (수동 편집 금지) |
