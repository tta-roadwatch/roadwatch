import { useState } from "react";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { QualityCheck } from "../api/types";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { Empty, ErrorState, Loading } from "../components/States";
import { SubTabs } from "../components/SubTabs";
import { DATA_TABS } from "./dataTabs";
import { num } from "../lib/format";

/** 검사 항목의 사람이 읽는 이름. 서버는 코드명을 준다. */
const CHECK_LABEL: Record<string, string> = {
  required_fields: "필수 필드 존재",
  coord_range: "좌표 범위",
  label_consistency: "파일 라벨과 수집시각 일치",
  metric_availability: "지표 산출 가능 여부",
  constant_fields: "전 레코드 동일값 필드",
};

/** 검사 상태 표기.
 *
 * warn 을 danger 로 올리지 않는다. 이 서비스는 원인을 단정하지 않으므로
 * 주의까지만 말한다. excluded 는 실패가 아니라 분석에서 뺐다는 기록이다.
 */
const STATUS_META: Record<string, { label: string; variant: string }> = {
  pass: { label: "통과", variant: "low" },
  warn: { label: "주의", variant: "intermittent" },
  excluded: { label: "분석 제외", variant: "unranked" },
};

function statusMeta(s: string) {
  return STATUS_META[s] ?? { label: s, variant: "unranked" };
}

/** SCR-04 품질검증.
 *
 * 검사를 통과했다는 자랑이 아니라, 무엇을 걸러냈고 무엇을 분석에서 뺐는지
 * 남기는 화면이다. 그래서 warn 과 excluded 를 숨기지 않고 기본으로 보여준다.
 */
export function Quality() {
  const { data, loading, error, reload } = useApi(() => api.quality(), []);
  const [filter, setFilter] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  if (loading) return <Loading label="품질검증 결과를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  const statuses = Object.keys(data.summary);
  const rows = filter ? data.checks.filter((c) => c.status === filter) : data.checks;

  return (
    <div className="rw-stack">
      <PageHeader
        title="품질검증"
        description={`주행 세션별 검사 ${num(data.total)}건 · 걸러낸 항목과 분석에서 제외한 항목을 함께 기록합니다`}
        actions={
          <div className="rw-row rw-wrap">
            <button
              type="button"
              className={`rw-btn rw-btn--sm ${filter === null ? "rw-btn--secondary" : "rw-btn--ghost"}`}
              onClick={() => setFilter(null)}
            >
              전체 {num(data.total)}
            </button>
            {statuses.map((s) => (
              <button
                key={s}
                type="button"
                className={`rw-btn rw-btn--sm ${filter === s ? "rw-btn--secondary" : "rw-btn--ghost"}`}
                onClick={() => setFilter(filter === s ? null : s)}
              >
                {statusMeta(s).label} {num(data.summary[s])}
              </button>
            ))}
          </div>
        }
      />

      <SubTabs tabs={DATA_TABS} />

      <Card
        title="검사 결과"
        aside="행을 누르면 상세를 펼칩니다"
        flush
        footer="'주의'는 분석을 막는 오류가 아니라 해석에 주의가 필요하다는 기록입니다. '분석 제외'는 해당 항목을 판정 근거에서 뺐다는 뜻입니다."
      >
        {rows.length === 0 ? (
          <Empty>해당 상태의 검사가 없습니다.</Empty>
        ) : (
          <div className="rw-table-wrap">
            <table className="rw-table">
              <thead>
                <tr>
                  <th scope="col">세션</th>
                  <th scope="col">검사 항목</th>
                  <th scope="col">상태</th>
                  <th scope="col">요약</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => {
                  const id = `${c.session_id}:${c.check_name}`;
                  return (
                    <CheckRow
                      key={id}
                      check={c}
                      open={open === id}
                      onToggle={() => setOpen(open === id ? null : id)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function CheckRow({
  check,
  open,
  onToggle,
}: {
  check: QualityCheck;
  open: boolean;
  onToggle: () => void;
}) {
  const meta = statusMeta(check.status);
  const detail = check.detail ?? {};
  // 서버가 상세를 자유 형식으로 준다. note 가 있으면 그것이 요약이고,
  // 없으면 펼쳐서 원문을 보여준다.
  const note = typeof detail.note === "string" ? detail.note : null;

  return (
    <>
      <tr data-clickable="true" onClick={onToggle}>
        <th scope="row" className="rw-bold">
          {check.session_id}
        </th>
        <td>
          {CHECK_LABEL[check.check_name] ?? check.check_name}
          <p className="rw-aux rw-mono">{check.check_name}</p>
        </td>
        <td>
          <span className={`rw-badge rw-badge--${meta.variant}`}>{meta.label}</span>
        </td>
        <td className="rw-aux">{note ?? "상세 보기"}</td>
      </tr>

      {open && (
        <tr>
          <td colSpan={4}>
            <pre className="rw-code" style={{ maxHeight: 340 }}>
              {JSON.stringify(check.detail, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
