import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  /** 제목 오른쪽에 놓는 보조 정보나 동작 */
  aside?: ReactNode;
  /** 표를 담을 때는 모서리까지 닿게 패딩을 없앤다 */
  flush?: boolean;
  footer?: ReactNode;
  children: ReactNode;
}

export function Card({ title, aside, flush, footer, children }: CardProps) {
  return (
    <section className="rw-card">
      {(title || aside) && (
        <header className="rw-card__head">
          {title && <h2 className="rw-card-title">{title}</h2>}
          {aside && <div className="rw-aux">{aside}</div>}
        </header>
      )}
      <div className={`rw-card__body${flush ? " rw-card__body--flush" : ""}`}>
        {children}
      </div>
      {footer && <footer className="rw-card__foot">{footer}</footer>}
    </section>
  );
}
