import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { CellDetail as CellDetailData, Report } from "../api/types";
import { Alert } from "../components/Alert";
import { ClassBadge, StatusBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { EventRate } from "../components/EventRate";
import { PageHeader } from "../components/PageHeader";
import { Empty, ErrorState, Loading } from "../components/States";
import { classMeta } from "../lib/classification";
import { FAMILY_ORDER, familyShort } from "../lib/family";
import { tallyEventTypes } from "../lib/metrics";
import { coord, num, pct } from "../lib/format";

/** SCR-06 구간 상세.
 *
 * 이 화면의 핵심은 세션별 이벤트율을 **갈래별로 나눠** 보여주는 것이다.
 * BSM 갈래(비상정지·자율주행 해제)와 조인 갈래(저속 정체)는 이벤트 정의가
 * 달라서, 한 줄로 늘어놓으면 대표 구간이 0~100% 로 보이고 "여러 주행에서
 * 반복된다"는 판정 근거가 화면에서 무너진다.
 */
export function CellDetail() {
  const { cellKey = "" } = useParams();
  const { data, loading, error, reload } = useApi(
    () => api.cell(cellKey),
    [cellKey],
  );

  if (loading) return <Loading label="구간 정보를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "구간을 불러오지 못했습니다"} onRetry={reload} />;
  }

  const { cell, observations, by_family, inspections } = data;
  const families = FAMILY_ORDER.filter((f) => by_family[f]);
  const variant = classMeta(cell.classification).key;
  const { primary, reference } = tallyEventTypes(observations);
  const maxCount = Math.max(1, ...primary.map((p) => p.count));
  const latest = inspections[0];

  // 비교에서 빠지는 세션. 두 사유를 뭉뚱그리면 안 된다 —
  //   관측 없음: 이 세션이 해당 격자를 지나지 않았다
  //   측정 불가: 지나갔지만 필요한 데이터셋이 없어 산출할 수 없다
  // 둘 다 "이벤트 0%" 가 아니다.
  const excluded = observations.filter((o) => !o.measurable);
  const notObserved = excluded.filter((o) => !o.observed).length;
  const notMeasurable = excluded.length - notObserved;

  return (
    <div className="rw-stack">
      <PageHeader
        crumbs={[
          { label: "취약도로 지도", to: "/map" },
          { label: coord(cell.lat, cell.lon) },
        ]}
        title={<span className="rw-num">{coord(cell.lat, cell.lon)}</span>}
        titleAside={<ClassBadge classification={cell.classification} />}
        description={
          <>
            {cell.road_name ?? "도로명 미상"}
            {cell.address ? ` · ${cell.address}` : ""}
            {cell.link_id ? " · ITS 전국표준노드링크로 매핑" : ""}
          </>
        }
        actions={
          <>
            <Link
              to={`/map?cell=${encodeURIComponent(cell.cell_key)}`}
              className="rw-btn rw-btn--secondary"
            >
              지도에서 보기
            </Link>
            <Link
              to={`/inspections?cell=${encodeURIComponent(cell.cell_key)}`}
              className="rw-btn rw-btn--primary"
            >
              현장점검 권고 등록
            </Link>
          </>
        }
      />

      {latest && (
        <Alert
          severity={latest.status === "resolved" ? "done" : "info"}
          title={`이 구간에 등록된 현장점검이 ${inspections.length}건 있습니다`}
          action={<StatusBadge status={latest.status} />}
        >
          {latest.findings.length > 0
            ? `최근 점검 결과: ${latest.findings.join(", ")}`
            : "아직 점검 결과가 입력되지 않았습니다."}
        </Alert>
      )}

      <div className="rw-cols rw-cols--detail">
        <div className="rw-stack">
          {/* ── 세션별 이벤트율 (갈래별) ── */}
          <Card
            title="세션별 이벤트율"
            aside="관측 단위 중복 제거 기준"
            footer={data.family_notice}
          >
            {families.length === 0 ? (
              <Empty>
                측정 가능한 관측이 없습니다. 이벤트가 없었다는 뜻이 아니라, 이
                격자를 지난 세션에 필요한 데이터셋이 없다는 뜻입니다.
              </Empty>
            ) : (
              families.map((f) => {
                const b = by_family[f]!;
                return (
                  <section key={f} className="rw-family">
                    <div className="rw-family__head">
                      <h3 className="rw-family__title">{b.label}</h3>
                      <span className="rw-family__range">
                        {b.sessions.length}개 세션 · {pct(b.min_event_rate)} ~{" "}
                        {pct(b.max_event_rate)}
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
                        variant={variant}
                      />
                    ))}
                  </section>
                );
              })
            )}

            {/* 비교에서 빠지는 세션은 갈래 밖에 따로 세운다 */}
            {excluded.length > 0 && (
              <section className="rw-family">
                <div className="rw-family__head">
                  <h3 className="rw-family__title rw-muted">비교 대상 제외</h3>
                  <span className="rw-family__range">
                    {[
                      notObserved > 0 ? `관측 없음 ${notObserved}개` : null,
                      notMeasurable > 0 ? `측정 불가 ${notMeasurable}개` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </div>
                {excluded.map((o) => (
                  <EventRate
                    key={o.session_id}
                    label={o.session_id}
                    observed={o.observed}
                    measurable={false}
                    eventRate={null}
                    eventCount={null}
                    observationCount={null}
                  />
                ))}
                <p className="rw-note" style={{ marginTop: "var(--rw-space-4)" }}>
                  "측정 불가"는 "이벤트 0%"와 구분되며, 세션 간 비교에서 자동
                  제외됩니다.
                </p>
              </section>
            )}
          </Card>

          {/* ── 이벤트 유형 분포 ── */}
          <Card
            title="이벤트 유형 분포"
            aside={`측정 가능한 세션 합계 ${num(
              primary.reduce((s, p) => s + p.count, 0),
            )}건`}
          >
            {primary.length === 0 ? (
              <Empty>판정에 쓰인 이벤트가 없습니다.</Empty>
            ) : (
              primary.map((p) => (
                <div key={p.key} className="rw-rate">
                  <div className="rw-rate__head">
                    <span>{p.label}</span>
                    <span className="rw-rate__value rw-rate__value--primary">
                      {num(p.count)}건
                    </span>
                  </div>
                  <div className="rw-bar">
                    <div
                      className="rw-bar__fill rw-bar__fill--primary"
                      style={{ width: `${(p.count / maxCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))
            )}

            {/* 참고 지표를 판정 근거처럼 보이게 하면 안 된다 */}
            {reference.length > 0 && (
              <p className="rw-note" style={{ marginTop: "var(--rw-space-5)" }}>
                참고 지표(판정 근거 아님):{" "}
                {reference.map((r) => `${r.label} ${num(r.count)}건`).join(" · ")}
              </p>
            )}
          </Card>

          {/* ── 반복성 판정 근거 ── */}
          <Card title="반복성 판정 근거">
            <p>{repeatEvidence(data)}</p>
            <p className="rw-note" style={{ marginTop: "var(--rw-space-4)" }}>
              {classMeta(cell.classification).description} 원인은 현장 확인 후
              확정됩니다.
            </p>
          </Card>
        </div>

        <div className="rw-stack">
          <ReportCard cellKey={cell.cell_key} />
          <EntityCard cellKey={cell.cell_key} />

          <Card title="도로 속성">
            <div className="rw-dl">
              <dt>도로명</dt>
              <dd>{cell.road_name ?? "—"}</dd>
              <dt>차로 수</dt>
              <dd>{cell.lanes ?? "—"}</dd>
              <dt>제한속도</dt>
              <dd>{cell.max_speed ? `${cell.max_speed}km/h` : "—"}</dd>
              <dt>링크 ID</dt>
              <dd className="rw-mono">{cell.link_id ?? "—"}</dd>
              <dt>링크 거리</dt>
              <dd>{cell.link_dist_m ? `${cell.link_dist_m}m` : "—"}</dd>
              <dt>격자</dt>
              <dd className="rw-mono">{cell.cell_key}</dd>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/** 판정 근거 문장. 있는 수치만 쓰고 없는 값은 지어내지 않는다. */
function repeatEvidence(data: CellDetailData): string {
  const { cell, by_family } = data;
  const families = FAMILY_ORDER.filter((f) => by_family[f]);
  if (families.length === 0) {
    return "측정 가능한 관측이 없어 반복성을 판정하지 않았습니다.";
  }

  const parts = families.map((f) => {
    const b = by_family[f]!;
    const rates = b.sessions.map((s) => pct(s.event_rate)).join(", ");
    return `${familyShort(f)} 갈래에서는 ${b.sessions.length}개 주행의 이벤트율이 ${rates}로 관측되었습니다`;
  });

  const head = `서로 다른 ${cell.session_count ?? 0}개 주행 세션에서 동일 격자가 관측되었습니다. ${parts.join(". ")}.`;

  if (families.length > 1) {
    return `${head} 두 갈래는 이벤트 정의가 다르므로 값을 직접 비교하지 않고 갈래 안에서만 반복성을 봅니다.`;
  }
  return head;
}

/** AI 점검 리포트 초안. 키가 없으면 서버가 템플릿으로 대체하고, 응답의
 *  generated_by 로 어느 쪽인지 밝힌다. 화면도 그대로 표기한다. */
function ReportCard({ cellKey }: { cellKey: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setFailed(null);
    try {
      setReport(await api.report(cellKey));
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "리포트를 만들지 못했습니다");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="AI 점검 리포트 초안"
      aside={
        report ? (
          <span className="rw-badge rw-badge--measured">
            {report.generated_by === "claude"
              ? `생성형 AI · ${report.model}`
              : "규칙 기반 템플릿"}
          </span>
        ) : (
          "생성형 AI"
        )
      }
    >
      {report ? (
        <div className="rw-stack-sm">
          <p style={{ whiteSpace: "pre-wrap" }}>{report.text}</p>
          <p className="rw-note">{report.disclaimer}</p>
          <button
            type="button"
            className="rw-btn rw-btn--secondary rw-btn--sm"
            onClick={generate}
            disabled={busy}
          >
            {busy ? "생성 중…" : "다시 생성"}
          </button>
        </div>
      ) : (
        <div className="rw-stack-sm">
          <p className="rw-aux">
            관측된 사실만으로 점검 우선순위를 제안하는 초안을 만듭니다. 원인은
            진단하지 않습니다.
          </p>
          {failed && <p className="rw-note">{failed}</p>}
          <button
            type="button"
            className="rw-btn rw-btn--primary rw-btn--block"
            onClick={generate}
            disabled={busy}
          >
            {busy ? "생성 중…" : "리포트 초안 생성"}
          </button>
        </div>
      )}
    </Card>
  );
}

/** 표준 응답을 그대로 보여준다. 화면에서 재가공하지 않는 것이 요점이다. */
function EntityCard({ cellKey }: { cellKey: string }) {
  const urn = `urn:ngsi-ld:TrafficEvent:roadwatch:${cellKey}`;
  const { data, loading, error } = useApi(() => api.entity(urn), [urn]);

  return (
    <Card title="TrafficEvent" aside="Part4/R1 정규 표현법">
      {loading && <Loading label="표준 응답을 불러오는 중입니다" />}
      {error && <p className="rw-aux">{error}</p>}
      {data != null && (
        <pre className="rw-code" style={{ maxHeight: 320 }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </Card>
  );
}
