/** 주행 궤적의 세션별 색.
 *
 * 지도(MapLibre match 식)와 범례가 각자 색을 정하면 어긋난다. 범례에서
 * 순서(index)로 색을 매기면 API 응답 순서가 바뀌는 순간 지도와 달라지므로,
 * 세션 ID 를 키로 한 곳에서 정한다.
 *
 * 분류 색(warning·success)과 겹치지 않게 primary 계열을 쓴다. 세션을 구분하는
 * 게 목적이지 심각도를 뜻하지 않는다.
 */
const COLORS: Record<string, string> = {
  "2022-05-16": "--rw-traj-1",
  "2022-07-25": "--rw-traj-2",
  "2022-08-05": "--rw-traj-3",
};

const FALLBACK = "--rw-traj-other";

export function trajColorVar(sessionId: string): string {
  return COLORS[sessionId] ?? FALLBACK;
}

export const TRAJ_COLOR_ENTRIES = Object.entries(COLORS);
