import { classMeta } from "../lib/classification";
import type { InspectionStatus } from "../api/types";

/** 3단계 분류 배지. 색 결정은 classification.ts 한 곳에서만 한다. */
export function ClassBadge({
  classification,
  short = false,
}: {
  classification: string | null | undefined;
  short?: boolean;
}) {
  const meta = classMeta(classification);
  return (
    <span className={`rw-badge rw-badge--${meta.key}`} title={meta.description}>
      {short ? meta.label : meta.badge}
    </span>
  );
}

const STATUS_LABEL: Record<InspectionStatus, string> = {
  recommended: "권고",
  inspecting: "점검 중",
  resolved: "조치 완료",
  not_applicable: "해당 없음",
};

/** 점검 상태 배지.
 *
 * 권고는 아직 사람이 확인하지 않은 시스템 판정이므로 분류와 같은 warning 계열,
 * 진행 중은 primary, 완료는 success, 해당 없음(사람이 오탐으로 내린 것)은 gray.
 */
const STATUS_VARIANT: Record<InspectionStatus, string> = {
  recommended: "intermittent",
  inspecting: "primary",
  resolved: "low",
  not_applicable: "always_manual",
};

export function StatusBadge({ status }: { status: InspectionStatus }) {
  return (
    <span className={`rw-badge rw-badge--${STATUS_VARIANT[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

export { STATUS_LABEL };

/** 실측인지 시뮬레이션인지 밝히는 배지. SCR-08 에서 여러 곳에 반복해 붙는다. */
export function SimulationBadge({ simulated }: { simulated: boolean }) {
  return simulated ? (
    <span className="rw-badge rw-badge--simulated">시뮬레이션</span>
  ) : (
    <span className="rw-badge rw-badge--measured">실측값</span>
  );
}
