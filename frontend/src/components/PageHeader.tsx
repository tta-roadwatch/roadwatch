import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface Crumb {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: ReactNode;
  /** 제목 옆에 붙는 배지 등 */
  titleAside?: ReactNode;
  description?: ReactNode;
  crumbs?: Crumb[];
  actions?: ReactNode;
}

export function PageHeader({
  title,
  titleAside,
  description,
  crumbs,
  actions,
}: PageHeaderProps) {
  return (
    <div className="rw-page-head">
      <div className="rw-grow">
        {crumbs && crumbs.length > 0 && (
          <nav className="rw-breadcrumb" aria-label="현재 위치">
            {crumbs.map((c, i) => (
              <span key={`${c.label}-${i}`} className="rw-row">
                {i > 0 && (
                  <span className="rw-breadcrumb__sep" aria-hidden="true">
                    ›
                  </span>
                )}
                {c.to ? <Link to={c.to}>{c.label}</Link> : <span>{c.label}</span>}
              </span>
            ))}
          </nav>
        )}

        <div className="rw-row rw-wrap">
          <h1 className="rw-page-title">{title}</h1>
          {titleAside}
        </div>

        {description && (
          <p className="rw-aux" style={{ marginTop: "var(--rw-space-2)" }}>
            {description}
          </p>
        )}
      </div>

      {actions && <div className="rw-row rw-wrap">{actions}</div>}
    </div>
  );
}
