/** 표기 형식. 수치 반올림은 API 와 반드시 같아야 한다. */

/** 비율(0~1) → 백분율 숫자. 반올림은 half-up 이다.
 *
 * 백엔드는 Decimal(ROUND_HALF_UP) 으로 81.25 를 81.3 으로 올린다. JS 의
 * toFixed 는 이진 표현에 따라 81.2 를 낼 수 있어, 같은 값이 API 응답과
 * 화면에서 다르게 보인다. 그래서 직접 half-up 으로 맞춘다.
 */
export function pctValue(rate: number): number {
  return Math.round(rate * 100 * 10) / 10;
}

/** 비율 → "82.8%" 문자열. 정수로 떨어지면 소수점을 떼어 "100%" 로 쓴다. */
export function pct(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return "—";
  const v = pctValue(rate);
  return `${Number.isInteger(v) ? v : v.toFixed(1)}%`;
}

/** 천 단위 구분 */
export function num(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return n.toLocaleString("ko-KR");
}

/** ISO 문자열 → "2022-05-16" */
export function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("sv-SE");
}

/** ISO 문자열 → "2022-05-16 12:43" */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString("sv-SE")} ${d.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })}`;
}

/** 위경도 → "37.40350, 127.10479" — 목업의 구간 표기 형식 */
export function coord(lat: number, lon: number): string {
  return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
}
