"""원본 파일 레지스트리와 스트리밍 리더.

파일명 표기가 제각각이라(`메세지`/`메시지`, `데이터` 유무) glob을 쓰지 않고
명시적 목록으로 관리한다. session_id는 ss_num 복원 실측값이며 적재 시 재검증한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import ijson

KST = ZoneInfo("Asia/Seoul")

# 데이터셋 종류
BSM, GPS, STATUS, OBJECT, CONTROL = "BSM", "GPS", "STATUS", "OBJECT", "CONTROL"

#: 좌표를 가진 종류만 driving_records에 적재한다
HAS_COORDS = {BSM, GPS}

#: 843,734건 합계에 포함되는 종류 (CONTROL은 기획서 집계 밖)
CORE_KINDS = {BSM, GPS, STATUS, OBJECT}


@dataclass(frozen=True)
class SourceFile:
    filename: str
    kind: str
    session_id: str      # 예상 세션 ID — 적재 시 실측으로 재검증
    expected_count: int


SOURCES: list[SourceFile] = [
    # ── BSM : ss_num 없음. colct_dt(밀리초 datetime)가 시간축 ──────────
    SourceFile("기본안전메세지_nia.json",                    BSM,     "2022-10-03",  15_585),
    SourceFile("기본안전메시지_nia(2023).json",              BSM,     "2023-02-23",  14_425),
    SourceFile("기본안전메시지_nia_2024.json",               BSM,     "2024-01-02",  10_000),
    # ── GPS/INS : 위치 기준축 ────────────────────────────────────────
    SourceFile("차량GPSINS_nia_2024.json",                   GPS,     "2022-05-16",  90_000),
    SourceFile("차량GPSINS_nia(2023).json",                  GPS,     "2022-07-25", 151_455),
    SourceFile("차량GPSINS데이터_nia.json",                  GPS,     "2022-08-05",  52_494),
    # ── 차량 상태정보 ───────────────────────────────────────────────
    SourceFile("차량상태정보데이터_nia_2024.json",           STATUS,  "2022-05-16",  45_000),
    SourceFile("차량상태정보데이터_nia(2023).json",          STATUS,  "2022-07-25",  75_710),
    SourceFile("차량상태정보_nia.json",                      STATUS,  "2022-08-05",  26_237),
    # ── 객체인식 ────────────────────────────────────────────────────
    SourceFile("차량객체인식데이터_nia_2024.json",           OBJECT,  "2022-05-16", 135_000),
    SourceFile("차량객체인식데이터_nia(2023).json",          OBJECT,  "2022-07-06", 127_924),
    SourceFile("차량객체인식데이터_nia(2023)_230613.json",   OBJECT,  "2022-06-16",   9_238),
    SourceFile("차량객체인식정보데이터_nia.json",            OBJECT,  "2022-08-05",  90_666),
    # ── 차량 제어정보 (기획서 843,734 집계 밖) ────────────────────────
    SourceFile("차량제어정보데이터_nia_2024.json",           CONTROL, "2022-05-16",  45_000),
    SourceFile("차량제어정보데이터_nia(2023).json",          CONTROL, "2022-07-25",  75_711),
    SourceFile("차량제어정보_nia.json",                      CONTROL, "2022-08-05",  26_239),
]


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "./data"))


def raw_path(src: SourceFile) -> Path:
    return data_dir() / "raw" / src.filename


def stream(path: Path) -> Iterator[dict]:
    """최상위 JSON 배열을 레코드 단위로 흘려보낸다 (최대 161MB 파일 대응)."""
    with open(path, "rb") as fh:
        yield from ijson.items(fh, "item")


# ── 시간 파싱 ─────────────────────────────────────────────────────────

def parse_ss_num(raw) -> datetime | None:
    """ss_num(epoch)을 KST datetime으로. 초/밀리초 단위를 모두 받는다."""
    if raw is None:
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if n > 1e12:          # 밀리초
        n /= 1000.0
    return datetime.fromtimestamp(n, tz=timezone.utc).astimezone(KST)


#: colct_dt 표기가 데이터셋마다 다르다 (실측 확인)
#:   BSM               '2022-10-03 10:46:03.669'   공백 + 콜론 + 밀리초
#:   GPS/STATUS/…      '2024-05-16-12-43-23'       전부 하이픈 구분
COLCT_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d-%H-%M-%S",
    "%Y-%m-%d",
)


def parse_colct_dt(raw) -> datetime | None:
    """colct_dt(파일 라벨 시각)를 KST datetime으로.

    이 값은 배포 라벨이라 실제 수집 연도와 최대 2년 어긋난다.
    세션 식별에 쓰지 않고 라벨 불일치 판정에만 쓴다.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for fmt in COLCT_DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    return None


def observed_at(kind: str, rec: dict) -> datetime | None:
    """레코드의 관측 시각. ss_num이 있으면 그것을, 없으면(BSM) colct_dt를 쓴다."""
    if kind != BSM:
        dt = parse_ss_num(rec.get("ss_num"))
        if dt is not None:
            return dt
    return parse_colct_dt(rec.get("colct_dt"))
