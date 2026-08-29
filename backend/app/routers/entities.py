"""데이터 인터페이스 — TTAK.KO-10.1331-Part3 6.1.

엔티티 조회 리소스. Part3 가 규정하는 질의 파라미터(type · id · q · limit ·
offset · options)를 받고, Part4/R1 정규 표현법으로 응답한다.

options=keyValues 는 정규 표현법 대신 값만 평탄하게 돌려주는 축약형이다.
화면이 매번 .value 를 파고들 필요가 없어 프론트에서 이 모드를 쓴다.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from .. import errors, ngsild
from ..deps import cursor

router = APIRouter(prefix="/ngsi-ld/v1", tags=["Part3 6.1 데이터 인터페이스"])

SUPPORTED = ("TrafficEvent", "VehicleTraffic")

#: 취약구간 — road_issues 가 판정 결과, grid_cells 가 공간·도로 속성
_EVENT_SQL = """
select r.cell_key, r.classification, r.session_count,
       r.min_event_rate, r.max_event_rate, r.is_candidate, r.decided_at,
       g.center_lat, g.center_lon, g.road_name, g.address,
       g.link_id, g.lanes, g.max_speed
from road_issues r join grid_cells g using (cell_key)
"""

#: 세션×격자 관측 — 이벤트율의 근거가 되는 원 관측
_TRAFFIC_SQL = """
select o.cell_key, o.session_id, o.observation_count, o.event_count,
       o.event_rate, o.event_types, o.measurable,
       g.center_lat, g.center_lon,
       s.actual_start
from cell_observations o
join grid_cells g using (cell_key)
join sessions s on s.id = o.session_id
"""


def _key_values(e: dict) -> dict:
    """정규 표현법 → 축약형. Property 는 value, GeoProperty 는 GeoJSON,
    Relationship 은 object 만 남긴다."""
    out = {}
    for k, v in e.items():
        if k == "@context":
            continue
        if isinstance(v, dict) and "type" in v:
            if v["type"] == "Relationship":
                out[k] = v.get("object")
            else:
                out[k] = v.get("value")
        else:
            out[k] = v
    return out


def _render(rows: list[dict], entity_type: str, key_values: bool) -> list[dict]:
    build = ngsild.traffic_event if entity_type == "TrafficEvent" else ngsild.vehicle_traffic
    ents = [build(r, context=not key_values) for r in rows]
    return [_key_values(e) for e in ents] if key_values else ents


@router.get("/entities", summary="엔티티 목록 조회")
def list_entities(
    type: str = Query("TrafficEvent", description="TrafficEvent | VehicleTraffic"),
    q: str | None = Query(None, description='속성 필터. 예: classification==intermittent'),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    options: str | None = Query(None, description="keyValues 지정 시 축약형"),
):
    if type not in SUPPORTED:
        raise errors.bad_request(
            f"지원하지 않는 엔티티 타입입니다: {type} (가능: {', '.join(SUPPORTED)})")

    base = _EVENT_SQL if type == "TrafficEvent" else _TRAFFIC_SQL
    where, params = [], []

    if q:
        # Part3 의 질의 언어 전체가 아니라 화면이 쓰는 == 비교만 지원한다.
        if "==" not in q:
            raise errors.bad_request("q 는 '속성==값' 형식만 지원합니다")
        attr, _, val = q.partition("==")
        col = {
            "classification": "r.classification",
            "isCandidate": "r.is_candidate",
            "sessionId": "o.session_id",
            "measurable": "o.measurable",
        }.get(attr.strip())
        if col is None:
            raise errors.bad_request(f"질의할 수 없는 속성입니다: {attr}")
        val = val.strip()
        if val in ("true", "false"):
            where.append(f"{col} = %s")
            params.append(val == "true")
        else:
            where.append(f"{col} = %s")
            params.append(val)

    sql = base + (" where " + " and ".join(where) if where else "")
    sql += " order by 1, 2 limit %s offset %s"
    params += [limit, offset]

    with cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return _render(rows, type, options == "keyValues")


@router.get("/entities/{entity_id:path}", summary="엔티티 단건 조회")
def get_entity(entity_id: str, options: str | None = Query(None)):
    key = ngsild.cell_key_from_urn(entity_id)
    if key is None:
        raise errors.bad_request(
            f"TrafficEvent URN 형식이 아닙니다: {entity_id} "
            f"(예: urn:ngsi-ld:TrafficEvent:roadwatch:21:4)")
    with cursor() as cur:
        cur.execute(_EVENT_SQL + " where r.cell_key = %s", (key,))
        row = cur.fetchone()
    if row is None:
        raise errors.not_found(f"해당 구간이 없습니다: {key}")
    e = ngsild.traffic_event(row, context=options != "keyValues")
    return _key_values(e) if options == "keyValues" else e


@router.get("/context.jsonld", summary="서비스 확장 컨텍스트",
            include_in_schema=False)
def context():
    """코어 컨텍스트에 없는 본 서비스 용어 정의. 엔티티의 @context 가 이 경로를
    가리키므로 실제로 서빙돼야 한다."""
    return ngsild.SERVICE_CONTEXT
