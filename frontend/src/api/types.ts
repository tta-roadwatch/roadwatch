/** API 응답 타입. 실제 응답을 받아 확인한 형태를 그대로 옮긴 것이다. */

import type { Classification } from "../lib/classification";

export type InspectionStatus =
  | "recommended"
  | "inspecting"
  | "resolved"
  | "not_applicable";

/** 분석 갈래. 갈래마다 이벤트 정의가 달라 이벤트율을 직접 비교하면 안 된다. */
export type MetricFamily = "bsm" | "joined";

// ── SCR-01 대시보드 ──────────────────────────────────────────

export interface TopCandidate {
  cell_key: string;
  road_name: string | null;
  session_count: number;
  min_event_rate: number | null;
  max_event_rate: number | null;
}

export interface Dashboard {
  headline: string;
  subtext: string;
  stats: {
    records: number;
    sessions: number;
    cells: number;
    candidates: number;
    pending_inspections: number;
    resolved_inspections: number;
  };
  classification: Record<Classification, number>;
  quality_flag: { label_mismatch_sessions: number; note: string };
  top_candidates: TopCandidate[];
}

// ── SCR-03 표준 정규화 ───────────────────────────────────────

export interface CodebookDef {
  name: string;
  abnormal: Record<string, string[]>;
}

export interface Normalization {
  ingest: {
    by_kind: { kind: string; files: number; records: number }[];
    total: number;
  };
  normalization: {
    source: string;
    without_codebook: number;
    with_codebook: number;
    corrected: number;
    headline: string;
    explanation: string;
    emergency_flags: string[];
    codebooks: Record<string, CodebookDef>;
    session_codebook: Record<string, string>;
    example: {
      session_id: string;
      raw: Record<string, number>;
      raw_note: string;
      normalized: Record<string, unknown>;
    };
  };
  sessions: {
    session_id: string;
    codebook: string;
    inverted: boolean;
    label_date: string | null;
    actual_start: string | null;
    label_mismatch: boolean;
  }[];
  coord_validity: { valid: number; total: number; rate: number };
}

// ── SCR-04 품질검증 ──────────────────────────────────────────

export interface QualityCheck {
  session_id: string;
  check_name: string;
  status: string;
  detail: Record<string, unknown> | null;
}

export interface Quality {
  summary: Record<string, number>;
  total: number;
  checks: QualityCheck[];
}

// ── SCR-05 격자 ──────────────────────────────────────────────

export interface Cell {
  cell_key: string;
  lat: number;
  lon: number;
  road_name: string | null;
  address: string | null;
  link_id: string | null;
  lanes: number | null;
  max_speed: number | null;
  link_dist_m: number | null;
  classification: Classification | null;
  classification_label: string | null;
  session_count: number | null;
  observed_sessions: number;
  min_event_rate: number | null;
  max_event_rate: number | null;
  is_candidate: boolean;
  inspection_status: InspectionStatus | null;
}

// ── SCR-06 구간 상세 ─────────────────────────────────────────

export interface Observation {
  session_id: string;
  observed_at: string | null;
  /** 이 세션이 이 격자를 지나갔는가 */
  observed: boolean;
  /** 지나갔더라도 필요한 데이터셋이 없으면 측정 불가다 — 이벤트 0% 가 아니다 */
  measurable: boolean;
  observation_count: number | null;
  event_count: number | null;
  event_rate: number | null;
  event_types: Record<string, number> | null;
  metric_family: MetricFamily | null;
  metric_family_label: string | null;
  available_metrics: string[];
}

export interface FamilySummary {
  label: string;
  sessions: {
    session_id: string;
    event_rate: number;
    event_count: number;
    observation_count: number;
  }[];
  min_event_rate: number | null;
  max_event_rate: number | null;
}

/** 상세 응답의 격자는 목록 응답과 필드가 다르다. observed_sessions 와
 *  inspection_status 는 목록에만 있고, 상세에서는 observations · inspections
 *  배열에서 직접 세야 한다. */
export type CellDetailCell = Omit<Cell, "observed_sessions" | "inspection_status">;

export interface CellDetail {
  cell: CellDetailCell;
  observations: Observation[];
  inspections: Inspection[];
  /** 갈래별 요약. 화면은 반드시 이 단위로 나눠 보여준다. */
  by_family: Partial<Record<MetricFamily, FamilySummary>>;
  family_notice: string;
}

// ── SCR-07 현장점검 ──────────────────────────────────────────

export interface Inspection {
  id: number;
  cell_key?: string;
  status: InspectionStatus;
  findings: string[];
  action: string | null;
  inspector: string | null;
  inspected_at: string | null;
  created_at: string;
  road_name?: string | null;
  classification?: Classification | null;
}

export interface FindingOptions {
  findings: string[];
  /** 이 항목이 선택되면 사람이 시스템 판정을 번복해 후보에서 내린다 */
  not_a_road_issue: string;
  statuses: InspectionStatus[];
}

export interface InspectionCreate {
  cell_key: string;
  findings: string[];
  action?: string | null;
  inspector?: string | null;
  status?: InspectionStatus;
}

// ── SCR-08 개선 전·후 ────────────────────────────────────────

export interface ComparisonSide {
  session_id: string | null;
  observed_at: string | null;
  event_count: number | null;
  observation_count: number | null;
  event_rate: number | null;
  /** true 면 실측이 아니다. 화면은 반드시 표기해야 한다. */
  simulated: boolean;
}

export interface Comparison {
  cell_key: string;
  road_name: string | null;
  before: ComparisonSide;
  after: ComparisonSide;
  simulation_notice: string;
  history: {
    status: InspectionStatus;
    findings: string[];
    action: string | null;
    at: string | null;
  }[];
  measured_sessions: {
    session_id: string;
    observed_at: string | null;
    event_rate: number | null;
    event_count: number | null;
    observation_count: number | null;
  }[];
}

// ── SCR-06 AI 리포트 ─────────────────────────────────────────

export interface Report {
  cell_key: string;
  road_name: string | null;
  text: string;
  /** 키가 없으면 규칙 기반 템플릿으로 자동 대체된다 */
  generated_by: "claude" | "template";
  model: string | null;
  facts: string;
  disclaimer: string;
}

// ── SCR-02 / SCR-09 표준 ─────────────────────────────────────

export interface DatasetMeta {
  id: string;
  type: string;
  identifier: string;
  title: string;
  description: string;
  publisher: string;
  landingPage: string;
  license: string;
  issued: string | null;
  temporal: { startDate: string | null; endDate: string | null };
  spatial: { placeName: string };
  keyword: string[];
  distribution: { title: string; mediaType: string; accessService: string }[];
  dataQuality: {
    timeSourceRestored: boolean;
    labelDate: string | null;
    labelMismatch: boolean;
    labelMismatchNote: string | null;
    codebook: string | null;
    codebookNote: string | null;
    availableMetrics: string[];
    measurable: boolean;
    measurableNote: string | null;
  };
}

// ── SCR-09 표준 현황 ─────────────────────────────────────────

export type StandardStatus = "implemented" | "partial" | "reference";

export interface StandardRow {
  id: string;
  name: string;
  role: string;
  status: StandardStatus;
  /** 실제 응답을 눌러 확인할 수 있는 경로. 설계 참조 항목은 null 이다. */
  evidence: string | null;
  note: string;
  status_label: string;
}

export interface Standards {
  standards: StandardRow[];
  summary: Record<StandardStatus, number>;
  note: string;
  spatial_note: string;
}

// ── 지도 레이어 (GeoJSON) ────────────────────────────────────

export interface CellFeatureProperties {
  cell_key: string;
  center: [number, number];
  road_name: string | null;
  address: string | null;
  lanes: number | null;
  max_speed: number | null;
  classification: Classification | null;
  session_count: number | null;
  observed_sessions: number;
  min_event_rate: number | null;
  max_event_rate: number | null;
  is_candidate: boolean;
  inspection_status: InspectionStatus | null;
}

export interface CellFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: string;
    geometry: { type: "Polygon"; coordinates: number[][][] };
    properties: CellFeatureProperties;
  }[];
  metadata: { cell_size_m: number; d_lat: number; d_lon: number; count: number };
}

export interface RoadLinkCollection {
  type: "FeatureCollection";
  features: unknown[];
  metadata: { source: string; crs_note: string; count: number };
}

/**
 * SCR-03 데모 하이라이트 — 정규화 전·후 비상정지 지점.
 *
 * 지도에 찍히는 수(mapped_raw)와 실측 오판 수(misjudged_total)가 다르다.
 * 차이는 좌표가 유효하지 않아 표시할 수 없는 레코드다. 화면이 "15,588개
 * 마커"라고 말하면 과장이므로 두 수를 모두 받아 구분해 표기한다.
 */
export interface NormalizationPointCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      session_id: string;
      observed_at: string | null;
      codebook: string;
      flags: string[];
    };
  }[];
  metadata: {
    normalized: boolean;
    mapped: number;
    mapped_raw: number;
    mapped_normalized: number;
    misjudged_total: number;
    not_mappable: number;
    coverage_note: string;
  };
}

/** SCR-05 — 차량이 실제로 지나간 경로. 격자는 분석 단위지 주행이 아니다. */
export interface TrajectoryCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "LineString"; coordinates: [number, number][] };
    properties: { session_id: string; seconds: number };
  }[];
  metadata: { sessions: number; points: number; note: string };
}

export interface MapBounds {
  bbox: [number, number, number, number] | null;
  center: [number, number] | null;
  place_name: string;
}

// ── 인증 ─────────────────────────────────────────────────────

export interface AuthUser {
  username: string;
  display_name: string | null;
  organization: string | null;
  role: string;
  is_demo: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface AuthConfig {
  /** 데모 계정이 없으면 테스트 로그인 버튼을 띄우지 않는다 */
  demo_login_available: boolean;
  demo_username: string | null;
  dev_secret_in_use: boolean;
  notice: string;
}
