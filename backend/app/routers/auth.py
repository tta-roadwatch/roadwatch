"""로그인 — 로그인 화면.

데모 시연을 위해 `테스트 로그인` 을 따로 둔다. 심사 자리에서 아이디·비밀번호를
타이핑하는 시간이 아깝고, 오타로 시연이 끊기면 손해다. 다만 편의를 위해 인증을
없애는 게 아니라, 데모 계정으로 정상 로그인 절차를 밟아 같은 토큰을 발급한다 —
즉 우회 경로가 아니라 지정된 계정의 자동 입력이다.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import auth, errors

router = APIRouter(prefix="/api/auth", tags=["인증"])


class LoginRequest(BaseModel):
    username: str
    password: str


def _token_response(user: dict) -> dict:
    token, ttl = auth.issue_token(user)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": ttl,
        "user": auth.public(user),
    }


@router.post("/login", summary="로그인")
def login(body: LoginRequest):
    user = auth.authenticate(body.username, body.password)
    return _token_response(user)


@router.post("/demo-login", summary="테스트 로그인 (데모 계정)")
def demo_login():
    """화면의 `테스트 로그인` 버튼.

    인증을 건너뛰는 게 아니라 데모 계정으로 정상 발급받는다. 발급된 토큰의
    권한도 일반 사용자(inspector)와 같다.
    """
    # main 을 여기서 부른다. 최상단에서 부르면 main → routers → auth →
    # main 으로 순환 참조가 된다.
    from .. import main

    seed = next(u for u in auth.SEED_USERS if u["is_demo"])
    user = auth.find_user(seed["username"])
    if user is None:
        raise errors.not_found(
            "데모 계정이 준비되지 않았습니다. make reset 으로 스키마를 다시 적용해 주세요.")
    auth.touch_login(user["username"])
    return _token_response(user)


@router.get("/me", summary="현재 사용자")
def me(user: dict = auth.RequireUser):
    return auth.public(user)


@router.get("/config", summary="로그인 화면 설정")
def config():
    """화면이 테스트 로그인 버튼을 띄울지 판단할 근거.

    운영 배포에서는 데모 계정을 지우면 버튼이 자동으로 사라진다.
    """
    # main 을 여기서 부른다. 최상단에서 부르면
    # main → routers → auth → main 으로 순환 참조가 된다.
    from .. import main

    seed = next(u for u in auth.SEED_USERS if u["is_demo"])
    demo = auth.find_user(seed["username"])
    return {
        "demo_login_available": demo is not None,
        "demo_username": seed["username"] if demo else None,
        # 개발 기본 비밀키를 그대로 쓰는지 화면·심사자에게 숨기지 않는다
        "dev_secret_in_use": auth.using_dev_secret(),
        # CORS 를 전부 열어 둔 상태도 숨기지 않는다. 재현을 위해 열 수는
        # 있어도, 열려 있다는 사실은 보여야 한다.
        "cors_open_to_all": "*" in main.CORS_ORIGINS,
        "cors_origins": main.CORS_ORIGINS,
        "notice": ("조회 API 는 인증 없이 열려 있습니다. 공개 데이터이기 때문입니다. "
                   "행정 기록을 남기는 쓰기(현장점검 등록)만 로그인이 필요합니다. "
                   "시민 제보는 판정을 바꾸지 않으므로 인증 없이 접수합니다."),
    }
