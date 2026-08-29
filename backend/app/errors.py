"""오류 응답 — TTAK.KO-10.1331-Part3 5장 응답 코드 체계.

Part3 는 오류를 ProblemDetails(RFC 7807) 형태로 돌려주도록 규정한다.
FastAPI 기본 오류는 {"detail": "..."} 라서 이 형식과 맞지 않으므로,
main.py 에서 예외 핸들러로 전부 갈아끼운다.
"""
from __future__ import annotations

from fastapi import HTTPException

#: Part3 가 참조하는 NGSI-LD 오류 타입 URI
BASE = "https://uri.etsi.org/ngsi-ld/errors"

INVALID_REQUEST = f"{BASE}/InvalidRequest"
BAD_REQUEST_DATA = f"{BASE}/BadRequestData"
RESOURCE_NOT_FOUND = f"{BASE}/ResourceNotFound"
INTERNAL_ERROR = f"{BASE}/InternalError"

TITLES = {
    INVALID_REQUEST: "요청 형식이 올바르지 않습니다",
    BAD_REQUEST_DATA: "요청 데이터가 올바르지 않습니다",
    RESOURCE_NOT_FOUND: "요청한 리소스를 찾을 수 없습니다",
    INTERNAL_ERROR: "서버 내부 오류입니다",
}


def problem(type_uri: str, status: int, detail: str) -> dict:
    return {"type": type_uri, "title": TITLES.get(type_uri, "오류"),
            "status": status, "detail": detail}


class ProblemError(HTTPException):
    """ProblemDetails 로 직렬화되는 예외."""

    def __init__(self, type_uri: str, status: int, detail: str):
        super().__init__(status_code=status, detail=detail)
        self.type_uri = type_uri


def not_found(detail: str) -> ProblemError:
    return ProblemError(RESOURCE_NOT_FOUND, 404, detail)


def bad_request(detail: str) -> ProblemError:
    return ProblemError(BAD_REQUEST_DATA, 400, detail)
