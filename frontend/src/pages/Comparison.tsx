import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { Comparison as ComparisonData, Inspection } from "../api/types";
import type { ComparisonSide } from "../api/types";
import { Alert } from "../components/Alert";
import { SimulationBadge, StatusBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { Empty, ErrorState, Loading } from "../components/States";
import { day, num, pct } from "../lib/format";

interface Bundle {
  comparison: ComparisonData;
  history: Inspection[];
}

/** SCR-08 개선 전·후 비교.
 *
 * 조치 전은 실측이고 조치 후는 시뮬레이션이다. 실제 개선 이력이 확인된 사례가
 * 없으므로 조치 후 값을 실측처럼 보이게 하면 안 된다. 응답의 simulated 플래그를
 * 근거로 화면 세 곳(제목 배지 · 상단 안내 · 각 카드 배지)에 표기한다.
 */
export function Comparison() {
  const { cellKey = "" } = useParams();

  const { data, loading, error, reload } = useApi<Bundle>(async () => {
    const [comparison, history] = await Promise.all([
      api.comparison(cellKey),
      // 조치 이력의 담당자는 비교 응답에 없어 점검 목록에서 가져온다.
      // 없는 값을 화면에서 지어내지 않으려는 것이다.
      api.inspections({ cell_key: cellKey }).catch(() => [] as Inspection[]),
    ]);
    return { comparison, history };
  }, [cellKey]);

  if (loading) return <Loading label="비교 결과를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "비교 결과를 불러오지 못했습니다"} onRetry={reload} />;
  }

  const { comparison: c, history } = data;

  return (
    <div className="rw-stack">
      <PageHeader
        crumbs={[
          { label: "취약도로 지도", to: "/map" },
          {
            label: c.road_name ?? c.cell_key,
            to: `/cells/${encodeURIComponent(c.cell_key)}`,
          },
          { label: "개선 전·후" },
        ]}
        title="개선 전·후 비교"
        titleAside={<span className="rw-badge rw-badge--simulated">시뮬레이션 데이터</span>}
        description={`${c.road_name ?? "도로명 미상"} · 격자 ${c.cell_key}`}
      />

      {/* 표기 ① 상단 안내 */}
      <Alert severity="caution" title="조치 후 값은 시뮬레이션입니다">
        {c.simulation_notice} 조치 전 {pct(c.before.event_rate)}만 실측값입니다.
      </Alert>

      <div className="rw-flip">
        <Side
          label={`조치 전 · ${day(c.before.observed_at) }`}
          side={c.before}
          tone="wrong"
        />
        <span className="rw-flip__arrow" aria-hidden="true">
          →
        </span>
        <Side label="조치 후 · 재측정" side={c.after} tone="right" />
      </div>

      <Card
        title="조치 이력"
        flush
        footer="재측정은 신규 주행 세션이 공개되어야 가능합니다. 현재는 조치 후 값을 시뮬레이션으로만 제시합니다."
      >
        {history.length === 0 ? (
          <Empty>등록된 조치 이력이 없습니다.</Empty>
        ) : (
          <div className="rw-table-wrap">
            <table className="rw-table">
              <thead>
                <tr>
                  <th scope="col">일자</th>
                  <th scope="col">단계</th>
                  <th scope="col">내용</th>
                  <th scope="col">담당</th>
                </tr>
              </thead>
              <tbody>
                {[...history]
                  .sort((a, b) => a.created_at.localeCompare(b.created_at))
                  .map((h) => (
                    <tr key={h.id}>
                      <td className="rw-num">{day(h.inspected_at ?? h.created_at)}</td>
                      <td>
                        <StatusBadge status={h.status} />
                      </td>
                      <td>
                        {h.findings.length > 0 ? h.findings.join(", ") : null}
                        {h.findings.length > 0 && h.action ? " — " : null}
                        {h.action}
                        {h.findings.length === 0 && !h.action
                          ? "세션 교차 반복성 검출 → 현장점검 권고 등록"
                          : null}
                      </td>
                      {/* 담당자가 없는 권고는 파이프라인이 올린 것이다.
                          그 외에 값이 없으면 지어내지 않고 비워 둔다. */}
                      <td className="rw-aux">
                        {h.inspector ??
                          (h.status === "recommended" ? "시스템" : "—")}
                      </td>
                    </tr>
                  ))}
                <tr>
                  <td className="rw-muted">—</td>
                  <td>
                    <span className="rw-badge rw-badge--unranked">재측정 대기</span>
                  </td>
                  <td className="rw-aux">
                    신규 주행 세션 공개 시 동일 격자 자동 재계산
                  </td>
                  <td className="rw-aux">시스템</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="측정된 세션" aside="조치 전 값의 근거" flush>
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">세션</th>
                <th scope="col">관측 시각</th>
                <th scope="col">이벤트</th>
                <th scope="col">관측</th>
                <th scope="col">이벤트율</th>
              </tr>
            </thead>
            <tbody>
              {c.measured_sessions.map((s) => (
                <tr key={s.session_id}>
                  <td className="rw-bold">{s.session_id}</td>
                  <td className="rw-num">{day(s.observed_at)}</td>
                  <td className="rw-num">{num(s.event_count)}초</td>
                  <td className="rw-num">{num(s.observation_count)}초</td>
                  <td className="rw-num rw-bold">{pct(s.event_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="rw-aux">
        <Link to={`/cells/${encodeURIComponent(c.cell_key)}`}>
          구간 상세로 돌아가기
        </Link>
      </p>
    </div>
  );
}

function Side({
  label,
  side,
  tone,
}: {
  label: string;
  side: ComparisonSide;
  tone: "wrong" | "right";
}) {
  return (
    <div className={`rw-figure${side.simulated ? " rw-figure--sim" : ""}`}>
      <p className="rw-figure__label">{label}</p>
      <p className={`rw-figure__value rw-figure__value--${tone}`}>
        {pct(side.event_rate)}
      </p>
      <p className="rw-figure__foot">
        이벤트 {num(side.event_count)}초 / 관측 {num(side.observation_count)}초
      </p>
      {/* 표기 ②③ 각 카드에 실측인지 시뮬레이션인지 붙인다 */}
      <p style={{ marginTop: "var(--rw-space-4)" }}>
        <SimulationBadge simulated={side.simulated} />
      </p>
    </div>
  );
}
