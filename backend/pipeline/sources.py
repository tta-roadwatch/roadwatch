"""원본 파일 레지스트리와 스트리밍 리더.

등록된 16개 파일은 명시 목록으로 관리한다. 파일명 표기가 제각각이라
(`메세지`/`메시지`, `데이터` 유무) glob 으로 잡으면 조용히 누락되고,
등록된 expected_count 가 적재 후 대조되어 파일이 잘렸는지도 잡아낸다.

다만 새 데이터가 공개될 때마다 코드를 고쳐야 한다면 쓰기 어려운 도구다.
그래서 등록되지 않은 파일은 `discover()` 가 자동으로 찾는다 — 데이터셋 종류는
필드 구성으로, 세션은 ss_num 에서 복원해 추론한다. 파일을 data/raw 에 넣고
`make ingest` 만 하면 된다.

정리하면 두 경로가 공존한다.
    등록된 파일   종류·세션·건수까지 대조 (무결성 검증 유지)
    새 파일       데이터에서 추론해 적재 (코드 수정 불필요)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
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
    expected_count: int | None = None   # None 이면 대조하지 않는다(자동 인식분)
    discovered: bool = False


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


# ── 자동 인식 ─────────────────────────────────────────────────────────
# 등록되지 않은 파일을 data/raw 에서 찾아 종류·세션을 추론한다.
# 새 주행 데이터가 공개될 때 코드를 고치지 않아도 되게 하는 것이 목적이다.

#: 종류를 가르는 고유 필드. 16개 원본 전수로 확인했다.
#: 위에서부터 검사하므로 더 특징적인 것을 먼저 둔다 —
#: STATUS 와 CONTROL 은 gear_num 을 공유해서 auto_sttus 로 먼저 갈라야 한다.
KIND_MARKERS: list[tuple[str, str]] = [
    (BSM, "mnl_emg_flg"),
    (GPS, "gps_srvc_dvsn_cd"),
    (STATUS, "auto_sttus"),
    (OBJECT, "blkr_cont_cd"),
    (CONTROL, "stop_yn"),
]

#: 종류·세션 추론에 쓰는 표본 수. 레코드가 시간순이 아니라서 첫 줄만 보면
#: 세션이 어긋난다(실제로 07-25 주행에서 겪었다). 넉넉히 읽어 최소 시각을 쓰고,
#: 적재 후 ingest 가 파일 전체 최소 시각으로 다시 검증해 경고를 남긴다.
DISCOVER_SAMPLE = 5000


def detect_kind(records: list[dict]) -> str | None:
    """레코드의 필드 구성으로 데이터셋 종류를 판별한다."""
    keys: set[str] = set()
    for r in records[:20]:
        keys |= set(r.keys())
    for kind, marker in KIND_MARKERS:
        if marker in keys:
            return kind
    return None


@lru_cache(maxsize=1)
def _discover_cached() -> tuple[SourceFile, ...]:
    return tuple(discover())


def refresh() -> None:
    """자동 인식 결과를 다시 읽는다. 파일을 추가한 뒤 같은 프로세스에서
    이어 돌릴 때 쓴다 (API 는 재기동되므로 보통 필요 없다)."""
    _discover_cached.cache_clear()


def discover(registered: set[str] | None = None) -> list[SourceFile]:
    """data/raw 에서 등록되지 않은 JSON 을 찾아 SourceFile 로 만든다.

    판별하지 못한 파일은 조용히 넘기지 않고 건너뛴 사실이 드러나야 하므로
    호출부(ingest)가 결과 목록을 보고 판단하게 한다.
    """
    registered = registered or {s.filename for s in SOURCES}
    root = data_dir() / "raw"
    if not root.is_dir():
        return []

    found: list[SourceFile] = []
    for path in sorted(root.glob("*.json")):
        if path.name in registered:
            continue
        head: list[dict] = []
        try:
            for rec in stream(path):
                head.append(rec)
                if len(head) >= DISCOVER_SAMPLE:
                    break
        except Exception:
            continue          # 읽을 수 없는 파일은 대상이 아니다
        if not head:
            continue

        kind = detect_kind(head)
        if kind is None:
            continue

        dates = [dt.date() for dt in (observed_at(kind, r) for r in head) if dt]
        if not dates:
            continue
        found.append(SourceFile(path.name, kind, min(dates).isoformat(),
                                expected_count=None, discovered=True))
    return found


def all_sources() -> list[SourceFile]:
    """등록분 + 자동 인식분. 파이프라인은 이 목록으로 돈다.

    자동 인식은 디스크를 훑으므로 캐시한다 — join 은 세션×종류마다 호출한다.
    """
    return [*SOURCES, *_discover_cached()]
