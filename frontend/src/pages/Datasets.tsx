import { useState } from "react";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { DatasetMeta } from "../api/types";
import { Alert } from "../components/Alert";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loading } from "../components/States";
import { SubTabs } from "../components/SubTabs";
import { DATA_TABS } from "./dataTabs";
import { dateTime, day, num } from "../lib/format";

/** SCR-02 데이터세트 · 세션.
 *
 * 8개 주행 세션을 TTAK.KO-10.1398 데이터세트로 등록한 메타데이터를 보여준다.
 * 요점은 품질 문제를 감추지 않고 메타데이터로 드러낸다는 것이다 — 파일 라벨의
 * 연도가 실제 수집시각과 어긋나는 세션이 있고, 세션마다 보유 데이터셋이 달라
 * 산출 가능한 지표도 다르다.
 */
export function Datasets() {
  const { data, loading, error, reload } = useApi(() => api.datasets(), []);
  const [open, setOpen] = useState<string | null>(null);

  if (loading) return <Loading label="데이터세트를 불러오는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  const mismatched = data.filter((d) => d.dataQuality.labelMismatch);
  const unmeasurable = data.filter((d) => !d.dataQuality.measurable);
  const inverted = data.filter((d) => d.dataQuality.codebook === "inverted");

  return (
    <div className="rw-stack">
      <PageHeader
        title="데이터세트 · 세션"
        description={`판교 제로시티 주행 세션 ${num(data.length)}개 · TTAK.KO-10.1398 데이터세트 메타데이터`}
      />

      <SubTabs tabs={DATA_TABS} />

      {mismatched.length > 0 && (
        <Alert
          severity="caution"
          title={`파일 라벨의 연도가 실제 수집시각과 다른 세션이 ${mismatched.length}개 있습니다`}
        >
          {mismatched.map((d) => d.identifier).join(", ")} — 수집 시각은 파일명이
          아니라 ss_num(epoch)에서 복원한 실제 값을 사용해 분석했습니다. 감춘 것이
          해당 차이는 메타데이터에 기록했습니다.
        </Alert>
      )}

      <div className="rw-card">
        <div className="rw-stats">
          <Stat label="주행 세션" value={num(data.length)} unit="개" />
          <Stat label="라벨 불일치" value={num(mismatched.length)} unit="개" />
          <Stat label="반대 코드 체계" value={num(inverted.length)} unit="개" />
          <Stat label="측정 불가" value={num(unmeasurable.length)} unit="개" />
        </div>
      </div>

      <Card
        title="세션 목록"
        aside="행을 누르면 데이터세트 메타데이터를 펼칩니다"
        flush
        footer="산출 가능한 지표가 없는 세션은 '이벤트 0%'가 아니라 '측정 불가'입니다. 세션마다 보유 데이터셋이 다르기 때문입니다."
      >
        <div className="rw-table-wrap">
          <table className="rw-table">
            <thead>
              <tr>
                <th scope="col">세션</th>
                <th scope="col">실제 수집 시각</th>
                <th scope="col">파일 라벨</th>
                <th scope="col">원본 파일</th>
                <th scope="col">산출 가능 지표</th>
                <th scope="col">코드 체계</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <DatasetRow
                  key={d.id}
                  meta={d}
                  open={open === d.id}
                  onToggle={() => setOpen(open === d.id ? null : d.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function DatasetRow({
  meta,
  open,
  onToggle,
}: {
  meta: DatasetMeta;
  open: boolean;
  onToggle: () => void;
}) {
  const q = meta.dataQuality;

  return (
    <>
      <tr data-clickable="true" onClick={onToggle}>
        <th scope="row" className="rw-bold">
          {meta.identifier}
        </th>
        <td className="rw-num">{dateTime(meta.temporal.startDate)}</td>
        <td className="rw-num">
          <span className={q.labelMismatch ? "rw-muted" : undefined}>
            {day(q.labelDate)}
          </span>
          {q.labelMismatch && (
            <span
              className="rw-badge rw-badge--intermittent"
              style={{ marginLeft: "var(--rw-space-2)" }}
            >
              불일치
            </span>
          )}
        </td>
        <td className="rw-num">{meta.distribution.length}개</td>
        <td>
          {q.measurable ? (
            meta.keyword.join(", ")
          ) : (
            <span className="rw-badge rw-badge--unranked">측정 불가</span>
          )}
        </td>
        <td>
          {q.codebook === "inverted" ? (
            <span className="rw-badge rw-badge--intermittent">반대 체계</span>
          ) : (
            <span className="rw-aux">{q.codebook ?? "—"}</span>
          )}
        </td>
      </tr>

      {open && (
        <tr>
          <td colSpan={6} className="rw-table__detail">
            <div className="rw-stack-sm">
              <p className="rw-aux">{meta.description}</p>

              <div className="rw-dl">
                <dt>식별자</dt>
                <dd className="rw-mono">{meta.id}</dd>
                <dt>제공기관</dt>
                <dd>{meta.publisher}</dd>
                <dt>이용조건</dt>
                <dd>{meta.license}</dd>
                <dt>수집 구간</dt>
                <dd>
                  {dateTime(meta.temporal.startDate)} ~{" "}
                  {dateTime(meta.temporal.endDate)}
                </dd>
                <dt>공간 범위</dt>
                <dd>{meta.spatial.placeName}</dd>
              </div>

              {/* 품질 메모는 서버가 실측 결과로 써서 내려준다. 있는 것만 보인다. */}
              {[q.labelMismatchNote, q.codebookNote, q.measurableNote]
                .filter(Boolean)
                .map((note) => (
                  <p key={note} className="rw-note">
                    {note}
                  </p>
                ))}

              <div>
                <p className="rw-label">원본 파일</p>
                <ul className="rw-aux">
                  {meta.distribution.map((f) => (
                    <li key={f.title} className="rw-mono">
                      {f.title}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
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
