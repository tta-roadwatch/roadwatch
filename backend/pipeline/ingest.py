"""① 적재 + 세션 식별.

파일명을 신뢰하지 않는다. ss_num(epoch)에서 실제 수집시각을 복원해 세션 ID로
삼고, ss_num이 없는 BSM은 colct_dt(밀리초 datetime)를 쓴다.
좌표를 가진 BSM·GPS만 driving_records에 정규화 적재하며,
STATUS·OBJECT·CONTROL은 세션 메타만 기록하고 ④에서 raw로 다시 읽는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import psycopg

from . import sources as S
from .codebook import (
    SESSION_CODEBOOK,
    Codebook,
    detect,
    normalize_vehicle_id,
)

#: 한국 영역 대략 경계 — 이 밖이면 좌표 무효
LAT_RANGE = (33.0, 39.0)
LON_RANGE = (124.0, 132.0)

#: 코드북 판별용으로 앞에서 모아두는 레코드 수
DETECT_SAMPLE = 2000

COPY_COLUMNS = (
    "session_id", "dataset_kind", "vehicle_id", "observed_at", "obs_second",
    "lat", "lon", "speed", "steering", "accel_lng",
    "f_manual_emg", "f_auto_emg", "f_sensor_trb", "f_state_abn",
    "autonomy_raw", "valid_coord",
)


@dataclass
class FileReport:
    src: S.SourceFile
    count: int = 0
    session_id: str = ""
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    has_ss_num: bool = False
    label_date: date | None = None
    label_mismatch: bool = False
    loaded: int = 0                  # driving_records에 넣은 행 수
    invalid_coord: int = 0
    codebook: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def count_ok(self) -> bool:
        return self.count == self.src.expected_count


# ── 값 변환 ───────────────────────────────────────────────────────────

def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v) -> int | None:
    f = _f(v)
    return None if f is None else int(f)


def _valid_coord(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    if lat == 0.0 and lon == 0.0:          # GPS 미고정
        return False
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def _row(kind: str, rec: dict, session_id: str, cb: Codebook | None) -> tuple:
    """정규화된 driving_records 한 행."""
    lat, lon = _f(rec.get("la")), _f(rec.get("lo"))
    ok = _valid_coord(lat, lon)
    dt = S.observed_at(kind, rec)
    sec = int(dt.timestamp()) if dt else None

    if kind == S.BSM and cb is not None:
        flags = (
            cb.flag("mnl_emg_flg", rec.get("mnl_emg_flg")),
            cb.flag("auto_emg_flg", rec.get("auto_emg_flg")),
            cb.flag("snsr_trb_flg", rec.get("snsr_trb_flg")),
            cb.flag("vhcl_sttus_flg", rec.get("vhcl_sttus_flg")),
        )
        autonomy = _i(rec.get("autonm_flg"))
        speed, steer, accel = _f(rec.get("ve")), _f(rec.get("strwhl_angl")), _f(rec.get("lng_acclset"))
        vid = normalize_vehicle_id(rec.get("vhcl_id"))
    else:
        flags = (None, None, None, None)
        autonomy = None
        speed = steer = accel = None
        vid = None

    return (
        session_id, kind, vid, dt, sec,
        lat if ok else None, lon if ok else None,
        speed, steer, accel,
        *flags, autonomy, ok,
    )


# ── 파일 단위 적재 ────────────────────────────────────────────────────

def ingest_file(conn: psycopg.Connection, src: S.SourceFile) -> FileReport:
    path = S.raw_path(src)
    rep = FileReport(src=src)
    if not path.exists():
        rep.warnings.append(f"파일 없음: {path}")
        return rep

    stream = S.stream(path)
    head: list[dict] = []
    for rec in stream:
        head.append(rec)
        if len(head) >= DETECT_SAMPLE:
            break

    if not head:
        rep.warnings.append("빈 파일")
        return rep

    # 세션 식별 : 레지스트리 값을 쓰고, 적재 후 파일 최소 시각으로 재검증한다.
    #
    # 레코드가 시간순으로 정렬돼 있지 않다. 첫 레코드로 세션을 정하면 같은 주행의
    # 파일들이 서로 다른 날짜로 갈린다 — 실제로 2022-07-25 주행에서 GPS·제어정보의
    # 첫 줄이 07-26이라 세션이 분열했다. 파일 전체 최소 시각을 알려면 두 번 읽어야
    # 하므로(161MB), 실측으로 검증된 레지스트리 값을 신뢰하고 사후 대조한다.
    rep.has_ss_num = src.kind != S.BSM and S.parse_ss_num(head[0].get("ss_num")) is not None
    rep.session_id = src.session_id

    # 코드북 : 등록된 세션이면 그것을, 아니면 데이터에서 추론
    cb = None
    if src.kind == S.BSM:
        cb = SESSION_CODEBOOK.get(rep.session_id) or detect(head)
        rep.codebook = cb.name

    # driving_records의 FK를 만족시키려면 세션 행이 먼저 있어야 한다.
    # 집계값은 run()에서 UPDATE로 채운다.
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (rep.session_id,),
        )

    load = src.kind in S.HAS_COORDS
    lo_dt = hi_dt = None
    label_min: date | None = None

    def consume(rec: dict, write) -> None:
        nonlocal lo_dt, hi_dt, label_min
        rep.count += 1
        dt = S.observed_at(src.kind, rec)
        if dt:
            lo_dt = dt if lo_dt is None or dt < lo_dt else lo_dt
            hi_dt = dt if hi_dt is None or dt > hi_dt else hi_dt
        ldt = S.parse_colct_dt(rec.get("colct_dt"))
        if ldt:
            d = ldt.date()
            label_min = d if label_min is None or d < label_min else label_min
        if write is not None:
            row = _row(src.kind, rec, rep.session_id, cb)
            if not row[-1]:
                rep.invalid_coord += 1
            write(row)
            rep.loaded += 1

    if load:
        cols = ", ".join(COPY_COLUMNS)
        with conn.cursor() as cur:
            with cur.copy(f"COPY driving_records ({cols}) FROM STDIN") as cp:
                for rec in head:
                    consume(rec, cp.write_row)
                for rec in stream:
                    consume(rec, cp.write_row)
    else:
        for rec in head:
            consume(rec, None)
        for rec in stream:
            consume(rec, None)

    rep.actual_start, rep.actual_end = lo_dt, hi_dt
    rep.label_date = label_min
    if label_min and lo_dt:
        rep.label_mismatch = label_min.year != lo_dt.year
    if not rep.count_ok:
        rep.warnings.append(f"건수 예상 {src.expected_count:,} → 실측 {rep.count:,}")
    # 레지스트리 세션 ID 재검증 : 파일 최소 시각의 날짜와 일치해야 한다
    if lo_dt and lo_dt.date().isoformat() != rep.session_id:
        rep.warnings.append(f"세션 {rep.session_id} ≠ 최소시각 {lo_dt.date()}")
    return rep


# ── 세션 집계 ─────────────────────────────────────────────────────────

def _metrics(kinds: set[str]) -> list[str]:
    """세션이 보유한 데이터셋으로 산출 가능한 지표 (docs/thresholds.md §F 확정본).

    위치가 있어야 격자 분석이 가능하므로 GPS 또는 BSM이 전제다.
    조인 갈래의 이벤트 판정은 low_speed 하나로 하고, state_deviation·
    obstacle_density는 참고 지표로 event_types에 'ref:'로 기록된다.
    auto_sttus·ster_sttus·ve_sttus는 완전 상관(§B)이라 하나로 통합한다.
    """
    m: list[str] = []
    if S.BSM in kinds:
        m += ["emergency", "autonomy_disengage"]
    if S.GPS in kinds:
        if S.STATUS in kinds:
            m += ["low_speed", "state_deviation"]
        if S.OBJECT in kinds:
            m += ["obstacle_density"]
    return m


def run(conn: psycopg.Connection) -> list[FileReport]:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE sessions RESTART IDENTITY CASCADE")

    reports = [ingest_file(conn, src) for src in S.SOURCES]

    # 세션 단위로 묶기
    by_session: dict[str, list[FileReport]] = {}
    for r in reports:
        if r.session_id:
            by_session.setdefault(r.session_id, []).append(r)

    with conn.cursor() as cur:
        for sid, group in sorted(by_session.items()):
            kinds = {r.src.kind for r in group}
            starts = [r.actual_start for r in group if r.actual_start]
            ends = [r.actual_end for r in group if r.actual_end]
            labels = [r.label_date for r in group if r.label_date]
            cbs = [r.codebook for r in group if r.codebook]
            cur.execute(
                """UPDATE sessions SET
                     actual_start = %s, actual_end = %s, has_ss_num = %s,
                     label_date = %s, label_mismatch = %s,
                     available_metrics = %s, codebook = %s
                   WHERE id = %s""",
                (min(starts) if starts else None,
                 max(ends) if ends else None,
                 any(r.has_ss_num for r in group),
                 min(labels) if labels else None,
                 any(r.label_mismatch for r in group),
                 _metrics(kinds),
                 cbs[0] if cbs else None,
                 sid),
            )
            for r in group:
                cur.execute(
                    """INSERT INTO session_files
                       (session_id, dataset_kind, source_file, record_count,
                        expected_count, label_date, actual_start, actual_end,
                        has_ss_num, loaded_to_db)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (sid, r.src.kind, r.src.filename, r.count, r.src.expected_count,
                     r.label_date, r.actual_start, r.actual_end,
                     r.has_ss_num, r.loaded > 0),
                )
    conn.commit()
    return reports
