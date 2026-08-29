import type { ReactNode } from "react";
import { NavLink, Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

/** 상단 메뉴. 목업의 5개 대분류를 그대로 따른다. */
const MENU = [
  { to: "/", label: "대시보드", end: true },
  { to: "/data", label: "데이터" },
  { to: "/map", label: "취약도로 지도" },
  { to: "/inspections", label: "점검 관리" },
  { to: "/standards", label: "표준 · API" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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

          {/* 조회는 로그인 없이 열려 있다. 로그인은 현장점검 등록 권한이므로
              로그인하지 않은 상태도 정상 상태로 다룬다. */}
          <div className="rw-gnb__side">
            <span className="rw-aux">
              {user
                ? `${user.display_name ?? user.username} · ${user.organization ?? ""}`
                : "로그인하지 않음 · 조회만 가능"}
            </span>
            {user ? (
              <button
                type="button"
                className="rw-btn rw-btn--secondary rw-btn--sm"
                onClick={logout}
              >
                로그아웃
              </button>
            ) : (
              <button
                type="button"
                className="rw-btn rw-btn--secondary rw-btn--sm"
                onClick={() => navigate("/login")}
              >
                로그인
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="rw-main">{children}</main>
    </div>
  );
}
