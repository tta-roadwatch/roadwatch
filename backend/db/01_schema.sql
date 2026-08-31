-- ─────────────────────────────────────────────────────────────
-- RoadWatch — 자율주행 취약도로 탐지 서비스
-- 스키마는 TTAK.KO-10.1331-Part4/R1(스마트시티 데이터허브 데이터 모델)의
-- NGSI-LD 정규 표현법과 TrafficEvent 모델 구조를 관계형으로 옮긴 것이다.
-- ─────────────────────────────────────────────────────────────

-- 주행 세션 : 실제 수집일 하나 = 세션 하나.
-- 한 세션에 여러 데이터셋 파일이 딸리므로 파일은 session_files로 분리한다.
CREATE TABLE sessions (
    id                TEXT PRIMARY KEY,          -- 실제 수집일 (2022-05-16)
    actual_start      TIMESTAMPTZ,               -- ss_num(epoch) 또는 colct_dt에서 복원
    actual_end        TIMESTAMPTZ,
    has_ss_num        BOOLEAN NOT NULL DEFAULT FALSE,
    label_date        DATE,                      -- 파일 colct_dt 라벨의 날짜
    label_mismatch    BOOLEAN NOT NULL DEFAULT FALSE,  -- 라벨 연도 ≠ 실제 연도
    available_metrics TEXT[] NOT NULL DEFAULT '{}',    -- 산출 가능한 이벤트 종류
    codebook          TEXT,                      -- 적용한 코드북 (standard | inverted)
    ingested_at       TIMESTAMPTZ DEFAULT now()
);

-- 세션을 구성하는 원본 파일
CREATE TABLE session_files (
    id            BIGSERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    dataset_kind  TEXT NOT NULL,   -- BSM | GPS | STATUS | OBJECT | CONTROL
    source_file   TEXT NOT NULL UNIQUE,
    record_count  INTEGER NOT NULL DEFAULT 0,
    expected_count INTEGER,        -- 계획 §2.1 표의 값. 불일치 시 경고
    label_date    DATE,
    actual_start  TIMESTAMPTZ,
    actual_end    TIMESTAMPTZ,
    has_ss_num    BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_to_db  BOOLEAN NOT NULL DEFAULT FALSE   -- 좌표 보유(BSM·GPS)만 true
);
CREATE INDEX ON session_files (session_id);

-- 정규화된 주행 레코드 (좌표를 가진 BSM·GPS만 적재)
CREATE TABLE driving_records (
    id            BIGSERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    dataset_kind  TEXT NOT NULL,
    vehicle_id    TEXT,                          -- 세션별 타입 상이 → 문자열로 통일
    observed_at   TIMESTAMPTZ,                   -- NGSI-LD observedAt
    obs_second    BIGINT,                        -- epoch 초 (격자 집계의 관측 단위)
    lat           DOUBLE PRECISION,
    lon           DOUBLE PRECISION,
    speed         DOUBLE PRECISION,
    steering      DOUBLE PRECISION,
    accel_lng     DOUBLE PRECISION,
    -- 코드북 적용 후 boolean (원본 코드체계는 세션마다 반대일 수 있다)
    f_manual_emg  BOOLEAN,
    f_auto_emg    BOOLEAN,
    f_sensor_trb  BOOLEAN,
    f_state_abn   BOOLEAN,
    autonomy_raw  SMALLINT,                      -- autonm_flg 원본값 (의미 미확정)
    valid_coord   BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ON driving_records (session_id);
CREATE INDEX ON driving_records (session_id, obs_second);
CREATE INDEX ON driving_records (lat, lon) WHERE valid_coord;

-- 품질검증 결과
CREATE TABLE quality_checks (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    check_name  TEXT NOT NULL,     -- required_fields | coord_range | label_consistency
                                   -- constant_fields | metric_availability
    status      TEXT NOT NULL,     -- pass | warn | excluded
    detail      JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ON quality_checks (session_id);

-- 40m 격자 : ITS 전국표준노드링크로 도로 속성을 채운다
CREATE TABLE grid_cells (
    cell_key    TEXT PRIMARY KEY,          -- "iy:ix" 정수 인덱스
    center_lat  DOUBLE PRECISION NOT NULL,
    center_lon  DOUBLE PRECISION NOT NULL,
    road_name   TEXT,                      -- TrafficEvent.name
    address     TEXT,                      -- TrafficEvent.address
    link_id     TEXT,
    lanes       SMALLINT,
    max_speed   SMALLINT,
    link_dist_m DOUBLE PRECISION           -- 최근접 링크까지 거리 (50m 초과면 도로망 밖)
);

-- 세션 × 격자 관측 : TTAK.KO-10.1331-Part4/R1 7.2.1 VehicleTraffic
CREATE TABLE cell_observations (
    id                BIGSERIAL PRIMARY KEY,
    cell_key          TEXT NOT NULL REFERENCES grid_cells(cell_key) ON DELETE CASCADE,
    session_id        TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    observation_count INTEGER NOT NULL,    -- 관측 단위(초) 수
    event_count       INTEGER NOT NULL,    -- 중복 제거된 이벤트 관측 수
    event_rate        DOUBLE PRECISION NOT NULL,
    event_types       JSONB NOT NULL DEFAULT '{}'::jsonb,
    measurable        BOOLEAN NOT NULL DEFAULT TRUE,  -- 측정 불가 ≠ 이벤트 0%
    UNIQUE (cell_key, session_id)
);

-- 반복성 판정 결과 : 3단계 분류
CREATE TABLE road_issues (
    cell_key       TEXT PRIMARY KEY REFERENCES grid_cells(cell_key) ON DELETE CASCADE,
    classification TEXT NOT NULL,          -- always_manual | intermittent | low
    session_count  SMALLINT NOT NULL,      -- 반복 검출된 세션 수
    min_event_rate DOUBLE PRECISION,
    max_event_rate DOUBLE PRECISION,
    is_candidate   BOOLEAN NOT NULL DEFAULT FALSE,
    decided_at     TIMESTAMPTZ DEFAULT now()
);

-- 현장점검 : 시스템 판정을 사람이 확정·번복하는 지점.
--
-- 상태는 도로관리 업무의 실제 흐름을 따른다. 후보로 올라온 뒤 담당자가
-- 배정되고(scheduled), 현장을 보고(inspecting), 고칠 것이 있으면 조치를
-- 기다렸다가(action_needed), 끝난다(resolved). 현장에서 도로 문제가
-- 아니라고 확인되면 어느 단계에서든 not_applicable 로 빠진다.
CREATE TABLE inspections (
    id           BIGSERIAL PRIMARY KEY,
    cell_key     TEXT NOT NULL REFERENCES grid_cells(cell_key) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'recommended',
    -- recommended | scheduled | inspecting | action_needed | resolved | not_applicable
    findings     TEXT[] NOT NULL DEFAULT '{}',         -- 차선 마모 · 표지판 가림 · 상시 수동 운행 구간 …
    action       TEXT,                                 -- 무엇을 하기로 했는가
    cause        TEXT,                                 -- 현장에서 확인한 원인
    assignee     TEXT,                                 -- 담당자
    scheduled_for DATE,                                -- 점검 예정일
    inspector    TEXT,
    inspected_at TIMESTAMPTZ,
    -- 조치가 끝난 날. 개선 전·후 비교의 기준선이 되므로 날짜만 남긴다.
    completed_on DATE,
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON inspections (cell_key);
CREATE INDEX ON inspections (status);

-- 시민 도로 불편 제보
--
-- 판정에는 쓰지 않는다. 자율주행 데이터가 잡아내지 못하는 현장 사정을
-- 관리자가 점검 우선순위를 정할 때 참고하는 «추가 신호»다. 그래서
-- grid_cells 참조를 강제하지 않는다 — 격자 밖에서도 제보가 들어온다.
--
-- 접수는 인증 없이 연다. 점검 등록은 시스템 판정을 사람이 뒤집는
-- 행정 행위라 인증이 필요하지만, 민원 접수는 판정을 바꾸지 않고
-- 참고 자료로만 쌓이므로 공공 민원 창구처럼 열어두는 편이 맞다.
CREATE TABLE citizen_reports (
    id          BIGSERIAL PRIMARY KEY,
    cell_key    TEXT REFERENCES grid_cells(cell_key) ON DELETE SET NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    category    TEXT NOT NULL,        -- 차선 안 보임 · 공사 차선 변경 · 노면 파임 · 표지판 가림 · 기타
    note        TEXT,                 -- 시민이 덧붙인 한 줄
    status      TEXT NOT NULL DEFAULT 'received',   -- received | reviewing | reflected | closed
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON citizen_reports (cell_key);
CREATE INDEX ON citizen_reports (created_at DESC);

-- 사용자 : 도로관리 담당자.
-- 조회는 공개 데이터라 인증 없이 열어두고, 현장점검 등록(쓰기)에만 인증을 건다.
-- 실제 운영이라면 지자체 SSO 와 연동할 자리다.
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,             -- PBKDF2-HMAC-SHA256 (salt 포함)
    display_name  TEXT,
    organization  TEXT,
    role          TEXT NOT NULL DEFAULT 'inspector',  -- inspector | admin
    is_demo       BOOLEAN NOT NULL DEFAULT FALSE,     -- 테스트 로그인 대상 계정
    created_at    TIMESTAMPTZ DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
CREATE INDEX ON users (username);

-- 정규화 대비 지점 — 데모 하이라이트(SCR-03)를 지도에 얹기 위한 표.
-- 같은 BSM 레코드를 두 가지로 판정한 결과를 좌표와 함께 담는다.
--   raw_emergency        표준 체계를 전 세션에 그대로 적용 (정규화 안 함)
--   normalized_emergency 세션별 코드북 적용 (정규화)
-- 전자는 15,588건, 후자는 3건이다. 화면 토글이 이 차이를 지도로 보여준다.
CREATE TABLE normalization_points (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    codebook    TEXT NOT NULL,
    raw_emergency        BOOLEAN NOT NULL,
    normalized_emergency BOOLEAN NOT NULL,
    flags       TEXT[] NOT NULL DEFAULT '{}'   -- 어떤 플래그가 걸렸는지
);
CREATE INDEX ON normalization_points (session_id);
CREATE INDEX ON normalization_points (raw_emergency, normalized_emergency);

-- 주행 궤적 — 초당 대표 위치. 격자가 아니라 실제로 지나간 경로를 그린다.
-- GPS는 100Hz라 전량은 과하고, 초당 1점이면 지도에서 충분히 매끄럽다.
CREATE TABLE trajectories (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    obs_second  BIGINT NOT NULL,
    observed_at TIMESTAMPTZ,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    UNIQUE (session_id, obs_second)
);
CREATE INDEX ON trajectories (session_id, obs_second);
