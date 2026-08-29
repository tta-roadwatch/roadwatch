import type { Tab } from "../components/SubTabs";

/** '데이터' 대분류의 하위 화면. 세 화면이 같은 탭 줄을 공유한다. */
export const DATA_TABS: Tab[] = [
  { to: "/data", label: "데이터세트 · 세션", end: true },
  { to: "/data/normalization", label: "표준 정규화" },
  { to: "/data/quality", label: "품질검증" },
];
