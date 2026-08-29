import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, setAuthToken, setUnauthorizedHandler } from "../api/client";
import type { AuthUser, LoginResponse } from "../api/types";

/** 토큰 보관 위치.
 *
 * localStorage 를 쓴다. 시연 도중 새로고침이나 탭 이동으로 로그인이 풀리면
 * 흐름이 끊기기 때문이다. 토큰 수명은 서버가 12시간으로 제한한다.
 */
const STORAGE_KEY = "roadwatch.token";

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    // 시크릿 창이나 저장소가 막힌 환경에서도 화면은 떠야 한다
    return null;
  }
}

function writeStoredToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* 저장 못 해도 이번 세션 동안은 메모리의 토큰으로 동작한다 */
  }
}

interface AuthState {
  user: AuthUser | null;
  /** 저장된 토큰을 확인하는 동안 true. 이 사이에 로그인 화면을 깜빡이지 않는다. */
  restoring: boolean;
  login: (username: string, password: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [restoring, setRestoring] = useState(true);

  const logout = useCallback(() => {
    setAuthToken(null);
    writeStoredToken(null);
    setUser(null);
  }, []);

  const accept = useCallback((res: LoginResponse) => {
    setAuthToken(res.access_token);
    writeStoredToken(res.access_token);
    setUser(res.user);
  }, []);

  // 토큰이 만료되면 어느 화면에 있든 로그인 상태를 정리한다
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // 새로고침 후 복원. 저장된 토큰이 아직 유효한지 서버에 물어본다.
  useEffect(() => {
    const token = readStoredToken();
    if (!token) {
      setRestoring(false);
      return;
    }
    setAuthToken(token);
    let alive = true;
    api
      .me()
      .then((u) => {
        if (alive) setUser(u);
      })
      .catch(() => {
        if (alive) logout();
      })
      .finally(() => {
        if (alive) setRestoring(false);
      });
    return () => {
      alive = false;
    };
  }, [logout]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      restoring,
      login: async (username, password) => accept(await api.login(username, password)),
      demoLogin: async () => accept(await api.demoLogin()),
      logout,
    }),
    [user, restoring, accept, logout],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider 안에서만 사용할 수 있습니다");
  return v;
}
