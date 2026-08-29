import type { ReactNode } from "react";

export function Loading({ label = "불러오는 중입니다" }: { label?: string }) {
  return (
    <div className="rw-state" role="status">
      <div className="rw-spinner" aria-hidden="true" />
      <p className="rw-aux">{label}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rw-state" role="alert">
      <p className="rw-bold">{message}</p>
      {onRetry && (
        <button type="button" className="rw-btn rw-btn--secondary rw-btn--sm" onClick={onRetry}>
          다시 시도
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rw-state">
      <p className="rw-aux">{children}</p>
    </div>
  );
}
