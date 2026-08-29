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

export interface CellDetail {
  cell: Cell & { session_count: number | null };
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
