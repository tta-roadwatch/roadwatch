import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type {
  Cell,
  FindingOptions,
  Inspection,
  InspectionStatus,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { ClassBadge, StatusBadge, STATUS_LABEL } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { Empty, ErrorState, Loading } from "../components/States";
import { coord, day } from "../lib/format";

/** 업무 흐름 순서. 서버의 WORKFLOW 와 같은 차례여야 대시보드 업무함에서
 *  넘어왔을 때 같은 순서로 보인다. 상태를 늘리면 여기도 함께 늘린다 —
 *  빠뜨리면 그 상태의 칩이 사라지고 건수도 세지 않는다. */
const STATUS_ORDER: InspectionStatus[] = [
  "recommended",
  "scheduled",
  "inspecting",
  "action_needed",
  "resolved",
  "not_applicable",
];

function asStatus(v: string | null): InspectionStatus | null {
  return v && (STATUS_ORDER as string[]).includes(v)
    ? (v as InspectionStatus)
    : null;
}

interface Bundle {
  inspections: Inspection[];
  options: FindingOptions;
  cells: Map<string, Cell>;
}

/** SCR-07 현장점검 관리.
 *
 * 사람이 시스템 판정을 번복하는 지점이다. 체크리스트의 '상시 수동 운행 구간
 * (도로 문제 아님)' 을 고르면 서버가 해당 격자를 후보에서 내린다. 그 되돌림이
 * 실제로 동작해야 "AI 가 원인을 단정하지 않는다"는 주장이 화면에서 성립한다.
 *
 * 등록·상태변경은 로그인이 필요하다. 누가 판정을 뒤집었는지가 기록으로 남아야
 * 의미가 있어서, inspector 는 화면이 보내지 않고 서버가 토큰에서 채운다.
 */
export function Inspections() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  // 대시보드 업무함이 ?status=... 로 넘긴다. 주소를 그대로 상태로 삼아야
  // 뒤로가기·새로고침·링크 공유가 같게 동작한다.
  const filter = asStatus(params.get("status"));
  const setFilter = (next: InspectionStatus | null) => {
    const p = new URLSearchParams(params);
    if (next) p.set("status", next);
    else p.delete("status");
    setParams(p, { replace: true });
  };

  const targetCell = params.get("cell");

  const { data, loading, error, reload } = useApi<Bundle>(async () => {
    const [inspections, options, cells] = await Promise.all([
      api.inspections(),
      api.findingOptions(),
      api.cells().catch(() => [] as Cell[]),
    ]);
    return {
      inspections,
      options,
      cells: new Map(cells.map((c) => [c.cell_key, c])),
    };
  }, []);

  if (loading) return <Loading label="점검 목록을 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  const { inspections, options, cells } = data;
  const counts = STATUS_ORDER.map((s) => ({
    status: s,
    n: inspections.filter((i) => i.status === s).length,
  }));
  const rows = filter ? inspections.filter((i) => i.status === filter) : inspections;

  return (
    <div className="rw-stack">
      <PageHeader
        title="현장점검 관리"
        description="시스템은 후보를 제시하고, 원인은 담당자가 현장에서 확정합니다"
        actions={
          <div className="rw-row rw-wrap">
            <button
              type="button"
              className={`rw-btn rw-btn--sm ${filter === null ? "rw-btn--secondary" : "rw-btn--ghost"}`}
              onClick={() => setFilter(null)}
            >
              전체 {inspections.length}
            </button>
            {counts.map(({ status, n }) => (
              <button
                key={status}
                type="button"
                className={`rw-btn rw-btn--sm ${filter === status ? "rw-btn--secondary" : "rw-btn--ghost"}`}
                onClick={() => setFilter(filter === status ? null : status)}
              >
                {STATUS_LABEL[status]} {n}
              </button>
            ))}
          </div>
        }
      />

      {!user && (
        <Alert
          severity="caution"
          title="현장점검 등록에는 로그인이 필요합니다"
          action={
            <Link to="/login" className="rw-btn rw-btn--primary rw-btn--sm">
              로그인
            </Link>
          }
        >
          조회는 로그인 없이 가능합니다. 등록은 누가 판정을 확정·번복했는지
          기록으로 남겨야 하므로 로그인한 담당자만 할 수 있습니다.
        </Alert>
      )}

      <div className="rw-cols rw-cols--form">
        <Card title="점검 목록" aside="최근 등록순" flush>
          {rows.length === 0 ? (
            <Empty>해당 상태의 점검이 없습니다.</Empty>
          ) : (
            <div className="rw-table-wrap">
              <table className="rw-table">
                <thead>
                  <tr>
                    <th scope="col">구간 좌표</th>
                    <th scope="col">도로명</th>
                    <th scope="col">등록일</th>
                    <th scope="col">점검 결과</th>
                    <th scope="col">상태 · 담당</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((i) => {
                    const cell = i.cell_key ? cells.get(i.cell_key) : undefined;
                    return (
                      <tr key={i.id}>
                        <td className="rw-num">
                          {cell ? (
                            <Link
                              to={`/cells/${encodeURIComponent(cell.cell_key)}`}
                            >
                              {coord(cell.lat, cell.lon)}
                            </Link>
                          ) : (
                            `격자 ${i.cell_key ?? "—"}`
                          )}
                        </td>
                        <td>
                          {/* 도로명과 배지를 한 줄에 두면 이 칸 하나가 300px 를
                              먹어 나머지 칸이 무너진다. 세로로 쌓는다. */}
                          <div className="rw-stack-sm">
                            <span>{i.road_name ?? "도로명 미상"}</span>
                            <span>
                              <ClassBadge classification={i.classification} short />
                            </span>
                          </div>
                        </td>
                        <td className="rw-num">{day(i.created_at)}</td>
                        <td>
                          {i.findings.length > 0 ? i.findings.join(", ") : "—"}
                        </td>
                        {/* 상태와 담당자를 한 칸에 쌓는다. 열을 하나 줄여야
                            좁은 창에서 표가 가로로 넘치지 않는다. */}
                        <td>
                          <div className="rw-stack-sm">
                            <span>
                              <StatusBadge status={i.status} />
                            </span>
                            {/* 담당자가 없으면 줄 자체를 두지 않는다.
                                빈 자리 표시가 줄마다 쌓이면 표만 시끄러워진다. */}
                            {i.inspector && (
                              <span className="rw-aux">{i.inspector}</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <InspectionForm
          options={options}
          cells={cells}
          targetCell={targetCell}
          onTargetChange={(key) =>
            setParams(
              (prev) => {
                const next = new URLSearchParams(prev);
                if (key) next.set("cell", key);
                else next.delete("cell");
                return next;
              },
              { replace: true },
            )
          }
          canSubmit={Boolean(user)}
          onSaved={reload}
        />
      </div>
    </div>
  );
}

function InspectionForm({
  options,
  cells,
  targetCell,
  onTargetChange,
  canSubmit,
  onSaved,
}: {
  options: FindingOptions;
  cells: Map<string, Cell>;
  targetCell: string | null;
  onTargetChange: (key: string | null) => void;
  canSubmit: boolean;
  onSaved: () => void;
}) {
  const [findings, setFindings] = useState<string[]>([]);
  const [action, setAction] = useState("");
  const [status, setStatus] = useState<InspectionStatus>("inspecting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const cell = targetCell ? cells.get(targetCell) : undefined;
  const overturning = findings.includes(options.not_a_road_issue);

  const toggle = (f: string) =>
    setFindings((v) => (v.includes(f) ? v.filter((x) => x !== f) : [...v, f]));

  const reset = () => {
    setFindings([]);
    setAction("");
    setStatus("inspecting");
    setError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!targetCell) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api.createInspection({
        cell_key: targetCell,
        findings,
        action: action.trim() || null,
        status,
      });
      reset();
      setDone(true);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장하지 못했습니다");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="현장점검 등록"
      aside={cell ? <span className="rw-num">{coord(cell.lat, cell.lon)}</span> : undefined}
    >
      <form className="rw-stack" onSubmit={submit}>
        <div className="rw-field">
          <label className="rw-label" htmlFor="target-cell">
            대상 구간
          </label>
          <select
            id="target-cell"
            className="rw-select"
            value={targetCell ?? ""}
            onChange={(e) => onTargetChange(e.target.value || null)}
          >
            <option value="">구간을 선택하세요</option>
            {[...cells.values()]
              .filter((c) => c.is_candidate)
              .map((c) => (
                <option key={c.cell_key} value={c.cell_key}>
                  {coord(c.lat, c.lon)} · {c.road_name ?? "도로명 미상"}
                </option>
              ))}
          </select>
        </div>

        <fieldset className="rw-fieldset">
          <legend className="rw-label">점검 결과 (중복 선택)</legend>
          {options.findings.map((f) => (
            <label key={f} className="rw-check">
              <input
                type="checkbox"
                checked={findings.includes(f)}
                onChange={() => toggle(f)}
              />
              <span className="rw-check__text">{f}</span>
            </label>
          ))}
        </fieldset>

        {/* 사람이 시스템 판정을 뒤집는 순간이므로 결과를 미리 알린다 */}
        {overturning && (
          <p className="rw-note">
            "{options.not_a_road_issue}"을(를) 선택하면 해당 구간은 후보에서
            제외되고 지도에서 회색으로 표시됩니다. 분류 자체는 분석 결과이므로
            그대로 두고, 점검 대상 여부만 내립니다.
          </p>
        )}

        <div className="rw-field">
          <label className="rw-label" htmlFor="action">
            조치 내용
          </label>
          <textarea
            id="action"
            className="rw-textarea"
            placeholder="예) 차선 재도색 요청 — 도로관리과 이관"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>

        <div className="rw-field">
          <label className="rw-label" htmlFor="status">
            상태
          </label>
          <select
            id="status"
            className="rw-select"
            value={status}
            onChange={(e) => setStatus(e.target.value as InspectionStatus)}
          >
            {options.statuses.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <Alert severity="caution" title="저장하지 못했습니다">
            {error}
          </Alert>
        )}
        {done && (
          <Alert severity="done" title="점검 결과를 저장했습니다">
            목록과 지도에 바로 반영됩니다.
          </Alert>
        )}

        <div className="rw-row">
          <button
            type="button"
            className="rw-btn rw-btn--secondary"
            onClick={reset}
            disabled={busy}
          >
            취소
          </button>
          <button
            type="submit"
            className="rw-btn rw-btn--primary rw-grow"
            disabled={busy || !targetCell || !canSubmit}
          >
            {busy ? "저장 중…" : "점검 결과 저장"}
          </button>
        </div>

        {!canSubmit && (
          <p className="rw-aux">로그인하면 저장할 수 있습니다.</p>
        )}
      </form>
    </Card>
  );
}
