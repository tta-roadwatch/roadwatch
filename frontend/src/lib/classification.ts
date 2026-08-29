/** 3단계 분류의 표기 규칙. 화면마다 다시 정하지 않도록 여기 한 곳에 가둔다.
 *
 * 색 매핑은 의도된 선택이다:
 *   intermittent  → warning  점검 권고
 *   always_manual → gray     후보 아님
 *   low           → success  관찰
 *
 * danger 는 쓰지 않는다. 이 서비스는 원인을 단정하지 않는 것이 설계 원칙이라
 * "주의"는 말하되 "위험"은 말하지 않는다.
 */

export type Classification = "intermittent" | "always_manual" | "low";

/** 분류가 붙지 않은 격자(관측 세션이 부족한 셀)를 가리키는 내부 키 */
export type ClassKey = Classification | "unranked";

export interface ClassMeta {
  key: ClassKey;
  /** 표·범례에 쓰는 짧은 이름 */
  label: string;
  /** 배지에 쓰는 이름 — 판정의 의미까지 담는다 */
  badge: string;
  /** 무엇을 뜻하는지 한 줄 설명 */
  description: string;
  /** 지도 채움색·막대색으로 쓸 시맨틱 변수 이름 */
  fillVar: string;
}

export const CLASS_META: Record<ClassKey, ClassMeta> = {
  intermittent: {
    key: "intermittent",
    label: "점검 권고",
    badge: "간헐 발생 · 점검 권고",
    description: "서로 다른 주행에서 이상 이벤트가 반복 검출된 구간입니다.",
    fillVar: "--rw-intermittent",
  },
  always_manual: {
    key: "always_manual",
    label: "상시 수동",
    badge: "상시 수동 · 후보 아님",
    description:
      "모든 주행에서 수동으로 운행되는 구간입니다. 도로 문제로 보지 않습니다.",
    fillVar: "--rw-manual",
  },
  low: {
    key: "low",
    label: "낮음",
    badge: "낮음 · 관찰",
    description: "이상 이벤트가 드물게 관측된 구간입니다.",
    fillVar: "--rw-low",
  },
  unranked: {
    key: "unranked",
    label: "판정 없음",
    badge: "판정 없음",
    description:
      "반복성을 판정할 만큼 관측 세션이 모이지 않은 구간입니다.",
    fillVar: "--rw-unranked",
  },
};

/** 범례·요약에 고정으로 노출할 순서.
 *
 * always_manual 은 현 데이터에 0곳이지만 범례에서 빼지 않는다. 분류가 비어서가
 * 아니라 그 패턴이 관측되지 않은 것이므로, 빼버리면 "그런 판정은 없다"로
 * 잘못 읽힌다.
 */
export const CLASS_ORDER: Classification[] = [
  "intermittent",
  "always_manual",
  "low",
];

export function classMeta(c: string | null | undefined): ClassMeta {
  if (c && c in CLASS_META) return CLASS_META[c as ClassKey];
  return CLASS_META.unranked;
}
