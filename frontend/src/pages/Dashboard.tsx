import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { Cell, CellDetail, Dashboard as DashboardData } from "../api/types";
import { Alert } from "../components/Alert";
import { ClassBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { FAMILY_ORDER, familyShort } from "../lib/family";
import { coord, num, pct } from "../lib/format";

interface DashboardBundle {
  dash: DashboardData;
  byKey: Map<string, Cell>;
  details: Map<string, CellDetail>;
}

/** SCR-01 대시보드.
 *
 * 첫 화면이 통계판이 아니라 과업 제시라는 게 요점이다. 그래서 맨 위가 숫자
 * 타일이 아니라 "현장점검이 권고된 구간이 N곳" 문장이고, 그 아래에 근거가 온다.
 *
 * 상위 후보의 이벤트율은 대시보드 응답의 min~max 를 그대로 쓰지 않는다. 그 값은
 * 갈래를 섞은 범위라 대표 구간이 "0% ~ 100%" 로 보이고, 그러면 반복성이 있다는
 * 주장이 첫 화면에서부터 깨진다. 상위 후보만 상세를 함께 불러 갈래별로 나눠
 * 적는다 — 좁은 쪽만 골라 보이지 않고 양쪽 다 적어 왜 나눠야 하는지도 드러낸다.
 */
export function Dashboard() {
  const navigate = useNavigate();

  const { data, loading, error, reload } = useApi<DashboardBundle>(async () => {
    const dash = await api.dashboard();

    // 좌표와 갈래별 이벤트율은 부가 정보다. 실패해도 표는 그려져야 한다.
    const [cells, details] = await Promise.all([
      api.cells(true).catch(() => [] as Cell[]),
      Promise.all(
        dash.top_candidates.map((c) =>
          api.cell(c.cell_key).catch(() => null),
        ),
      ),
    ]);

    return {
      dash,
      byKey: new Map(cells.map((c) => [c.cell_key, c])),
      details: new Map(
        details.filter((d): d is CellDetail => d !== null).map((d) => [
          d.cell.cell_key,
          d,
        ]),
      ),
    };
  }, []);

  if (loading) return <Loading label="대시보드를 불러오는 중입니다" />;
  if (error || !data) {
    return (
      <ErrorState message={error ?? "대시보드를 불러오지 못했습니다"} onRetry={reload} />
    );
  }

  const { dash, byKey, details } = data;

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
        footer="본 서비스는 도로의 문제를 확정하지 않고 현장점검이 필요한 후보를 제시합니다. 이벤트율은 갈래마다 정의가 달라 갈래를 나눠 표기합니다."
      >
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">구간 좌표</th>
                <th scope="col">도로명</th>
                <th scope="col">반복 세션</th>
                <th scope="col">갈래별 이벤트율</th>
                <th scope="col">분류</th>
              </tr>
            </thead>
            <tbody>
              {dash.top_candidates.map((c) => {
                const cell = byKey.get(c.cell_key);
                const detail = details.get(c.cell_key);
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
                        반복 세션 수를 앞세운다. 한 세션의 최댓값으로 줄세우면
                        상위가 전부 100%가 되어 순위가 무의미해진다. */}
                    <td className="rw-num rw-bold">{c.session_count}개</td>
                    <td>
                      <FamilyRanges
                        detail={detail}
                        fallbackMin={c.min_event_rate}
                        fallbackMax={c.max_event_rate}
                      />
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

/** 갈래별 이벤트율 범위. 상세를 못 불러온 경우에만 합산 범위로 물러난다. */
function FamilyRanges({
  detail,
  fallbackMin,
  fallbackMax,
}: {
  detail: CellDetail | undefined;
  fallbackMin: number | null;
  fallbackMax: number | null;
}) {
  const families = detail
    ? FAMILY_ORDER.filter((f) => detail.by_family[f])
    : [];

  if (families.length === 0) {
    return (
      <span className="rw-num rw-aux">
        {pct(fallbackMin)} ~ {pct(fallbackMax)}
      </span>
    );
  }

  return (
    <div className="rw-stack-sm">
      {families.map((f) => {
        const b = detail!.by_family[f]!;
        return (
          <div key={f} className="rw-famline">
            <span className="rw-famline__tag">{familyShort(f)}</span>
            <span className="rw-famline__range rw-num">
              {b.min_event_rate === b.max_event_rate
                ? pct(b.min_event_rate)
                : `${pct(b.min_event_rate)} ~ ${pct(b.max_event_rate)}`}
            </span>
          </div>
        );
      })}
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
