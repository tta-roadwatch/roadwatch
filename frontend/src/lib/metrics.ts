/** 이벤트 유형 표기.
 *
 * 파이프라인은 참고 지표에 'ref:' 접두사를 붙여 기록한다. 판정 근거가 아닌
 * 신호를 근거처럼 보여주면 안 되므로 화면에서도 갈라 놓는다.
 */

const LABEL: Record<string, string> = {
  low_speed: "저속 정체",
  state_deviation: "주행상태 코드 이탈",
  obstacle_density: "경로 장애물 밀집",
  emergency: "비상정지",
  autonomy_disengage: "자율주행 해제",
};

export interface EventTypeCount {
  key: string;
  label: string;
  count: number;
  /** 판정 근거가 아니라 참고로만 본 지표 */
  reference: boolean;
}

export function metricLabel(key: string): string {
  return LABEL[key] ?? key;
}

/** 세션별 event_types 를 합산해 판정용·참고용으로 나눈다. */
export function tallyEventTypes(
  observations: { event_types: Record<string, number> | null }[],
): { primary: EventTypeCount[]; reference: EventTypeCount[] } {
  const totals = new Map<string, { count: number; reference: boolean }>();

  for (const o of observations) {
    for (const [raw, n] of Object.entries(o.event_types ?? {})) {
      const reference = raw.startsWith("ref:");
      const key = reference ? raw.slice(4) : raw;
      const prev = totals.get(key);
      if (prev) {
        prev.count += n;
        // 한 번이라도 판정 근거로 쓰였으면 참고용이 아니다
        prev.reference = prev.reference && reference;
      } else {
        totals.set(key, { count: n, reference });
      }
    }
  }

  const rows: EventTypeCount[] = [...totals.entries()]
    .map(([key, v]) => ({ key, label: metricLabel(key), ...v }))
    .sort((a, b) => b.count - a.count);

  return {
    primary: rows.filter((r) => !r.reference),
    reference: rows.filter((r) => r.reference),
  };
}
