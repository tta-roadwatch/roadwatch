import { prefersReducedMotion } from "../lib/reveal";

/** 랜딩 Hero 일러스트 — 서비스가 무엇을 하는지 그림 하나로.
 *
 * 실제 지도 스크린샷을 쓰다가 바꿨다. 스크린샷은 정보가 많아 «무엇을 하는
 * 서비스인가»가 한눈에 안 들어온다. 여기서 필요한 건 정확한 지도가 아니라
 * 개념이다 — 서로 다른 날 지나간 차들이 **같은 자리**에서 걸렸다는 것.
 *
 * 이미지 파일 대신 SVG 로 그린다. 용량이 거의 없고, 어떤 해상도에서도
 * 선명하며, 색을 KRDS 토큰에서 직접 가져올 수 있다 — 화면 색이 바뀌면
 * 그림도 같이 바뀐다.
 *
 * 셋을 겹쳐 두는 것이 이 그림의 전부다. 차 세 대가 다른 색인 것은 서로 다른
 * 주행이라는 뜻이고, 그 셋이 같은 지점에서 노란 격자를 만난다.
 */
export function RoadIllustration() {
  // SVG 의 animateMotion·animate 는 CSS prefers-reduced-motion 으로 끌 수 없다.
  // 여기서 판별해 정지된 그림으로 그린다 — 움직임만 빠지고 내용은 그대로다.
  const still = prefersReducedMotion();

  return (
    <svg
      className="rw-lp-illust"
      viewBox="0 0 1200 300"
      role="img"
      aria-label="서로 다른 세 번의 주행이 같은 도로 구간에서 반복해 이상을 겪는 모습을 나타낸 그림"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        {/* 도로가 화면 밖으로 자연스럽게 빠지도록 양 끝을 흐린다 */}
        <linearGradient id="rw-fade" x1="0" x2="1">
          <stop offset="0" stopColor="var(--rw-bg)" stopOpacity="0.9" />
          <stop offset="0.05" stopColor="var(--rw-bg)" stopOpacity="0" />
          <stop offset="0.95" stopColor="var(--rw-bg)" stopOpacity="0" />
          <stop offset="1" stopColor="var(--rw-bg)" stopOpacity="0.9" />
        </linearGradient>

        <path
          id="rw-road-path"
          d="M -40 232 C 230 232, 300 96, 570 96 C 840 96, 910 208, 1240 208"
        />
      </defs>

      {/* ── 배경의 옅은 격자 — 40m 격자를 암시한다 ── */}
      <g opacity="0.5">
        {Array.from({ length: 16 }, (_, i) => (
          <line
            key={`v${i}`}
            x1={i * 80}
            y1="0"
            x2={i * 80}
            y2="300"
            stroke="var(--rw-border)"
            strokeWidth="1"
          />
        ))}
        {Array.from({ length: 5 }, (_, i) => (
          <line
            key={`h${i}`}
            x1="0"
            y1={i * 75}
            x2="1200"
            y2={i * 75}
            stroke="var(--rw-border)"
            strokeWidth="1"
          />
        ))}
      </g>

      {/* ── 도로 ── */}
      <use
        href="#rw-road-path"
        fill="none"
        stroke="var(--rw-unranked)"
        strokeWidth="64"
        strokeLinecap="round"
      />
      <use
        href="#rw-road-path"
        fill="none"
        stroke="var(--rw-surface-sunken)"
        strokeWidth="56"
        strokeLinecap="round"
      />
      {/* 가운데 차선 */}
      <use
        href="#rw-road-path"
        fill="none"
        stroke="var(--rw-unranked)"
        strokeWidth="3"
        strokeDasharray="18 20"
        strokeLinecap="round"
      />

      {/* ── 반복 검출 구간 ──
          도로 위 같은 자리에 격자 셀이 겹친다. 이 서비스가 찾아내는 것. */}
      <g className="rw-lp-illust__cells">
        <Cell x={498} y={78} delay={0} />
        <Cell x={536} y={78} delay={0.18} />
        <Cell x={574} y={78} delay={0.36} />
      </g>

      {/* 검출 지점을 가리키는 표식 */}
      <g className="rw-lp-illust__pin">
        <line
          x1="554"
          y1="34"
          x2="554"
          y2="72"
          stroke="var(--rw-intermittent-text)"
          strokeWidth="2"
          strokeDasharray="4 4"
        />
        <circle cx="554" cy="26" r="7" fill="var(--rw-intermittent-text)" />
        <circle cx="554" cy="26" r="14" fill="var(--rw-intermittent-text)" opacity="0.22">
          {!still && (
            <>
              <animate
                attributeName="r"
                values="13;20;13"
                dur="2.4s"
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values="0.22;0;0.22"
                dur="2.4s"
                repeatCount="indefinite"
              />
            </>
          )}
        </circle>
      </g>

      {/* ── 서로 다른 세 주행 ──
          같은 길을 다른 날 지나간 차들. 색이 다른 것이 요점이다. */}
      <Car color="var(--rw-traj-1)" begin="0s" still={still} at={[300, 176, -30]} />
      <Car color="var(--rw-traj-2)" begin="-2.6s" still={still} at={[730, 112, 16]} />
      <Car color="var(--rw-traj-3)" begin="-5.2s" still={still} at={[1020, 200, 6]} />

      {/* 양 끝을 배경색으로 덮어 도로가 잘린 티가 안 나게 한다 */}
      <rect width="1200" height="300" fill="url(#rw-fade)" />
    </svg>
  );
}

/** 격자 셀 하나. 순서대로 나타나 «반복해서 걸렸다»를 시간으로 보인다. */
function Cell({
  x,
  y,
  delay,
  tone = "warn",
}: {
  x: number;
  y: number;
  delay: number;
  tone?: "warn" | "low";
}) {
  const fill =
    tone === "warn" ? "var(--rw-intermittent)" : "var(--rw-low)";
  const stroke =
    tone === "warn" ? "var(--rw-intermittent-text)" : "var(--rw-low-text)";
  return (
    <rect
      x={x}
      y={y}
      width="32"
      height="32"
      rx="4"
      fill={fill}
      stroke={stroke}
      strokeWidth="1.5"
      opacity="0"
      style={{ animationDelay: `${delay}s` }}
    />
  );
}

/** 도로를 따라 달리는 차. 위에서 본 모습이라 지도와 시점이 같다.
 *
 * still 이면 움직이지 않고 at 좌표에 세워 둔다. 세 대가 도로 위 서로 다른
 * 지점에 놓이므로 «여러 주행»이라는 뜻은 그대로 전달된다. */
function Car({
  color,
  begin,
  still,
  at,
}: {
  color: string;
  begin: string;
  still: boolean;
  at: [number, number, number];
}) {
  return (
    <g
      className="rw-lp-illust__car"
      transform={still ? `translate(${at[0]},${at[1]}) rotate(${at[2]})` : undefined}
    >
      <g transform="translate(-18,-11)">
        <rect width="36" height="22" rx="6" fill={color} />
        {/* 앞유리 — 진행 방향을 알 수 있게 한쪽에만 둔다 */}
        <rect x="22" y="4.5" width="9" height="13" rx="3" fill="var(--rw-surface)" opacity="0.85" />
        <circle cx="10" cy="11" r="3" fill="var(--rw-surface)" opacity="0.5" />
      </g>
      {!still && (
        <animateMotion
          dur="7.8s"
          repeatCount="indefinite"
          rotate="auto"
          begin={begin}
          keyPoints="0;1"
          keyTimes="0;1"
          calcMode="linear"
        >
          <mpath href="#rw-road-path" />
        </animateMotion>
      )}
    </g>
  );
}
