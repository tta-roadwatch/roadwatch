/** API 호출. 오류 형식과 cell_key 인코딩을 여기서 한 번만 처리한다. */

import type {
  AuthConfig,
  AuthUser,
  Cell,
  CellDetail,
  CellFeatureCollection,
  CellReports,
  CitizenReport,
  Comparison,
  Dashboard,
  DatasetMeta,
  FindingOptions,
  Inspection,
  InspectionCreate,
  InspectionStatus,
  LoginResponse,
  MapBounds,
  Normalization,
  NormalizationPointCollection,
  Quality,
  Report,
  RoadLinkCollection,
  Standards,
  TrajectoryCollection,
  Workbox,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(
  /\/+$/,
  "",
);

/** 쓰기 경로에 붙일 토큰. 조회는 인증 없이 열려 있어 토큰이 없어도 동작한다.
 *
 * 모듈 변수로 두는 이유는 client 가 auth 를 import 하면 순환 참조가 되기
 * 때문이다. 인증 상태를 가진 쪽이 여기에 밀어 넣는다.
 */
let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

/** 토큰이 만료·무효일 때 로그아웃시키기 위한 통로 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    // 네트워크 자체가 실패한 경우 — API 컨테이너가 아직 안 떴을 수 있다
    throw new ApiError(0, "API 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }

  if (!res.ok) {
    // 토큰이 만료됐거나 틀린 경우. 로그인 상태를 정리해 다시 로그인하게 한다.
    if (res.status === 401) onUnauthorized?.();

    // 오류 응답은 Part3 5장 형식(application/problem+json)이다
    let detail = `요청이 실패했습니다 (HTTP ${res.status})`;
    try {
      const body = await res.json();
      detail = body?.detail || body?.title || detail;
    } catch {
      /* 본문이 JSON 이 아니면 기본 문구를 쓴다 */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** cell_key 는 "21:4" 처럼 콜론이 들어가므로 반드시 인코딩해야 한다. */
const key = (cellKey: string) => encodeURIComponent(cellKey);

export const api = {
  dashboard: () => request<Dashboard>("/api/dashboard"),

  normalization: () => request<Normalization>("/api/normalization"),

  quality: () => request<Quality>("/api/quality"),

  cells: (candidatesOnly = false) =>
    request<Cell[]>(`/api/cells${candidatesOnly ? "?candidates_only=true" : ""}`),

  cell: (cellKey: string) => request<CellDetail>(`/api/cells/${key(cellKey)}`),

  comparison: (cellKey: string) =>
    request<Comparison>(`/api/cells/${key(cellKey)}/comparison`),

  report: (cellKey: string) =>
    request<Report>(`/api/cells/${key(cellKey)}/report`, { method: "POST" }),

  inspections: (params?: { status?: InspectionStatus; cell_key?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.cell_key) q.set("cell_key", params.cell_key);
    const qs = q.toString();
    return request<Inspection[]>(`/api/inspections${qs ? `?${qs}` : ""}`);
  },

  /** 점검 결과 선택지는 서버가 준다. 화면에 하드코딩하지 않는다. */
  findingOptions: () => request<FindingOptions>("/api/inspections/findings"),

  /** 업무함 — 상태별 건수와 오늘 할 일 */
  workbox: () => request<Workbox>("/api/inspections/workbox"),

  /** 시민 제보 항목도 서버가 준다 */
  reportCategories: () =>
    request<{ categories: string[] }>("/api/reports/categories"),

  cellReports: (cellKey: string) =>
    request<CellReports>(`/api/cells/${key(cellKey)}/reports`),

  citizenReports: (params?: { cell_key?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.cell_key) q.set("cell_key", params.cell_key);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<{ reports: CitizenReport[]; total: number; notice: string }>(
      `/api/reports${qs ? `?${qs}` : ""}`,
    );
  },

  /** 제보 접수는 인증이 필요 없다 — 판정을 바꾸지 않는 민원 창구다. */
  createReport: (body: {
    lat: number;
    lon: number;
    category: string;
    note?: string | null;
  }) =>
    request<CitizenReport>("/api/reports", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createInspection: (body: InspectionCreate) =>
    request<Inspection>("/api/inspections", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateInspection: (
    id: number,
    body: Partial<
      Pick<
        Inspection,
        | "status" | "findings" | "action" | "cause"
        | "assignee" | "scheduled_for" | "completed_on"
      >
    >,
  ) =>
    request<Inspection>(`/api/inspections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  datasets: () => request<DatasetMeta[]>("/ngsi-ld/v1/datasets"),

  standards: () => request<Standards>("/api/standards"),

  // ── 인증 ───────────────────────────────────────────────────
  // 조회는 열려 있고 현장점검 등록만 로그인이 필요하다.

  login: (username: string, password: string) =>
    request<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  /** 데모 계정으로 정상 발급받는다. 인증을 건너뛰는 우회 경로가 아니다. */
  demoLogin: () =>
    request<LoginResponse>("/api/auth/demo-login", { method: "POST" }),

  me: () => request<AuthUser>("/api/auth/me"),

  authConfig: () => request<AuthConfig>("/api/auth/config"),

  /** SCR-09 — 표준 준수 근거를 화면에서 눌러 확인할 수 있게 원문 그대로 받는다 */
  raw: (path: string) => request<unknown>(path),

  // ── 지도 레이어 ────────────────────────────────────────────
  // 격자 경계와 초기 뷰포트는 서버가 계산해 준다. 격자 규약(DLAT/DLON/LAT0)은
  // 캘리브레이션으로 정한 분석 규약이라 화면이 알 일이 아니고, 판교 좌표도
  // 하드코딩하지 않는다.

  geoCells: (candidatesOnly = false) =>
    request<CellFeatureCollection>(
      `/api/geo/cells${candidatesOnly ? "?candidates_only=true" : ""}`,
    ),

  geoRoadLinks: (namedOnly = true) =>
    request<RoadLinkCollection>(
      `/api/geo/roadlinks${namedOnly ? "?named_only=true" : ""}`,
    ),

  geoBounds: () => request<MapBounds>("/api/geo/bounds"),

  /**
   * SCR-03 — 정규화 전·후 비상정지 지점.
   * normalized=false 면 지도가 15,124개 마커로 뒤덮이고, true 면 3개만 남는다.
   */
  geoNormalization: (normalized: boolean) =>
    request<NormalizationPointCollection>(
      `/api/geo/normalization${normalized ? "?normalized=true" : ""}`,
    ),

  geoTrajectories: (sessionId?: string) =>
    request<TrajectoryCollection>(
      `/api/geo/trajectories${
        sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""
      }`,
    ),

  /** SCR-09 — 표준 응답을 화면에서 그대로 보여주기 위한 원문 조회 */
  entities: (opts?: { keyValues?: boolean; limit?: number }) => {
    const q = new URLSearchParams({ type: "TrafficEvent" });
    if (opts?.keyValues) q.set("options", "keyValues");
    if (opts?.limit) q.set("limit", String(opts.limit));
    return request<unknown[]>(`/ngsi-ld/v1/entities?${q}`);
  },

  entity: (urn: string) =>
    request<unknown>(`/ngsi-ld/v1/entities/${encodeURIComponent(urn)}`),

  context: () => request<unknown>("/ngsi-ld/v1/context.jsonld"),
};

export { BASE as API_BASE };
