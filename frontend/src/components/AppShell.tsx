import type { ReactNode } from "react";
import { NavLink, Link } from "react-router-dom";

/** 상단 메뉴. 목업의 5개 대분류를 그대로 따른다. */
const MENU = [
  { to: "/", label: "대시보드", end: true },
  { to: "/data", label: "데이터" },
  { to: "/map", label: "취약도로 지도" },
  { to: "/inspections", label: "점검 관리" },
  { to: "/standards", label: "표준 · API" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="rw-shell">
      <header className="rw-gnb">
        <div className="rw-gnb__inner">
          <Link to="/" className="rw-gnb__brand">
            <span className="rw-gnb__mark" aria-hidden="true">
              RW
            </span>
            자율주행 취약도로 탐지
          </Link>

          <nav className="rw-gnb__menu" aria-label="주요 메뉴">
            {MENU.map((m) => (
              <NavLink key={m.to} to={m.to} end={m.end} className="rw-gnb__link">
                {m.label}
              </NavLink>
            ))}
          </nav>

          <div className="rw-gnb__side">
            <span className="rw-aux">경기도자율주행센터</span>
            <Link to="/login" className="rw-btn rw-btn--secondary rw-btn--sm">
              로그아웃
            </Link>
          </div>
        </div>
      </header>

      <main className="rw-main">{children}</main>
    </div>
  );
}
