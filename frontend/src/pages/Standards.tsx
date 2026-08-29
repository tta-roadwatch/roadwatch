import { useState } from "react";

import { api, API_BASE } from "../api/client";
import { useApi } from "../api/useApi";
import type { StandardRow, StandardStatus } from "../api/types";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { Toggle } from "../components/Toggle";
import { num } from "../lib/format";

/** 표준 적용 정도. 과장하지 않는 것이 이 화면의 요점이라 배지도 3단계로 나눈다.
 *  '설계 참조'는 코드 산출물이 없다는 뜻이므로 성공색을 쓰지 않는다. */
const STATUS_VARIANT: Record<StandardStatus, string> = {
  implemented: "low",
  partial: "intermittent",
  reference: "unranked",
};

/** SCR-09 표준 · API.
 *
 * 표준 준수를 말로 주장하지 않고 실제 응답을 화면에서 그대로 보여준다.
 * evidence 경로를 누르면 그 자리에서 호출해 원문을 띄운다.
 */
export function Standards() {
  const { data, loading, error, reload } = useApi(() => api.standards(), []);
  const [path, setPath] = useState<string | null>(null);
  const [keyValues, setKeyValues] = useState(false);

  if (loading) return <Loading label="표준 현황을 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  return (
    <div className="rw-stack">
      <PageHeader
        title="표준 · API"
        description="적용한 표준과 그 근거가 되는 실제 응답입니다"
        actions={
          <div className="rw-row rw-wrap">
            <span className="rw-badge rw-badge--low">
              구현 {num(data.summary.implemented ?? 0)}
            </span>
            <span className="rw-badge rw-badge--intermittent">
              부분 구현 {num(data.summary.partial ?? 0)}
            </span>
            <span className="rw-badge rw-badge--unranked">
              설계 참조 {num(data.summary.reference ?? 0)}
            </span>
          </div>
        }
      />

      <p className="rw-note">{data.note}</p>

      <Card title="적용 표준" flush>
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">표준</th>
                <th scope="col">역할</th>
                <th scope="col">적용</th>
                <th scope="col">근거</th>
              </tr>
            </thead>
            <tbody>
              {data.standards.map((s) => (
                <StandardRowView
                  key={s.id}
                  row={s}
                  active={path === s.evidence}
                  onShow={() => setPath(s.evidence)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="rw-note">{data.spatial_note}</p>

      <Card
        title="NGSI-LD 응답"
        aside={
          <Toggle
            checked={keyValues}
            onChange={setKeyValues}
            label="축약형(keyValues)"
            onText="ON"
            offText="OFF"
          />
        }
        footer={
          <>
            정규 표현법은 속성마다 Property · GeoProperty · Relationship 을 밝히고
            observedAt 을 싣습니다. 축약형은 값만 평탄하게 돌려주는 조회 옵션입니다.
          </>
        }
      >
        <ResponseViewer
          path={
            path ??
            `/ngsi-ld/v1/entities?type=TrafficEvent&limit=1${keyValues ? "&options=keyValues" : ""}`
          }
          onReset={() => setPath(null)}
          custom={path !== null}
        />
      </Card>
    </div>
  );
}

function StandardRowView({
  row,
  active,
  onShow,
}: {
  row: StandardRow;
  active: boolean;
  onShow: () => void;
}) {
  return (
    <tr>
      <td>
        <span className="rw-bold rw-mono">{row.id}</span>
        <p className="rw-aux">{row.name}</p>
      </td>
      <td>
        {row.role}
        <p className="rw-aux">{row.note}</p>
      </td>
      <td>
        <span className={`rw-badge rw-badge--${STATUS_VARIANT[row.status]}`}>
          {row.status_label}
        </span>
      </td>
      <td>
        {row.evidence ? (
          <button
            type="button"
            className={`rw-btn rw-btn--sm ${active ? "rw-btn--secondary" : "rw-btn--ghost"}`}
            onClick={onShow}
          >
            <span className="rw-mono">{row.evidence}</span>
          </button>
        ) : (
          <span className="rw-aux">코드 산출물 없음</span>
        )}
      </td>
    </tr>
  );
}

/** 실제 응답을 그 자리에서 호출해 보여준다. 화면이 재가공하지 않는 게 요점이다. */
function ResponseViewer({
  path,
  onReset,
  custom,
}: {
  path: string;
  onReset: () => void;
  custom: boolean;
}) {
  const { data, loading, error } = useApi(() => api.raw(path), [path]);

  return (
    <div className="rw-stack-sm">
      <div className="rw-row-between rw-wrap">
        <code className="rw-mono rw-aux">
          GET {API_BASE}
          {path}
        </code>
        {custom && (
          <button type="button" className="rw-btn rw-btn--ghost rw-btn--sm" onClick={onReset}>
            기본 응답으로
          </button>
        )}
      </div>

      {loading && <Loading label="응답을 불러오는 중입니다" />}
      {error && <p className="rw-note">{error}</p>}
      {data != null && (
        <pre className="rw-code" style={{ maxHeight: 460 }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
