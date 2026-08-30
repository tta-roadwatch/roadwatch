import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Logo } from "../components/Logo";
import { Loading } from "../components/States";

/** 로그인 화면.
 *
 * 조회는 인증 없이 열려 있고 현장점검 등록만 로그인이 필요하다. 그래서 이
 * 화면은 관문이 아니라 쓰기 권한을 얻는 곳이다.
 *
 * `테스트 로그인` 은 인증을 건너뛰는 우회 경로가 아니라 데모 계정으로 정상
 * 발급받는 버튼이다. 서버가 데모 계정 유무를 알려주므로, 운영에서 계정을
 * 지우면 버튼도 자동으로 사라진다.
 */
export function Login() {
  const { user, restoring, login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // 링크를 받아 열었다가 로그인으로 튕긴 경우 원래 가려던 곳으로 돌려보낸다.
  // 없으면 대시보드가 기본이다.
  const from =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ??
    "/dashboard";
  const config = useApi(() => api.authConfig(), []);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (restoring) return <Loading label="로그인 상태를 확인하는 중입니다" />;
  if (user) return <Navigate to={from} replace />;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "로그인에 실패했습니다");
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void run(() => login(username, password));
  };

  return (
    <div className="rw-login">
      <div className="rw-login__panel">
        <Link to="/" className="rw-login__brand">
          <Logo size={40} />
          <div>
            {/* 서비스명만 두면 처음 보는 사람이 무슨 서비스인지 알 수 없다.
                로그인은 외부에서 처음 닿는 화면이라 부제에 설명을 남긴다.
                로고를 누르면 랜딩으로 나간다 — 막다른 화면이 아니다. */}
            <h1 className="rw-card-title">RoadWatch</h1>
            <p className="rw-aux">자율주행 취약도로 탐지 · 도로관리 담당자용</p>
          </div>
        </Link>

        <form className="rw-stack" onSubmit={submit}>
          <div className="rw-field">
            <label className="rw-label" htmlFor="username">
              아이디
            </label>
            <input
              id="username"
              className="rw-input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="rw-field">
            <label className="rw-label" htmlFor="password">
              비밀번호
            </label>
            <input
              id="password"
              type="password"
              className="rw-input"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <Alert severity="caution" title="로그인하지 못했습니다">
              {error}
            </Alert>
          )}

          <button
            type="submit"
            className="rw-btn rw-btn--primary rw-btn--block"
            disabled={busy}
          >
            {busy ? "확인 중…" : "로그인"}
          </button>

          {config.data?.demo_login_available && (
            <>
              <p className="rw-login__divider rw-aux">또는</p>
              <button
                type="button"
                className="rw-btn rw-btn--secondary rw-btn--block"
                onClick={() => void run(demoLogin)}
                disabled={busy}
              >
                테스트 로그인 ({config.data.demo_username})
              </button>
            </>
          )}
        </form>

        {/* 서버 notice 는 API 관점의 설명("조회 API 는 열려 있다")이라 이 화면에
            그대로 두면 "그럼 왜 로그인하지?"가 된다. 화면은 로그인 뒤에 있고
            API 는 공개인 것이 맞지만, 그 구분은 표준·API 화면에서 다룬다. */}
        {config.data?.demo_login_available && (
          <p className="rw-note" style={{ marginTop: "var(--rw-space-6)" }}>
            계정이 없으시면 «테스트 로그인»으로 모든 화면을 둘러보실 수 있습니다.
            보이는 분석 결과는 실제 개방데이터로 산출한 값입니다.
          </p>
        )}
      </div>
    </div>
  );
}
