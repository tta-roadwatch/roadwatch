/** API 호출. 오류 형식과 cell_key 인코딩을 여기서 한 번만 처리한다. */

import type {
  Cell,
  CellDetail,
  Comparison,
  Dashboard,
  DatasetMeta,
  FindingOptions,
  Inspection,
  InspectionCreate,
  InspectionStatus,
  Normalization,
  Quality,
  Report,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(
  /\/+$/,
  "",
);

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
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // 네트워크 자체가 실패한 경우 — API 컨테이너가 아직 안 떴을 수 있다
    throw new ApiError(0, "API 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }

  if (!res.ok) {
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

  createInspection: (body: InspectionCreate) =>
    request<Inspection>("/api/inspections", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateInspection: (
    id: number,
    body: Partial<Pick<Inspection, "status" | "findings" | "action" | "inspector">>,
  ) =>
    request<Inspection>(`/api/inspections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  datasets: () => request<DatasetMeta[]>("/ngsi-ld/v1/datasets"),

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
