import { num, pct } from "../lib/format";
import type { ClassKey } from "../lib/classification";

/** 세션별 이벤트율 한 줄.
 *
 * 이 컴포넌트의 존재 이유는 "측정 불가"와 "이벤트 0%"를 절대 같은 모양으로
 * 그리지 않기 위해서다. 세션마다 보유 데이터셋이 달라 산출 가능한 지표가
 * 다르므로, 값이 없는 것은 이벤트가 없었다는 뜻이 아니다.
 *
 *   관측 없음  — 이 세션이 해당 격자를 지나지 않았다
 *   측정 불가  — 지나갔지만 필요한 데이터셋이 없어 산출할 수 없다
 *   0.0%       — 산출했고 이벤트가 실제로 없었다
 */
interface EventRateProps {
  label: string;
  observed: boolean;
  measurable: boolean;
  eventRate: number | null;
  eventCount: number | null;
  observationCount: number | null;
  variant?: ClassKey | "primary";
  /** 측정 불가 사유를 덧붙일 때 */
  note?: string;
}

export function EventRate({
  label,
  observed,
  measurable,
  eventRate,
  eventCount,
  observationCount,
  variant = "intermittent",
  note,
}: EventRateProps) {
  const usable = observed && measurable && eventRate !== null;

  const status = !observed ? "관측 없음" : !measurable ? "측정 불가" : null;

  return (
    <div className="rw-rate">
      <div className="rw-rate__head">
        <span className={usable ? "" : "rw-muted"}>{label}</span>
        <span
          className={
            usable
              ? `rw-rate__value rw-rate__value--${variant}`
              : "rw-rate__value rw-rate__value--none"
          }
        >
          {usable ? pct(eventRate) : status}
        </span>
      </div>

      <div className={`rw-bar${usable ? "" : " rw-bar--unmeasurable"}`}>
        {usable && (
          <div
            className={`rw-bar__fill rw-bar__fill--${variant}`}
            style={{ width: `${Math.min(100, (eventRate ?? 0) * 100)}%` }}
          />
        )}
      </div>

      <p className="rw-rate__foot rw-aux">
        {usable
          ? `${num(eventCount)} / ${num(observationCount)}초`
          : note || (observed ? "해당 세션에 필요한 데이터셋이 없습니다" : "이 세션은 해당 구간을 지나지 않았습니다")}
      </p>
    </div>
  );
}
