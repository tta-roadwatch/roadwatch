/** 분석 갈래의 표기 규칙.
 *
 * BSM 갈래와 조인 갈래는 이벤트 정의가 서로 다르다. BSM 은 비상정지·자율주행
 * 해제 기준이고, 조인은 저속(초당 최저 속도 2.0m/s 미만) 기준이다. 두 갈래를
 * 합쳐 min~max 로 보이면 같은 구간이 "0~100%" 로 읽혀서, 반복성이 있다는
 * 이 서비스의 핵심 주장이 화면에서 무너진다.
 *
 * 그래서 이벤트율은 어느 화면에서든 갈래를 나눠 보여준다.
 */

import type { MetricFamily } from "../api/types";

/** 표·배지에 쓰는 짧은 이름. 서버가 주는 긴 라벨은 카드 제목에 쓴다. */
export const FAMILY_SHORT: Record<MetricFamily, string> = {
  joined: "저속 정체",
  bsm: "비상정지 · 해제",
};

export const FAMILY_ORDER: MetricFamily[] = ["joined", "bsm"];

export function familyShort(f: MetricFamily | null | undefined): string {
  return f ? FAMILY_SHORT[f] : "판정 근거 없음";
}
