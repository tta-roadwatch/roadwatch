import { useState } from "react";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Alert } from "../components/Alert";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { SubTabs } from "../components/SubTabs";
import { Toggle } from "../components/Toggle";
import { DATA_TABS } from "./dataTabs";
import { num } from "../lib/format";

/** SCR-03 표준 정규화 — 데모 하이라이트.
 *
 * 토글 하나로 15,585건의 판정이 뒤집히는 장면이 이 화면의 전부다. 같은 TTA
 * 표준 필드인데 세션마다 코드 체계가 반대라서, 코드북을 적용하지 않으면
 * BSM 전 구간이 "비상정지 발생"으로 잘못 판정된다.
 *
 * 수치는 파이프라인이 실행 중 실측해 고정한 값이고, 화면은 그걸 그대로 쓴다.
 */
export function Normalization() {
  // 기본은 적용(ON) 상태다. 끄는 동작이 "정규화를 빼면 이렇게 된다"를 보이는
  // 실험이지, 꺼진 게 기본값은 아니다.
  const [applied, setApplied] = useState(true);

  const { data, loading, error, reload } = useApi(() => api.normalization(), []);

  if (loading) return <Loading label="정규화 결과를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  const n = data.normalization;
  const invertedSessions = data.sessions.filter((s) => s.inverted);
  const flags = [...n.emergency_flags, "vhcl_sttus_flg"];

  return (
    <div className="rw-stack">
      <PageHeader
        title="표준 정규화"
        description={`${n.source} · 세션별 코드북을 적용해 판정을 바로잡습니다`}
        crumbs={[{ label: "데이터", to: "/data" }, { label: "표준 정규화" }]}
      />

      <SubTabs tabs={DATA_TABS} />

      <Alert
        severity="caution"
        title={`플래그 코드 체계가 반대인 세션이 ${invertedSessions.length}개 있습니다`}
        action={
          <Toggle
            checked={applied}
            onChange={setApplied}
            label="표준 정규화"
          />
        }
      >
        {n.explanation}
      </Alert>

      {/* 토글이 뒤집는 대상. 숫자 두 개가 화면에서 실제로 바뀐다. */}
      <Card
        title="비상정지 판정 건수"
        aside={`${n.source} 기준`}
        footer={
          applied
            ? `세션별 코드북을 적용해 ${num(n.corrected)}건의 오판을 제거했습니다.`
            : `정규화를 적용하지 않으면 ${num(n.corrected)}건이 잘못 판정됩니다.`
        }
      >
        <div className="rw-flip">
          <div className="rw-figure">
            <p className="rw-figure__label">정규화 미적용</p>
            <p className="rw-figure__value rw-figure__value--wrong">
              {num(n.without_codebook)}건
            </p>
            <p className="rw-figure__foot">
              모든 세션에 같은 코드 체계를 가정한 결과입니다.
            </p>
          </div>

          <span className="rw-flip__arrow" aria-hidden="true">
            →
          </span>

          <div className="rw-figure">
            <p className="rw-figure__label">정규화 적용</p>
            <p
              className={
                applied
                  ? "rw-figure__value rw-figure__value--right"
                  : "rw-figure__value rw-muted"
              }
            >
              {applied ? `${num(n.with_codebook)}건` : "—"}
            </p>
            <p className="rw-figure__foot">
              {applied
                ? "세션별 코드북을 적용한 실제 판정입니다."
                : "토글을 켜면 코드북을 적용한 결과를 보여줍니다."}
            </p>
          </div>
        </div>
      </Card>

      <div className="rw-cols rw-cols--2">
        <Card title="원본 BSM" aside="공간데이터마켓 원본">
          <pre className="rw-code">
            {JSON.stringify(n.example.raw, null, 2)}
          </pre>
          <p className="rw-note" style={{ marginTop: "var(--rw-space-4)" }}>
            {n.example.session_id} 세션 · {n.example.raw_note}
          </p>
        </Card>

        <Card
          title={applied ? "정규화 결과 · NGSI-LD" : "정규화 없이 해석하면"}
          aside={applied ? "TTAK.KO-10.1331-Part4/R1" : "잘못된 판정"}
        >
          <pre className="rw-code">
            {applied
              ? JSON.stringify(n.example.normalized, null, 2)
              : JSON.stringify(wrongReading(n.example.raw), null, 2)}
          </pre>
          <p className="rw-note" style={{ marginTop: "var(--rw-space-4)" }}>
            {applied
              ? "세션 코드북을 적용해 값이 false 로 판정됩니다. 오판 0건."
              : `이 세션에서는 1이 정상인데 발생으로 읽어 ${num(n.corrected)}건이 뒤집힙니다.`}
          </p>
        </Card>
      </div>

      <Card
        title="세션별 코드북"
        aside={`'발생'을 뜻하는 값 · 3개 세션 중 ${invertedSessions.length}개가 반대 체계`}
        flush
      >
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">세션</th>
                {flags.map((f) => (
                  <th scope="col" key={f} className="rw-mono">
                    {f}
                  </th>
                ))}
                <th scope="col">판정</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(n.session_codebook).map(([sid, book]) => {
                const abnormal = n.codebooks[book]?.abnormal ?? {};
                const inverted = book === "inverted";
                return (
                  <tr key={sid}>
                    <th scope="row" className="rw-bold">
                      {sid}
                    </th>
                    {flags.map((f) => (
                      <td key={f} className="rw-mono">
                        {(abnormal[f] ?? []).join(", ") || "—"}
                      </td>
                    ))}
                    <td className={inverted ? "rw-bold" : "rw-aux"}>
                      {inverted ? "반대 체계 → 반전 적용" : "표준 체계"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="좌표 유효성" aside="BSM 전체">
        <div className="rw-dl">
          <dt>유효 좌표</dt>
          <dd>{num(data.coord_validity.valid)}건</dd>
          <dt>전체</dt>
          <dd>{num(data.coord_validity.total)}건</dd>
          <dt>유효율</dt>
          <dd>{(data.coord_validity.rate * 100).toFixed(1)}%</dd>
        </div>
      </Card>
    </div>
  );
}

/** 정규화를 적용하지 않았을 때의 잘못된 해석. 토글 OFF 상태에서 보여준다.
 *
 * 원본의 1 을 그대로 "발생"으로 읽은 결과다. 화면에서 무엇이 뒤집히는지
 * 눈으로 보이게 하려는 것이지, 실제 판정 경로가 아니다.
 */
function wrongReading(raw: Record<string, number>): Record<string, unknown> {
  const NAME: Record<string, string> = {
    mnl_emg_flg: "manualEmergencyStop",
    auto_emg_flg: "automaticEmergencyStop",
    snsr_trb_flg: "sensorTrouble",
  };
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw)) {
    out[NAME[k] ?? k] = { type: "Property", value: v === 1 };
  }
  return out;
}
