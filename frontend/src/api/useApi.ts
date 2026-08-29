/** 조회 훅. 화면마다 로딩·오류 처리를 다시 쓰지 않게 한다. */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // fetcher 는 매 렌더 새로 만들어지므로 의존성에 넣지 않는다.
  // 대신 호출부가 넘긴 deps 와 재조회 신호(tick)로만 다시 부른다.
  const run = useCallback(fetcher, deps);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    run()
      .then((v) => {
        if (alive) setData(v);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(
          e instanceof ApiError ? e.message : "알 수 없는 오류가 발생했습니다.",
        );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [run, tick]);

  return { data, loading, error, reload: () => setTick((t) => t + 1) };
}
