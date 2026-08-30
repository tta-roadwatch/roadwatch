import type { ElementType, ReactNode } from "react";

import { useInView } from "../lib/reveal";

/** 시야에 들어오면 살짝 올라오며 나타나는 래퍼.
 *
 * 실제 움직임은 CSS(.rw-reveal)가 담당하고 여기서는 클래스만 붙인다 —
 * prefers-reduced-motion 처리를 CSS 와 훅 양쪽에 두면 한쪽만 고쳐질 수 있어
 * 규칙은 한 군데(reveal.ts + landing.css)에 모아둔다.
 *
 * delay 는 같은 줄의 카드들을 순차로 띄울 때 쓴다. 너무 길면 읽는 사람이
 * 기다리게 되므로 0.32초를 넘기지 않는다.
 */
export function Reveal({
  children,
  as: Tag = "div",
  delay = 0,
  className = "",
  ...rest
}: {
  children: ReactNode;
  as?: ElementType;
  delay?: number;
  className?: string;
} & Record<string, unknown>) {
  const { ref, inView } = useInView<HTMLDivElement>();

  return (
    <Tag
      ref={ref}
      className={`rw-reveal${inView ? " is-in" : ""}${className ? ` ${className}` : ""}`}
      style={delay ? { transitionDelay: `${Math.min(delay, 320)}ms` } : undefined}
      {...rest}
    >
      {children}
    </Tag>
  );
}
