"""RoadWatch 조회 API.

두 갈래로 나뉜다.

  /ngsi-ld/v1/*  표준 준수 경로 — TTAK.KO-10.1331-Part3 인터페이스,
                 Part4/R1 NGSI-LD 정규 표현법, TTAK.KO-10.1398 데이터세트
                 메타데이터. SCR-09 화면이 이 응답을 그대로 보여준다.
  /api/*         화면 편의 경로 — 집계를 서버에서 끝내고 화면은 그리기만 한다.

분석은 전부 pipeline 이 미리 계산해 DB 에 넣어둔다. 여기서는 읽기만 하며,
쓰기는 현장점검 등록 하나뿐이다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth as auth_mod, deps, errors
from .routers import (auth, datasets, entities, geo, inspections, report,
                      screens, standards)

DESCRIPTION = """
판교 제로시티 자율주행 개방데이터에서 **자율주행차가 반복적으로 어려움을 겪는
도로 구간**을 찾아 현장점검을 권고하는 서비스의 조회 API.

* `/ngsi-ld/v1/*` — TTA 표준 준수 경로
* `/api/*` — 화면 전용 경로

원인을 단정하지 않는 것이 설계 원칙이다. 응답은 관측된 사실과 반복성만
제공하며, 확정은 도로관리자의 현장점검이 한다.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps.pool()          # 기동 시 커넥션 풀을 미리 연다
    auth_mod.ensure_seed_users()
    yield
    deps.close()


app = FastAPI(
    title="RoadWatch API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

# 화면(5173)이 다른 오리진이라 필요하다. 공개 데이터 조회 API 라 제한하지 않는다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

for r in (entities.router, datasets.router, screens.router,
          inspections.router, report.router, geo.router,
          standards.router, auth.router):
    app.include_router(r)


# ── 오류 응답을 Part3 5장 형식으로 통일 ────────────────────────────────
# FastAPI 기본은 {"detail": "..."} 이라 표준과 맞지 않는다.

@app.exception_handler(errors.ProblemError)
async def _problem(request: Request, exc: errors.ProblemError):
    return JSONResponse(
        status_code=exc.status_code,
        content=errors.problem(exc.type_uri, exc.status_code, str(exc.detail)),
        media_type="application/problem+json",
    )


@app.exception_handler(HTTPException)
async def _http(request: Request, exc: HTTPException):
    uri = (errors.RESOURCE_NOT_FOUND if exc.status_code == 404
           else errors.INVALID_REQUEST if exc.status_code < 500
           else errors.INTERNAL_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content=errors.problem(uri, exc.status_code, str(exc.detail)),
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=errors.problem(errors.BAD_REQUEST_DATA, 400, str(exc.errors())),
        media_type="application/problem+json",
    )


@app.get("/", tags=["메타"], summary="서비스 정보")
def root():
    return {
        "service": "RoadWatch",
        "description": "자율주행 취약도로 탐지 및 도로환경 개선 지원 서비스",
        "standards": {
            "TTAK.KO-10.1331-Part3": "인터페이스 및 프로토콜 — /ngsi-ld/v1/*",
            "TTAK.KO-10.1331-Part4/R1": "데이터 모델 — NGSI-LD 정규 표현법",
            "TTAK.KO-10.1398": "데이터세트 메타데이터 — /ngsi-ld/v1/datasets",
            "TTAK.KO-06.0580": "V2N 정보 연계 — BSM 입력",
            "TTAK.KO-10.1331-Part2": "참조구조",
        },
        "auth": ("조회는 인증 없이 열려 있습니다. 현장점검 등록만 로그인이 "
                 "필요합니다 — POST /api/auth/login"),
        "docs": "/docs",
    }


@app.get("/health", tags=["메타"], summary="상태 확인")
def health():
    try:
        with deps.cursor() as cur:
            cur.execute("select count(*) as n from grid_cells")
            n = cur.fetchone()["n"]
        return {"status": "ok", "cells": n}
    except Exception as e:
        return JSONResponse(status_code=503,
                            content={"status": "degraded", "detail": str(e)})
