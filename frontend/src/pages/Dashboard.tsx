import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { Cell, Dashboard as DashboardData } from "../api/types";
import { Alert } from "../components/Alert";
import { ClassBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { coord, num, pct } from "../lib/format";

/** SCR-01 대시보드.
 *
 * 첫 화면이 통계판이 아니라 과업 제시라는 게 요점이다. 그래서 맨 위가 숫자
 * 타일이 아니라 "오늘 점검할 곳이 N곳" 문장이고, 그 아래에 근거가 온다.
 *
 * 좌표는 대시보드 응답에 없어 격자 목록에서 채워 넣는다. 목록 조회가 실패해도
 * 표는 격자 번호로 그려진다.
 */
export function Dashboard() {
  const navigate = useNavigate();

  const { data, loading, error, reload } = useApi<
    [DashboardData, Cell[] | null]
  >(
    () =>
      Promise.all([
        api.dashboard(),
        // 좌표는 부가 정보다. 실패해도 화면 전체를 막지 않는다.
        api.cells(true).catch(() => null),
      ]),
    [],
  );

  if (loading) return <Loading label="대시보드를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "대시보드를 불러오지 못했습니다"} onRetry={reload} />;
  }

  const [dash, cells] = data;
  const byKey = new Map((cells ?? []).map((c) => [c.cell_key, c]));

  return (
    <div className="rw-stack">
      <PageHeader title="대시보드" />

      <Alert
        title={dash.headline}
        action={
          <Link to="/map" className="rw-btn rw-btn--primary">
            취약도로 지도 열기
          </Link>
        }
      >
        {dash.subtext}
      </Alert>

      {/* 라벨 불일치는 분석 신뢰도에 직접 영향을 주므로 첫 화면에서 밝힌다.
          감춘 게 아니라 보정했음을 알리는 것이 목적이다. */}
      {dash.quality_flag.label_mismatch_sessions > 0 && (
        <Alert
          severity="caution"
          title={`파일 라벨과 실제 수집시각이 다른 세션이 ${dash.quality_flag.label_mismatch_sessions}개 있습니다`}
          action={
            <Link to="/data" className="rw-btn rw-btn--secondary rw-btn--sm">
              데이터 확인
            </Link>
          }
        >
          {dash.quality_flag.note}
        </Alert>
      )}

      <div className="rw-card">
        <div className="rw-stats">
          <Stat label="적재 레코드" value={num(dash.stats.records)} unit="건" />
          <Stat label="주행 세션" value={num(dash.stats.sessions)} unit="개" />
          <Stat label="취약구간 후보" value={num(dash.stats.candidates)} unit="곳" />
          <Stat
            label="점검 대기"
            value={num(dash.stats.pending_inspections)}
            unit="건"
          />
        </div>
      </div>

      <Card
        title="점검이 필요한 구간"
        aside={<Link to="/map">전체 보기</Link>}
        flush
        footer="본 서비스는 도로의 문제를 확정하지 않고 현장점검이 필요한 후보를 제시합니다."
      >
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">구간 좌표</th>
                <th scope="col">도로명</th>
                <th scope="col">반복 세션</th>
                <th scope="col">이벤트율 범위</th>
                <th scope="col">분류</th>
              </tr>
            </thead>
            <tbody>
              {dash.top_candidates.map((c) => {
                const cell = byKey.get(c.cell_key);
                return (
                  <tr
                    key={c.cell_key}
                    data-clickable="true"
                    onClick={() =>
                      navigate(`/cells/${encodeURIComponent(c.cell_key)}`)
                    }
                  >
                    <td className="rw-num">
                      {cell ? coord(cell.lat, cell.lon) : `격자 ${c.cell_key}`}
                    </td>
                    <td>{c.road_name ?? "도로명 미상"}</td>
                    {/* 이 서비스의 주장은 '여러 주행에서 반복된다'이므로
                        반복 세션 수를 앞세우고 이벤트율은 범위로만 밝힌다.
                        한 세션의 최댓값으로 줄세우면 상위가 전부 100%가 된다. */}
                    <td className="rw-num rw-bold">{c.session_count}개</td>
                    <td className="rw-num rw-aux">
                      {pct(c.min_event_rate)} ~ {pct(c.max_event_rate)}
                    </td>
                    <td>
                      <ClassBadge
                        classification={cell?.classification ?? "intermittent"}
                        short
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="rw-stat">
      <p className="rw-stat__label">{label}</p>
      <p className="rw-stat__value">
        {value}
        <span className="rw-stat__unit">{unit}</span>
      </p>
    </div>
  );
}
