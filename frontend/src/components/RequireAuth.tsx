import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Loading } from "./States";

/** 업무 화면을 인증 뒤에 둔다.
 *
 * 랜딩은 누구나 보고, 그 다음부터는 로그인한 사람의 화면이다. 도로관리
 * 업무 시스템이므로 이 편이 실제 운영에 가깝고, 랜딩 → 로그인 → 대시보드로
 * 이어지는 흐름도 서비스답게 읽힌다.
 *
 * 조회 API 자체는 인증 없이 열려 있다. 공개 데이터이고, 표준 준수를
 * 확인하려는 사람이 /ngsi-ld/v1/* 를 그냥 눌러볼 수 있어야 하기 때문이다.
 * 막는 것은 화면이지 데이터가 아니다.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, restoring } = useAuth();
  const location = useLocation();

  // 저장된 토큰을 확인하는 중이다. 여기서 곧바로 로그인 화면을 띄우면
  // 새로고침할 때마다 화면이 깜빡인다.
  if (restoring) {
    return <Loading label="로그인 상태를 확인하는 중입니다" />;
  }

  if (!user) {
    // 원래 가려던 곳을 남겨 로그인 후 그리로 보낸다. 링크를 받아 열었을 때
    // 로그인하고 나면 대시보드로 떨어지는 일이 없게 한다.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
