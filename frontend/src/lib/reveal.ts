import { useEffect, useRef, useState } from "react";

/** 스크롤에 따라 나타나는 효과.
 *
 * 랜딩은 위에서 아래로 읽는 화면이라, 요소가 시야에 들어올 때 살짝 올라오면
 * 읽는 흐름이 생긴다. 업무 화면에는 쓰지 않는다 — 매일 쓰는 화면에서 매번
 * 기다리게 하는 건 방해다.
 *
 * 접근성: prefers-reduced-motion 을 켠 사용자에게는 효과 없이 즉시 보인다.
 * 전정기관에 민감한 사람에게 움직임은 불편을 넘어 어지럼증을 유발한다.
 * 정부 디지털 서비스 기준(KRDS)을 따르는 화면이므로 선택이 아니라 요건이다.
 */

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

/** 요소가 시야에 들어왔는지. 한 번 보이면 계속 보인 상태로 둔다 —
 * 위아래로 스크롤할 때마다 다시 사라지면 성가시다. */
export function useInView<T extends HTMLElement>(rootMargin = "-64px") {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(() => prefersReducedMotion());

  useEffect(() => {
    if (prefersReducedMotion()) {
      setInView(true);
      return;
    }
    const el = ref.current;
    // IntersectionObserver 가 없는 환경에서는 그냥 보여준다.
    // 효과가 없는 것보다 내용이 안 보이는 게 훨씬 나쁘다.
    if (!el || typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [rootMargin]);

  return { ref, inView };
}

/** 숫자가 올라가는 효과.
 *
 * 843,734 가 처음부터 박혀 있으면 그냥 글자지만, 올라가면 "이만큼을 봤다"는
 * 감각이 생긴다. 끝값은 항상 정확히 목표값으로 맞춘다 — 근사치로 끝나면
 * 화면에 틀린 숫자가 남는다.
 */
export function useCountUp(target: number, active: boolean, ms = 1100): number {
  const [value, setValue] = useState(() =>
    prefersReducedMotion() ? target : 0,
  );

  useEffect(() => {
    if (!active) return;
    if (prefersReducedMotion()) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      // ease-out — 빠르게 오르다 끝에서 잦아든다
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setValue(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, ms]);

  return value;
}
