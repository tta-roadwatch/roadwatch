import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type {
  CellFeatureCollection,
  MapBounds,
  RoadLinkCollection,
} from "../api/types";
import { ClassBadge, StatusBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { EventRate } from "../components/EventRate";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { VulnerabilityMap, VWORLD_KEY } from "../components/VulnerabilityMap";
import {
  CLASS_META,
  CLASS_ORDER,
  classMeta,
  type ClassKey,
} from "../lib/classification";
import { FAMILY_ORDER, familyShort } from "../lib/family";
import { coord, num, pct } from "../lib/format";

/** 범례에 세우는 순서. always_manual 은 현 데이터에 0곳이지만 빼지 않는다 —
 * 분류가 비어서가 아니라 그 패턴이 관측되지 않은 것이라, 빼면 "그런 판정은
 * 없다"로 잘못 읽힌다. 판정 없음도 함께 세워 관측 부족과 구분한다. */
const LEGEND: ClassKey[] = [...CLASS_ORDER, "unranked"];

interface Bundle {
  cells: CellFeatureCollection;
  roads: RoadLinkCollection | null;
  bounds: MapBounds | null;
}

/** SCR-05 취약도로 지도.
 *
 * VWorld 키가 없어도 격자·도로망 레이어는 그대로 동작해야 한다. 키가 없으면
 * 배경 타일만 빠지고 분석 결과는 전부 보인다.
 */
export function MapPage() {
  const [visible, setVisible] = useState<ClassKey[]>(LEGEND);
  const [minSessions, setMinSessions] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi<Bundle>(async () => {
    const [cells, roads, bounds] = await Promise.all([
      api.geoCells(),
      // 도로망과 경계는 부가 정보다. 실패해도 격자는 떠야 한다.
      api.geoRoadLinks(true).catch(() => null),
      api.geoBounds().catch(() => null),
    ]);
    return { cells, roads, bounds };
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of data?.cells.features ?? []) {
      const k = f.properties.classification ?? "unranked";
      c[k] = (c[k] ?? 0) + 1;
    }
    return c;
  }, [data]);

  const maxObserved = useMemo(
    () =>
      Math.max(
        1,
        ...(data?.cells.features ?? []).map((f) => f.properties.observed_sessions),
      ),
    [data],
  );

  if (loading) return <Loading label="지도를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "지도를 불러오지 못했습니다"} onRetry={reload} />;
  }

  const shown = data.cells.features.filter(
    (f) =>
      visible.includes((f.properties.classification ?? "unranked") as ClassKey) &&
      f.properties.observed_sessions >= minSessions,
  ).length;

  const toggleClass = (k: ClassKey) =>
    setVisible((v) => (v.includes(k) ? v.filter((x) => x !== k) : [...v, k]));

  return (
    <div className="rw-stack">
      <PageHeader
        title="취약도로 지도"
        description={`${data.cells.metadata.cell_size_m}m 격자 · 전체 ${num(
          data.cells.metadata.count,
        )}곳 중 ${num(shown)}곳 표시 · 세션 교차 비교`}
        actions={
          <div className="rw-row rw-wrap">
            {CLASS_ORDER.map((k) => (
              <span key={k} className={`rw-badge rw-badge--${k}`}>
                {CLASS_META[k].label} {num(counts[k] ?? 0)}곳
              </span>
            ))}
          </div>
        }
      />

      {!VWORLD_KEY && (
        <p className="rw-note">
          VWorld 인증키가 설정되지 않아 배경 지도 없이 표시합니다. 격자와 도로망
          레이어는 정상 동작합니다 — 키를 넣으면 배경 지도만 더해집니다.
        </p>
      )}

      <div className="rw-cols rw-cols--map">
        {/* ── 필터 ── */}
        <Card title="필터">
          <div className="rw-stack">
            <div>
              <p className="rw-label" style={{ marginBottom: "var(--rw-space-2)" }}>
                분류
              </p>
              {LEGEND.map((k) => (
                <label key={k} className="rw-check">
                  <input
                    type="checkbox"
                    checked={visible.includes(k)}
                    onChange={() => toggleClass(k)}
                  />
                  <span className="rw-check__text">
                    <span className="rw-row">
                      <span
                        className="rw-legend__swatch"
                        style={{ background: `var(${CLASS_META[k].fillVar})` }}
                        aria-hidden="true"
                      />
                      {CLASS_META[k].label}
                    </span>
                    <span className="rw-aux">{num(counts[k] ?? 0)}곳</span>
                  </span>
                </label>
              ))}
            </div>

            <div className="rw-field">
              <label className="rw-label" htmlFor="min-sessions">
                최소 관측 세션
              </label>
              <input
                id="min-sessions"
                type="range"
                min={1}
                max={maxObserved}
                value={minSessions}
                onChange={(e) => setMinSessions(Number(e.target.value))}
              />
              <p className="rw-aux">
                {minSessions}개 이상 관측된 격자만 표시 (최대 {maxObserved}개)
              </p>
            </div>

            {/* 격자 크기는 파이프라인 캘리브레이션으로 정해진 값이라 화면에서
                바꿀 수 없다. 고를 수 있는 것처럼 보이면 안 되므로 값만 밝힌다. */}
            <div>
              <p className="rw-label">격자 크기</p>
              <p className="rw-aux">
                {data.cells.metadata.cell_size_m}m 고정 · 분석 캘리브레이션으로
                결정된 값입니다
              </p>
            </div>
          </div>
        </Card>

        {/* ── 지도 ── */}
        <div className="rw-stack-sm">
          <div className="rw-card rw-map-card">
            <VulnerabilityMap
              cells={data.cells}
              roads={data.roads}
              bounds={data.bounds}
              visibleClasses={visible}
              minObservedSessions={minSessions}
              selectedCellKey={selected}
              onSelect={setSelected}
            />
          </div>

          <div className="rw-card rw-legend">
            {LEGEND.map((k) => (
              <span key={k} className="rw-legend__item">
                <span
                  className="rw-legend__swatch"
                  style={{ background: `var(${CLASS_META[k].fillVar})` }}
                  aria-hidden="true"
                />
                <span className="rw-aux">
                  {CLASS_META[k].badge} · {num(counts[k] ?? 0)}곳
                </span>
              </span>
            ))}
          </div>
        </div>

        {/* ── 선택한 구간 ── */}
        <SelectedCell cellKey={selected} />
      </div>
    </div>
  );
}

/** 선택한 격자의 요약. 이벤트율은 여기서도 갈래를 나눠 보여준다. */
function SelectedCell({ cellKey }: { cellKey: string | null }) {
  const { data, loading, error } = useApi(
    () => (cellKey ? api.cell(cellKey) : Promise.resolve(null)),
    [cellKey],
  );

  if (!cellKey) {
    return (
      <Card title="선택한 구간">
        <p className="rw-aux">지도에서 격자를 선택하면 상세가 표시됩니다.</p>
      </Card>
    );
  }

  if (loading) return <Card title="선택한 구간"><Loading /></Card>;
  if (error || !data) {
    return (
      <Card title="선택한 구간">
        <p className="rw-aux">{error ?? "불러오지 못했습니다"}</p>
      </Card>
    );
  }

  const { cell, by_family } = data;
  const families = FAMILY_ORDER.filter((f) => by_family[f]);
  const latest = data.inspections[0];
  const observed = data.observations.filter((o) => o.observed).length;
  const measurable = data.observations.filter((o) => o.measurable).length;

  return (
    <Card title="선택한 구간">
      <div className="rw-stack">
        <div>
          <p className="rw-card-title rw-num">{coord(cell.lat, cell.lon)}</p>
          <p className="rw-aux">
            {cell.road_name ?? "도로명 미상"}
            {cell.address ? ` · ${cell.address}` : ""}
          </p>
          <div className="rw-row rw-wrap" style={{ marginTop: "var(--rw-space-3)" }}>
            <ClassBadge classification={cell.classification} />
            {latest && <StatusBadge status={latest.status} />}
          </div>
        </div>

        {families.length > 0 ? (
          families.map((f) => {
            const b = by_family[f]!;
            return (
              <div key={f} className="rw-family">
                <div className="rw-family__head">
                  <span className="rw-family__title">{familyShort(f)}</span>
                  <span className="rw-family__range">
                    {pct(b.min_event_rate)} ~ {pct(b.max_event_rate)}
                  </span>
                </div>
                {b.sessions.map((s) => (
                  <EventRate
                    key={s.session_id}
                    label={s.session_id}
                    observed
                    measurable
                    eventRate={s.event_rate}
                    eventCount={s.event_count}
                    observationCount={s.observation_count}
                    variant={classMeta(cell.classification).key}
                  />
                ))}
              </div>
            );
          })
        ) : (
          <p className="rw-note">
            측정 가능한 관측이 없습니다. 이벤트가 없었다는 뜻이 아니라 해당
            격자를 지난 세션에 필요한 데이터셋이 없다는 뜻입니다.
          </p>
        )}

        <div className="rw-dl">
          <dt>도로</dt>
          <dd>
            {cell.lanes ?? "—"}차로 · 제한 {cell.max_speed ?? "—"}km/h
          </dd>
          {/* 관측 수는 상세 응답에 따로 오지 않으므로 관측 배열에서 센다.
              '측정 가능'을 함께 적어야 관측은 됐지만 산출할 수 없는 세션이
              이벤트 0% 로 읽히지 않는다. */}
          <dt>관측 세션</dt>
          <dd>
            {observed}개 중 측정 가능 {measurable}개
          </dd>
        </div>

        <Link
          to={`/cells/${encodeURIComponent(cell.cell_key)}`}
          className="rw-btn rw-btn--primary rw-btn--block"
        >
          구간 상세 보기
        </Link>

        <p className="rw-aux">
          본 서비스는 원인을 판정하지 않고 현장점검 후보를 제시합니다.
        </p>
      </div>
    </Card>
  );
}
