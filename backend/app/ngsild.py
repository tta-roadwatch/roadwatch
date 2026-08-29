"""NGSI-LD 정규 표현법 직렬화 — TTAK.KO-10.1331-Part4/R1.

Part4/R1 은 데이터허브에 저장·제공하는 데이터를 NGSI-LD 정규 표현법(normalized
representation)으로 표현하도록 규정한다. 값을 그냥 넣는 게 아니라 속성마다
종류(Property / GeoProperty / Relationship)를 밝히고, 관측시각이 있으면
observedAt 을 함께 싣는다.

    "name": {"type": "Property", "value": "대왕판교로"}
    "location": {"type": "GeoProperty",
                 "value": {"type": "Point", "coordinates": [127.10, 37.40]}}

DB 스키마(01_schema.sql)는 이 모델을 관계형으로 옮긴 것이므로, 여기서는 컬럼을
표준 속성명으로 되돌리는 일만 한다. road_name→name, address→address,
observed_at→observedAt 매핑이 스키마 주석에 이미 명시돼 있다.

엔티티 종류
    TrafficEvent   (7.2.2) 취약구간 — 격자 하나가 이벤트 하나
    VehicleTraffic (7.2.1) 세션×격자 관측 — 이벤트율의 근거
"""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: ETSI 코어 컨텍스트 + 본 서비스 확장 컨텍스트(API 가 직접 서빙한다)
CORE_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
SERVICE_CONTEXT_PATH = "/ngsi-ld/v1/context.jsonld"

#: @context 는 해석 가능한 URI 여야 한다. 상대 경로를 실으면 응답을 받아간
#: 외부 소비자가 컨텍스트를 못 찾는다 — 표준을 지킨 게 아니라 지킨 척이 된다.
#: 배포 주소가 다르면 API_BASE_URL 로 바꾼다.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")


def service_context_url() -> str:
    return f"{API_BASE_URL}{SERVICE_CONTEXT_PATH}"

URN_PREFIX = "urn:ngsi-ld"
PRODUCER = "roadwatch"


# ── URN ───────────────────────────────────────────────────────────────

def urn(entity_type: str, *parts: str) -> str:
    """urn:ngsi-ld:TrafficEvent:roadwatch:21:4

    격자 키가 "21:4" 라 콜론을 포함한다. NGSI-LD 의 URN 은 콜론 구분이므로
    그대로 이어붙여도 유일성이 깨지지 않는다 — 접두사 길이가 고정이라
    뒤쪽 전체를 격자 키로 되돌릴 수 있다.
    """
    return ":".join([URN_PREFIX, entity_type, PRODUCER, *parts])


def cell_key_from_urn(value: str) -> str | None:
    """urn → 격자 키. 형식이 어긋나면 None."""
    head = f"{URN_PREFIX}:TrafficEvent:{PRODUCER}:"
    if not value.startswith(head):
        return None
    return value[len(head):] or None


# ── 속성 빌더 ─────────────────────────────────────────────────────────

def _iso(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def prop(value: Any, observed_at: Any = None, unit: str | None = None) -> dict | None:
    """Property. 값이 없으면 속성 자체를 넣지 않는다(None 반환)."""
    if value is None:
        return None
    out: dict[str, Any] = {"type": "Property", "value": _iso(value)}
    if observed_at is not None:
        out["observedAt"] = _iso(observed_at)
    if unit is not None:
        out["unitCode"] = unit
    return out


def geo(lat: float | None, lon: float | None) -> dict | None:
    """GeoProperty. GeoJSON 은 [경도, 위도] 순서다 — 뒤집으면 판교가 바다로 간다."""
    if lat is None or lon is None:
        return None
    return {"type": "GeoProperty",
            "value": {"type": "Point", "coordinates": [lon, lat]}}


def rel(target_urn: str | None) -> dict | None:
    if not target_urn:
        return None
    return {"type": "Relationship", "object": target_urn}


def entity(entity_id: str, entity_type: str, attrs: dict[str, Any],
           context: bool = True) -> dict:
    """None 인 속성을 걷어내고 엔티티를 조립한다."""
    out: dict[str, Any] = {"id": entity_id, "type": entity_type}
    out.update({k: v for k, v in attrs.items() if v is not None})
    if context:
        out["@context"] = [CORE_CONTEXT, service_context_url()]
    return out


# ── 엔티티 ────────────────────────────────────────────────────────────

def traffic_event(row: dict, context: bool = True) -> dict:
    """취약구간 하나 → TrafficEvent (Part4/R1 7.2.2).

    row 는 road_issues ⨝ grid_cells 결과.

    category 를 'roadCondition' 으로 고정하고 severity 는 싣지 않는다.
    이 서비스는 원인을 단정하지 않으므로(기획서 3.3) 위험도를 매기지 않고,
    관측된 이벤트율만 값으로 제공한다.
    """
    key = row["cell_key"]
    return entity(
        urn("TrafficEvent", key), "TrafficEvent",
        {
            "name": prop(row.get("road_name")),
            "address": prop(row.get("address")),
            "location": geo(row.get("center_lat"), row.get("center_lon")),
            "category": prop("roadCondition"),
            "subCategory": prop(row.get("classification")),
            "description": prop(_describe(row)),
            # 단수 eventRate 를 쓰지 않는다. 이 구간은 여러 세션에서 관측됐고
            # 갈래(BSM·조인)마다 이벤트 정의가 달라, 최댓값 하나를 "이 구간의
            # 이벤트율"이라 부르면 81.3~87.2% 인 구간이 100% 로 읽힌다.
            "minEventRate": prop(_round(row.get("min_event_rate"))),
            "maxEventRate": prop(_round(row.get("max_event_rate"))),
            "sessionCount": prop(row.get("session_count")),
            "inspectionRecommended": prop(row.get("is_candidate")),
            "dateObserved": prop(row.get("decided_at")),
            "refRoadLink": prop(row.get("link_id")),
            "laneCount": prop(row.get("lanes")),
            "maximumAllowedSpeed": prop(row.get("max_speed"), unit="KMH"),
        },
        context=context,
    )


def vehicle_traffic(row: dict, context: bool = True) -> dict:
    """세션×격자 관측 → VehicleTraffic (Part4/R1 7.2.1).

    row 는 cell_observations ⨝ grid_cells ⨝ sessions 결과.
    measurable=False 는 '이벤트 0%' 가 아니라 '측정 불가' 다 — 이 구분이
    사라지면 데이터가 없는 세션이 안전한 구간으로 오독된다.
    """
    key, sid = row["cell_key"], row["session_id"]
    return entity(
        urn("VehicleTraffic", key, sid), "VehicleTraffic",
        {
            "location": geo(row.get("center_lat"), row.get("center_lon")),
            "refTrafficEvent": rel(urn("TrafficEvent", key)),
            "refDataset": rel(urn("Dataset", sid)),
            "observationCount": prop(row.get("observation_count"),
                                     observed_at=row.get("actual_start")),
            "eventCount": prop(row.get("event_count")),
            "eventRate": prop(_round(row.get("event_rate"))),
            "eventTypes": prop(row.get("event_types")),
            "measurable": prop(row.get("measurable")),
            "dateObserved": prop(row.get("actual_start")),
        },
        context=context,
    )


def _round(v: Any) -> Any:
    return round(v, 4) if isinstance(v, (int, float)) else v


def _describe(row: dict) -> str:
    """원인을 단정하지 않는 문장. 관측 사실만 적는다."""
    cls = row.get("classification")
    n = row.get("session_count") or 0
    lo = _pct(row.get("min_event_rate"))
    hi = _pct(row.get("max_event_rate"))
    if cls == "intermittent":
        return (f"서로 다른 {n}개 주행 세션에서 이상 이벤트가 {lo}~{hi} 로 "
                f"반복 검출된 구간입니다. 원인은 현장 확인 후 확정됩니다.")
    if cls == "always_manual":
        return (f"{n}개 세션 전부에서 이벤트율이 95% 이상입니다. 도로 문제보다 "
                f"상시 수동 운행 정책일 개연성이 있어 후보에서 제외합니다.")
    return f"{n}개 세션에서 이벤트율이 25% 미만입니다. 관찰 대상입니다."


def _pct(v: Any) -> str:
    """백분율 표기. 반올림 규칙은 문서·리포트와 같은 half-up 이다.

    파이썬 기본 포매팅은 half-even 이라 81.25% 를 81.2 로 내리는데, 기획서와
    README 는 81.3 으로 적혀 있다. 같은 수치가 자리마다 다르게 보이면 안 된다.
    """
    if not isinstance(v, (int, float)):
        return "-"
    return f"{Decimal(v * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


# ── 확장 컨텍스트 ─────────────────────────────────────────────────────
#: 코어 컨텍스트에 없는 본 서비스 용어. API 가 직접 서빙한다.
SERVICE_CONTEXT = {
    "@context": {
        "roadwatch": "https://roadwatch.example/ngsi-ld/",
        "eventRate": "roadwatch:eventRate",
        "minEventRate": "roadwatch:minEventRate",
        "maxEventRate": "roadwatch:maxEventRate",
        "observationCount": "roadwatch:observationCount",
        "eventCount": "roadwatch:eventCount",
        "eventTypes": "roadwatch:eventTypes",
        "sessionCount": "roadwatch:sessionCount",
        "measurable": "roadwatch:measurable",
        "inspectionRecommended": "roadwatch:inspectionRecommended",
        "refTrafficEvent": {"@id": "roadwatch:refTrafficEvent", "@type": "@id"},
        "refDataset": {"@id": "roadwatch:refDataset", "@type": "@id"},
        "refRoadLink": "roadwatch:refRoadLink",
        "laneCount": "roadwatch:laneCount",
        "maximumAllowedSpeed": "roadwatch:maximumAllowedSpeed",
        "TrafficEvent": "roadwatch:TrafficEvent",
        "VehicleTraffic": "roadwatch:VehicleTraffic",
    }
}
