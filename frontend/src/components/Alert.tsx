import type { ReactNode } from "react";

/** KRDS critical_alerts 패턴.
 *
 * 흰 배경 + 테두리 + 그림자 + 좌측 심각도 배지로만 구성한다. 배경을 색으로
 * 채우거나 본문 텍스트를 색으로 물들이지 않는다 — 색은 배지 하나가 진다.
 *
 * 심각도에 danger 가 없는 것은 누락이 아니다. 이 서비스는 원인을 단정하지
 * 않으므로 "주의(caution)"까지만 말한다.
 */
type Severity = "info" | "caution" | "done";

const BADGE_LABEL: Record<Severity, string> = {
  info: "안내",
  caution: "주의",
  done: "완료",
};

interface AlertProps {
  severity?: Severity;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}

export function Alert({ severity = "info", title, children, action }: AlertProps) {
  return (
    <div className="rw-alert" role={severity === "caution" ? "alert" : "status"}>
      <span className={`rw-alert__badge rw-alert__badge--${severity}`}>
        {BADGE_LABEL[severity]}
      </span>
      <div className="rw-alert__body">
        <p className="rw-alert__title">{title}</p>
        {children && <p className="rw-alert__text">{children}</p>}
      </div>
      {action && <div className="rw-alert__action">{action}</div>}
    </div>
  );
}
