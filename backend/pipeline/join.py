"""④ ss_num 초 단위 조인.

상태·객체정보에는 좌표가 없다. GPS/INS를 기준축으로 삼아 같은 초의 위치를
빌려온다. 같은 초에 여러 레코드가 있으면 관측 1회로 취급하고 신호는 병합한다
(이벤트는 OR, 수치는 최악값). 위치를 얻지 못한 초는 탈락시킨다.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg

from . import sources as S


@dataclass(frozen=True)
class SecondSignals:
    """한 세션의 한 초에 모인 원신호."""
    state_deviated: bool = False      # auto_sttus 계열 이탈
    speed_ratio_min: float | None = None   # 그 초의 최소 ve/goal_ve
    speed_min: float | None = None    # 그 초의 최저 실제 속도 (m/s)
    obstacle_max: float = 0.0         # 그 초의 최대 obcl_nmbr
    has_status: bool = False
    has_object: bool = False


def position_index(conn: psycopg.Connection, session_id: str) -> dict[int, tuple[float, float]]:
    """GPS 초 → 대표 좌표.

    초당 100건(100Hz)이고 초 내 이동은 p99 ≤ 7.4m(셀 40m의 1/5)이라
    첫 레코드를 대표로 쓴다 — docs/thresholds.md §E.
    """
    with conn.cursor() as cur:
        cur.execute(
            """select distinct on (obs_second) obs_second, lat, lon
               from driving_records
               where session_id = %s and dataset_kind = %s
                 and valid_coord and obs_second is not null
               order by obs_second, id""",
            (session_id, S.GPS),
        )
        return {sec: (lat, lon) for sec, lat, lon in cur.fetchall()}


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sources_for(session_id: str, kind: str) -> list[S.SourceFile]:
    return [s for s in S.all_sources() if s.session_id == session_id and s.kind == kind]


def collect_signals(session_id: str) -> dict[int, SecondSignals]:
    """STATUS·OBJECT를 raw에서 스트리밍하며 초 단위로 병합한다."""
    state: dict[int, bool] = {}
    ratio: dict[int, float] = {}
    vmin: dict[int, float] = {}
    obst: dict[int, float] = {}
    has_status: set[int] = set()
    has_object: set[int] = set()

    for src in _sources_for(session_id, S.STATUS):
        for rec in S.stream(S.raw_path(src)):
            dt = S.parse_ss_num(rec.get("ss_num"))
            if dt is None:
                continue
            sec = int(dt.timestamp())
            has_status.add(sec)
            # 주행상태 이탈 — 세 필드는 완전 상관이라 하나만 본다 (§B)
            if str(rec.get("auto_sttus", "")).strip() == "0":
                state[sec] = True
            # 목표속도 미달 — 그 초의 최소 비율을 남긴다
            gv, v = _f(rec.get("goal_ve")), _f(rec.get("ve"))
            if v is not None and (sec not in vmin or v < vmin[sec]):
                vmin[sec] = v
            if gv is not None and v is not None and gv >= 1.0:
                r = v / gv
                if sec not in ratio or r < ratio[sec]:
                    ratio[sec] = r

    for src in _sources_for(session_id, S.OBJECT):
        for rec in S.stream(S.raw_path(src)):
            dt = S.parse_ss_num(rec.get("ss_num"))
            if dt is None:
                continue
            sec = int(dt.timestamp())
            has_object.add(sec)
            n = _f(rec.get("obcl_nmbr"))
            if n is not None and n > obst.get(sec, 0.0):
                obst[sec] = n

    out: dict[int, SecondSignals] = {}
    for sec in has_status | has_object:
        out[sec] = SecondSignals(
            state_deviated=state.get(sec, False),
            speed_ratio_min=ratio.get(sec),
            speed_min=vmin.get(sec),
            obstacle_max=obst.get(sec, 0.0),
            has_status=sec in has_status,
            has_object=sec in has_object,
        )
    return out
