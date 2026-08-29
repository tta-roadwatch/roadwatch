import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

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
  const config = useApi(() => api.authConfig(), []);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (restoring) return <Loading label="로그인 상태를 확인하는 중입니다" />;
  if (user) return <Navigate to="/" replace />;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      navigate("/", { replace: true });
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
        <div className="rw-login__brand">
          <Logo size={40} />
          <div>
            <h1 className="rw-card-title">자율주행 취약도로 탐지</h1>
            <p className="rw-aux">경기도자율주행센터 · 도로관리 담당자용</p>
          </div>
        </div>

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

        {config.data && (
          <p className="rw-note" style={{ marginTop: "var(--rw-space-6)" }}>
            {config.data.notice}
          </p>
        )}
      </div>
    </div>
  );
}
