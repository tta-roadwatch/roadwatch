"""인증 — 도로관리 담당자 로그인.

**어디에 인증을 거는가**가 이 모듈의 설계 결정이다.

조회는 열어둔다. 이 서비스가 다루는 것은 전부 무료 개방데이터이고, 도로가
어디서 어려운지는 시민도 볼 수 있어야 한다. 심사자가 API 를 그냥 curl 해봤을
때 막히면 표준 준수를 확인할 방법도 함께 막힌다.

쓰기는 막는다. 현장점검 등록은 시스템 판정을 사람이 확정하거나 번복하는
지점이고(기획서 3.3), 누가 뒤집었는지가 기록으로 남아야 의미가 있다.
inspector 필드를 토큰에서 채우는 이유다.

비밀번호는 표준 라이브러리 PBKDF2-HMAC-SHA256 으로 해싱한다. bcrypt/argon2 가
더 낫지만 의존을 늘리지 않으려 했고, 반복 횟수를 충분히 두면 이 규모에서는
문제되지 않는다.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Request

from . import errors
from .deps import cursor

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=12)

PBKDF2_ROUNDS = 200_000

#: 배포 시 반드시 환경변수로 덮어써야 한다. 개발 기본값을 그대로 쓰면
#: 토큰을 누구나 위조할 수 있다 — 공개 저장소에 있는 값이기 때문이다.
#: 32바이트 이상이어야 한다 (RFC 7518 3.2 — HS256 최소 키 길이).
DEV_SECRET = "roadwatch-dev-secret-change-me-in-production"
#: 빈 문자열도 미설정으로 본다. .env.example 이 `JWT_SECRET=` 로 배포되므로
#: os.environ.get 의 기본값만 믿으면 빈 키로 서명하다 InvalidKeyError 가 난다 —
#: 예제 파일을 그대로 복사한 사람의 로그인이 통째로 깨진다.
SECRET = os.environ.get("JWT_SECRET", "").strip() or DEV_SECRET


def using_dev_secret() -> bool:
    return SECRET == DEV_SECRET


# ── 비밀번호 ──────────────────────────────────────────────────────────

def hash_password(password: str, salt: str | None = None) -> str:
    """pbkdf2$rounds$salt$hash 형식으로 저장한다."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                             PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt, digest = stored.split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt), int(rounds))
    except (ValueError, TypeError):
        return False
    # 타이밍 공격을 피하려 상수시간 비교를 쓴다
    return hmac.compare_digest(dk.hex(), digest)


# ── 토큰 ──────────────────────────────────────────────────────────────

def issue_token(user: dict) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    exp = now + TOKEN_TTL
    payload = {
        "sub": user["username"],
        "name": user.get("display_name"),
        "role": user.get("role", "inspector"),
        "org": user.get("organization"),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM), int(TOKEN_TTL.total_seconds())


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise errors.ProblemError(errors.INVALID_REQUEST, 401,
                                  "토큰이 만료되었습니다. 다시 로그인해 주세요.")
    except jwt.InvalidTokenError:
        raise errors.ProblemError(errors.INVALID_REQUEST, 401,
                                  "토큰이 올바르지 않습니다.")


# ── 사용자 ────────────────────────────────────────────────────────────

def find_user(username: str) -> dict | None:
    with cursor() as cur:
        cur.execute("select * from users where username = %s", (username,))
        return cur.fetchone()


def touch_login(username: str) -> None:
    with cursor(commit=True) as cur:
        cur.execute("update users set last_login_at = now() where username = %s",
                    (username,))


def authenticate(username: str, password: str) -> dict:
    user = find_user(username)
    # 사용자 없음과 비밀번호 틀림을 구분해 알려주지 않는다 — 계정 존재 여부가
    # 새어나가면 그 자체가 정보다.
    if user is None or not verify_password(password, user["password_hash"]):
        raise errors.ProblemError(errors.INVALID_REQUEST, 401,
                                  "아이디 또는 비밀번호가 올바르지 않습니다.")
    touch_login(username)
    return user


def public(user: dict) -> dict:
    return {"username": user["username"], "display_name": user.get("display_name"),
            "organization": user.get("organization"), "role": user.get("role"),
            "is_demo": bool(user.get("is_demo"))}


# ── 의존성 ────────────────────────────────────────────────────────────

def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def current_user(request: Request) -> dict:
    """쓰기 경로에 건다. 토큰이 없거나 틀리면 401."""
    token = _bearer(request)
    if token is None:
        raise errors.ProblemError(errors.INVALID_REQUEST, 401,
                                  "로그인이 필요합니다. Authorization: Bearer <token>")
    claims = decode_token(token)
    user = find_user(claims.get("sub", ""))
    if user is None:
        raise errors.ProblemError(errors.INVALID_REQUEST, 401,
                                  "토큰의 사용자를 찾을 수 없습니다.")
    return user


def optional_user(request: Request) -> dict | None:
    """조회 경로용. 토큰이 있으면 누구인지 알고, 없어도 통과시킨다."""
    token = _bearer(request)
    if token is None:
        return None
    try:
        claims = decode_token(token)
    except errors.ProblemError:
        return None
    return find_user(claims.get("sub", ""))


RequireUser = Depends(current_user)
OptionalUser = Depends(optional_user)


# ── 초기 계정 ─────────────────────────────────────────────────────────
#: 해시를 SQL 에 박아두지 않는다. 기동 시 없으면 만들어서, 새 볼륨이든 기존
#: 볼륨이든 같은 계정이 준비되게 한다.
SEED_USERS = [
    {"username": "demo", "password": "roadwatch2026",
     "display_name": "데모 사용자", "organization": "성남시 도로관리과",
     "role": "inspector", "is_demo": True},
    {"username": "admin", "password": "roadwatch2026!",
     "display_name": "관리자", "organization": "성남시 도로관리과",
     "role": "admin", "is_demo": False},
]


def ensure_seed_users() -> None:
    try:
        with cursor(commit=True) as cur:
            for u in SEED_USERS:
                cur.execute(
                    """insert into users
                       (username, password_hash, display_name, organization, role, is_demo)
                       values (%s,%s,%s,%s,%s,%s)
                       on conflict (username) do nothing""",
                    (u["username"], hash_password(u["password"]), u["display_name"],
                     u["organization"], u["role"], u["is_demo"]),
                )
    except Exception:
        # users 테이블이 아직 없는 구버전 볼륨이면 조용히 넘어간다.
        # make reset 하면 01_schema.sql 이 만들어준다.
        pass
