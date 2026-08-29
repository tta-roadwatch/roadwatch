import { NavLink } from "react-router-dom";

export interface Tab {
  to: string;
  label: string;
  end?: boolean;
}

/** 대분류 안의 하위 화면 전환. 목업의 세션 상세 탭 구조를 따른다. */
export function SubTabs({ tabs }: { tabs: Tab[] }) {
  return (
    <nav className="rw-subtabs" aria-label="하위 화면">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} end={t.end} className="rw-subtabs__link">
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
