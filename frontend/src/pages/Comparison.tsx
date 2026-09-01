import { Fragment } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type {
  Comparison as ComparisonData,
  ComparisonSide,
  Inspection,
} from "../api/types";
import { Alert } from "../components/Alert";
import { StatusBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { day, num, pct } from "../lib/format";

interface Bundle {
  comparison: ComparisonData;
  history: Inspection[];
}

/** SCR-08 조치 전·후 비교.
 *
 * 조치 완료일을 기준선 삼아 실제 관측을 양쪽으로 가른다. 예전에는 조치 후
 * 값을 시뮬레이션으로 채웠는데, 판교 데이터가 2022-05 ~ 2024-01 에 걸쳐
 * 있어 조치일이 그 사이면 양쪽 다 실측이 된다.
 *
 * 세 가지 상태를 그대로 화면에 옮긴다.
 *   no_action          조치 기록이 없다 — 비교할 기준선이 없다
 *   awaiting_remeasure 한쪽에만 세션이 있다 — 재측정을 기다린다
 *   compared           양쪽 다 실측이다
 *
 * 값이 달라도 조치 «때문»이라고 쓰지 않는다. 계절·시간대·교통량이 함께
 * 달라졌을 수 있어서다. 이 서비스는 원인을 단정하지 않는다.
 */
export function Comparison() {
  const { cellKey = "" } = useParams();

  const { data, loading, error, reload } = useApi<Bundle>(async () => {
    const [comparison, history] = await Promise.all([
      api.comparison(cellKey),
      // 담당자는 비교 응답에 없어 점검 목록에서 가져온다. 없는 값을
      // 화면에서 지어내지 않으려는 것이다.
      api.inspections({ cell_key: cellKey }).catch(() => [] as Inspection[]),
    ]);
    return { comparison, history };
  }, [cellKey]);

  if (loading) return <Loading label="비교 결과를 불러오는 중입니다" />;
  if (error || !data) {
    return (
      <ErrorState message={error ?? "비교 결과를 불러오지 못했습니다"} onRetry={reload} />
    );
  }

  const c = data.comparison;

  return (
    <>
      <PageHeader
        title="조치 전·후"
        description={`${c.road_name ?? "도로명 없음"} · ${c.cell_key}`}
        crumbs={[
          { label: "취약도로 지도", to: "/map" },
          { label: "구간 상세", to: `/cells/${encodeURIComponent(c.cell_key)}` },
          { label: "조치 전·후" },
        ]}
      />

      <div className="rw-stack">
        {c.state === "no_action" && (
        <Alert
          severity="info"
          title="비교할 기준선이 없습니다"
          action={
            <Link className="rw-btn rw-btn--secondary rw-btn--sm" to="/inspections">
              점검 관리로
            </Link>
          }
        >
          {c.notice}
        </Alert>
      )}

      {c.state === "awaiting_remeasure" && (
        <Alert severity="caution" title="재측정 대기">
          {c.notice}
        </Alert>
      )}

      {c.state === "compared" && (
        <>
          <Alert
            severity="info"
            title={`${day(c.baseline)} 조치를 기준으로 나눈 실제 관측입니다`}
          >
            {c.notice}
          </Alert>

          <div className="rw-flip">
            <SideCard label="조치 전" side={c.before!} />
            <div className="rw-flip__arrow" aria-hidden="true">
              →
            </div>
            <SideCard label="조치 후" side={c.after!} />
          </div>

          {c.delta != null && (
            <Card title="변화">
              <div className="rw-figure">
                <p className="rw-figure__label">이벤트율 차이</p>
                <p className="rw-figure__value">
                  {c.delta > 0 ? "+" : ""}
                  {pct(c.delta)}p
                </p>
              </div>
              <p className="rw-note">
                관측된 차이입니다. 이 변화가 조치 때문인지는 확정하지 않습니다 —
                계절·시간대·교통량이 함께 달라졌을 수 있습니다. 확정은 현장점검이
                합니다.
              </p>
            </Card>
          )}
        </>
      )}

      <Card title="조치 이력">
        {c.history.length === 0 ? (
          <p className="rw-note">등록된 점검·조치 기록이 없습니다.</p>
        ) : (
          <div className="rw-table-wrap">
            <table className="rw-table">
              <thead>
                <tr>
                  <th scope="col">상태</th>
                  <th scope="col">확인한 원인</th>
                  <th scope="col">조치 내용</th>
                  <th scope="col">완료일</th>
                </tr>
              </thead>
              <tbody>
                {c.history.map((h, i) => (
                  <tr key={i}>
                    <td>
                      <StatusBadge status={h.status} />
                    </td>
                    <td>{h.cause ?? <span className="rw-note">—</span>}</td>
                    <td>{h.action ?? <span className="rw-note">—</span>}</td>
                    <td>{h.completed_on ? day(h.completed_on) : <span className="rw-note">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="세션별 관측">
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">주행일</th>
                <th scope="col" className="rw-table__num">
                  이벤트 / 관측
                </th>
                <th scope="col" className="rw-table__num">
                  이벤트율
                </th>
              </tr>
            </thead>
            <tbody>
              {c.measured_sessions.map((s) => (
                <tr key={s.session_id}>
                  <td>{day(s.observed_at)}</td>
                  <td className="rw-table__num">
                    {num(s.event_count)} / {num(s.observation_count)}초
                  </td>
                  <td className="rw-table__num">{pct(s.event_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Card>
      </div>
    </>
  );
}

/** 조치 전·후 한쪽. 여러 세션을 관측 수로 가중 평균한 값이다.
 *
 * 단순 평균이면 3초 관측과 300초 관측이 같은 무게를 갖는다. 이벤트율은
 * 관측 대비 비율이라 그러면 틀린다. 그래서 세션 수를 함께 밝혀 «몇 번의
 * 주행을 묶은 값인지» 보이게 한다. */
function SideCard({ label, side }: { label: string; side: ComparisonSide }) {
  return (
    <Card title={label}>
      <div className="rw-rate">
        <div className="rw-rate__head">
          <span className="rw-badge rw-badge--measured">실측값</span>
          <span className="rw-meta">{side.session_count}개 주행</span>
        </div>
        <div className="rw-rate__value rw-rate__value--primary">
          {pct(side.event_rate)}
        </div>
        <div className="rw-rate__foot">
          {num(side.event_count)} / {num(side.observation_count)}초
        </div>
      </div>
      <div className="rw-dl">
        {side.sessions.map((s) => (
          <Fragment key={s.session_id}>
            <dt>{day(s.observed_at)}</dt>
            <dd>{pct(s.event_rate)}</dd>
          </Fragment>
        ))}
      </div>
    </Card>
  );
}
