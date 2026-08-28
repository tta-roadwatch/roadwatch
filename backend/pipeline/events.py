"""⑤ 이벤트 추출.

초 단위 관측을 만들고 각 초에 어떤 이벤트가 발생했는지 판정한다.
임계값 근거는 docs/thresholds.md.

두 갈래로 산출한다.
  분석 A (BSM)  — 좌표를 자체 보유. 조인 없이 단독.
  분석 B (조인) — GPS 위치 + STATUS·OBJECT 신호.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg

from . import join, sources as S
from .codebook import autonomy_disengaged

# ── 임계값 (docs/thresholds.md §F — Phase 6 캘리브레이션 결과) ──────────
#: 그 초의 최저 속도가 이 값 미만이면 저속·정지로 본다 (7.2 km/h).
#: 목표 셀 4곳에서 오차 7/306(2.3%)로 기획서 실측값을 재현하는 정의다.
LOW_SPEED_MAX = 2.0
#: 참고용으로 남기는 보조 임계 (현재 이벤트 판정에는 쓰지 않는다)
SPEED_GOAL_MIN = 1.0
SPEED_RATIO_MAX = 0.5
OBSTACLE_MIN = 5.0

EMERGENCY = "emergency"
AUTONOMY = "autonomy_disengage"
LOW_SPEED = "low_speed"
STATE_DEV = "state_deviation"
SPEED_SHORT = "speed_shortfall"
OBSTACLE = "obstacle_density"


@dataclass(frozen=True)
class SecondObs:
    """격자 집계의 입력 단위 — 한 세션의 한 초."""
    session_id: str
    sec: int
    lat: float
    lon: float
    events: frozenset[str]
    #: 이벤트 판정에는 쓰지 않는 참고 신호 (event_types에 "ref:" 접두어로 기록)
    refs: frozenset[str] = frozenset()


def _bsm_observations(conn: psycopg.Connection, session_id: str) -> list[SecondObs]:
    """분석 A — BSM. 같은 초의 레코드는 관측 1회, 이벤트는 OR로 병합."""
    with conn.cursor() as cur:
        cur.execute(
            """select obs_second,
                      min(lat), min(lon),
                      bool_or(coalesce(f_manual_emg,false)
                              or coalesce(f_auto_emg,false)
                              or coalesce(f_sensor_trb,false))            as emg,
                      bool_or(autonomy_raw = 2)                           as disengaged
               from driving_records
               where session_id = %s and dataset_kind = %s
                 and valid_coord and obs_second is not null
               group by obs_second
               order by obs_second""",
            (session_id, S.BSM),
        )
        out = []
        for sec, lat, lon, emg, dis in cur.fetchall():
            ev = set()
            if emg:
                ev.add(EMERGENCY)
            if dis:
                ev.add(AUTONOMY)
            out.append(SecondObs(session_id, sec, lat, lon, frozenset(ev)))
        return out


def _joined_observations(conn: psycopg.Connection, session_id: str) -> list[SecondObs]:
    """분석 B — GPS 위치에 STATUS·OBJECT 신호를 붙인다."""
    pos = join.position_index(conn, session_id)
    if not pos:
        return []
    sig = join.collect_signals(session_id)

    out = []
    for sec, (lat, lon) in sorted(pos.items()):
        s = sig.get(sec)
        ev, refs = set(), set()
        if s is not None:
            # 이벤트 판정은 저속·정지 하나로 한다 (docs/thresholds.md §F).
            #   · auto_sttus 기반 정의는 목표 셀에서 11% 또는 100%로 양극단이라 기각
            #   · obstacle_density를 OR로 더하면 오차가 7 → 17로 악화
            # 장애물·상태 신호는 refs로 넘겨 event_types에 "ref:"로만 기록된다.
            if s.speed_min is not None and s.speed_min < LOW_SPEED_MAX:
                ev.add(LOW_SPEED)
            if s.state_deviated:
                refs.add(STATE_DEV)
            if s.obstacle_max >= OBSTACLE_MIN:
                refs.add(OBSTACLE)
        out.append(SecondObs(session_id, sec, lat, lon, frozenset(ev), frozenset(refs)))
    return out


def observations(conn: psycopg.Connection, session_id: str) -> list[SecondObs]:
    """세션의 초 단위 관측. BSM 세션이면 A, 아니면 B."""
    kinds = {s.kind for s in S.SOURCES if s.session_id == session_id}
    if S.BSM in kinds:
        return _bsm_observations(conn, session_id)
    return _joined_observations(conn, session_id)


def all_sessions(conn: psycopg.Connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("select id from sessions order by id")
        return [r[0] for r in cur.fetchall()]
