"""현장점검 — SCR-07.

이 서비스에서 유일한 쓰기 경로다. 분석 결과는 판정이지 결론이 아니고,
도로관리자가 현장에서 확인해 확정하거나 뒤집는다. 그 번복 지점이 여기다.

체크리스트에 '상시 수동 운행 구간(도로 문제 아님)' 항목이 있는 것이 핵심이다.
시스템이 취약구간으로 올린 것을 사람이 오탐으로 내릴 수 있어야, AI가 원인을
단정하지 않는다는 주장이 화면에서 실제로 성립한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import errors
from ..deps import cursor

router = APIRouter(prefix="/api", tags=["화면"])

#: 점검 결과 선택지. '도로 문제 아님' 항목이 오탐 배제용이다.
FINDINGS = [
    "차선 마모", "표지판 가림", "신호등 시인성", "공사구간", "노면 상태",
    "상시 수동 운행 구간 (도로 문제 아님)", "특이사항 없음", "기타",
]

#: 이 항목이 선택되면 도로 문제가 아니므로 후보에서 내린다
NOT_A_ROAD_ISSUE = "상시 수동 운행 구간 (도로 문제 아님)"

STATUSES = ("recommended", "inspecting", "resolved", "not_applicable")


class InspectionCreate(BaseModel):
    cell_key: str
    findings: list[str] = Field(default_factory=list)
    action: str | None = None
    inspector: str | None = None
    status: str = "inspecting"


class InspectionUpdate(BaseModel):
    findings: list[str] | None = None
    action: str | None = None
    inspector: str | None = None
    status: str | None = None


def _row(r: dict) -> dict:
    return {
        "id": r["id"], "cell_key": r["cell_key"], "status": r["status"],
        "findings": r["findings"], "action": r["action"], "inspector": r["inspector"],
        "inspected_at": _iso(r["inspected_at"]), "created_at": _iso(r["created_at"]),
        "road_name": r.get("road_name"),
        "classification": r.get("classification"),
    }


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


_SELECT = """
select i.*, g.road_name, r.classification
from inspections i
join grid_cells g on g.cell_key = i.cell_key
left join road_issues r on r.cell_key = i.cell_key
"""


@router.get("/inspections/findings", summary="점검 결과 선택지")
def findings_options():
    return {"findings": FINDINGS, "not_a_road_issue": NOT_A_ROAD_ISSUE,
            "statuses": list(STATUSES)}


@router.get("/inspections", summary="점검 목록")
def list_inspections(status: str | None = None, cell_key: str | None = None):
    sql, params = _SELECT, []
    where = []
    if status:
        where.append("i.status = %s")
        params.append(status)
    if cell_key:
        where.append("i.cell_key = %s")
        params.append(cell_key)
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by i.created_at desc"
    with cursor() as cur:
        cur.execute(sql, params)
        return [_row(r) for r in cur.fetchall()]


@router.post("/inspections", summary="점검 등록", status_code=201)
def create_inspection(body: InspectionCreate):
    if body.status not in STATUSES:
        raise errors.bad_request(f"알 수 없는 상태입니다: {body.status}")
    bad = [f for f in body.findings if f not in FINDINGS]
    if bad:
        raise errors.bad_request(f"알 수 없는 점검 항목입니다: {', '.join(bad)}")

    with cursor(commit=True) as cur:
        cur.execute("select 1 from grid_cells where cell_key = %s", (body.cell_key,))
        if cur.fetchone() is None:
            raise errors.not_found(f"해당 격자가 없습니다: {body.cell_key}")
        cur.execute(
            """insert into inspections (cell_key, status, findings, action, inspector,
                                        inspected_at)
               values (%s,%s,%s,%s,%s,%s) returning id""",
            (body.cell_key, body.status, body.findings, body.action, body.inspector,
             datetime.now(timezone.utc) if body.status != "recommended" else None),
        )
        new_id = cur.fetchone()["id"]
        _apply_not_a_road_issue(cur, body.cell_key, body.findings)
        cur.execute(_SELECT + " where i.id = %s", (new_id,))
        return _row(cur.fetchone())


@router.patch("/inspections/{inspection_id}", summary="점검 상태 변경")
def update_inspection(inspection_id: int, body: InspectionUpdate):
    if body.status is not None and body.status not in STATUSES:
        raise errors.bad_request(f"알 수 없는 상태입니다: {body.status}")

    sets, params = [], []
    for col, val in (("status", body.status), ("action", body.action),
                     ("inspector", body.inspector), ("findings", body.findings)):
        if val is not None:
            sets.append(f"{col} = %s")
            params.append(val)
    if not sets:
        raise errors.bad_request("변경할 항목이 없습니다")
    sets.append("inspected_at = %s")
    params.append(datetime.now(timezone.utc))
    params.append(inspection_id)

    with cursor(commit=True) as cur:
        cur.execute(
            f"update inspections set {', '.join(sets)} where id = %s returning cell_key",
            params)
        row = cur.fetchone()
        if row is None:
            raise errors.not_found(f"해당 점검이 없습니다: {inspection_id}")
        if body.findings is not None:
            _apply_not_a_road_issue(cur, row["cell_key"], body.findings)
        cur.execute(_SELECT + " where i.id = %s", (inspection_id,))
        return _row(cur.fetchone())


def _apply_not_a_road_issue(cur, cell_key: str, findings: list[str]) -> None:
    """'도로 문제 아님'이 선택되면 후보에서 내린다.

    분류(classification)는 분석 결과이므로 바꾸지 않는다. 사람이 뒤집은 것은
    '점검 대상인가'이지 '어떤 패턴인가'가 아니다. 그래서 is_candidate 만 내린다.
    """
    if NOT_A_ROAD_ISSUE in findings:
        cur.execute(
            "update road_issues set is_candidate = false where cell_key = %s",
            (cell_key,))
