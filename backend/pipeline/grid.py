"""⑥ 40m 격자 집계.

격자 규약은 Phase 5 캘리브레이션으로 확정했다 (docs/thresholds.md §F).
목표 셀 4개 중 3개가 정확히 일치하고 나머지 1개가 ±1이다 (307관측 중 오차 1, 0.3%).

관측 단위는 초다. 초당 100Hz로 최대 7m를 이동하므로 한 초가 셀 경계에 걸치면
양쪽 셀 모두에서 관측된 것으로 센다 — 이 규칙이 목표 관측초를 재현한다.
"""
from __future__ import annotations

import collections
import json
import math
from dataclasses import dataclass

import psycopg

from . import events, sources as S

# ── 격자 규약 (변경 금지 — 캘리브레이션 결과) ──────────────────────────
#: 40m에 대응하는 도(度) 단위. 정확값(40/111320) 대신 반올림 상수를 쓴다.
DLAT = 0.00036
DLON = 0.00045
#: 앵커 = 판교 분석 영역 좌하단
LAT0 = 37.3957615
LON0 = 127.1027615

#: 관측이 이보다 적은 셀은 분석에서 제외 (기획서 5.3절)
MIN_OBSERVATIONS = 30


def cell_of(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor((lat - LAT0) / DLAT), math.floor((lon - LON0) / DLON))


def cell_key(iy: int, ix: int) -> str:
    return f"{iy}:{ix}"


def cell_center(iy: int, ix: int) -> tuple[float, float]:
    return ((iy + 0.5) * DLAT + LAT0, (ix + 0.5) * DLON + LON0)


@dataclass
class CellStat:
    observation_count: int = 0
    event_count: int = 0
    event_types: collections.Counter = None    # 유형별 레코드(초) 수

    def __post_init__(self):
        if self.event_types is None:
            self.event_types = collections.Counter()


def _cells_touched(conn: psycopg.Connection, session_id: str, kind: str) -> dict[int, set]:
    """초 → 그 초의 레코드들이 지나간 셀 집합."""
    out: dict[int, set] = collections.defaultdict(set)
    with conn.cursor() as cur:
        cur.execute(
            """select obs_second, lat, lon from driving_records
               where session_id=%s and dataset_kind=%s and valid_coord
                 and obs_second is not null""",
            (session_id, kind),
        )
        for sec, lat, lon in cur.fetchall():
            out[sec].add(cell_of(lat, lon))
    return out


def aggregate(conn: psycopg.Connection, session_id: str) -> dict[tuple[int, int], CellStat]:
    """세션 하나를 격자로 집계한다."""
    obs = events.observations(conn, session_id)
    if not obs:
        return {}
    ev_by_sec = {o.sec: o.events for o in obs}
    refs_by_sec = {o.sec: o.refs for o in obs}

    kinds = {s.kind for s in S.SOURCES if s.session_id == session_id}
    pos_kind = S.BSM if S.BSM in kinds else S.GPS
    touched = _cells_touched(conn, session_id, pos_kind)

    stats: dict[tuple[int, int], CellStat] = collections.defaultdict(CellStat)
    for sec, cells in touched.items():
        ev = ev_by_sec.get(sec)
        if ev is None:
            continue
        refs = refs_by_sec.get(sec) or ()
        for c in cells:
            st = stats[c]
            st.observation_count += 1
            if ev:
                st.event_count += 1
                for e in ev:
                    st.event_types[e] += 1
            for r in refs:                     # 참고 신호 — 이벤트율에 미포함
                st.event_types[f"ref:{r}"] += 1
    return stats


def run(conn: psycopg.Connection) -> dict[str, int]:
    """전 세션 집계 → grid_cells · cell_observations 적재."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE cell_observations RESTART IDENTITY")
        cur.execute("DELETE FROM grid_cells")
        cur.execute("select id, coalesce(array_length(available_metrics,1),0) from sessions order by id")
        sessions = cur.fetchall()

    summary: dict[str, int] = {}
    cells_seen: set[tuple[int, int]] = set()

    with conn.cursor() as cur:
        for sid, n_metrics in sessions:
            stats = aggregate(conn, sid)
            kept = {c: s for c, s in stats.items() if s.observation_count >= MIN_OBSERVATIONS}
            summary[sid] = len(kept)
            measurable = n_metrics > 0

            for c, st in kept.items():
                if c not in cells_seen:
                    lat, lon = cell_center(*c)
                    cur.execute(
                        "INSERT INTO grid_cells (cell_key, center_lat, center_lon) "
                        "VALUES (%s,%s,%s) ON CONFLICT (cell_key) DO NOTHING",
                        (cell_key(*c), lat, lon),
                    )
                    cells_seen.add(c)
                rate = st.event_count / st.observation_count
                cur.execute(
                    """INSERT INTO cell_observations
                       (cell_key, session_id, observation_count, event_count,
                        event_rate, event_types, measurable)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (cell_key(*c), sid, st.observation_count, st.event_count,
                     rate, json.dumps(dict(st.event_types)), measurable),
                )
    conn.commit()
    return summary
