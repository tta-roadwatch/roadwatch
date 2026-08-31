"""시민 도로 불편 제보.

자율주행 데이터가 잡아내지 못하는 것이 있다. 공사로 차선이 바뀐 첫날,
표지판을 가린 가로수, 밤에만 안 보이는 노면 표시 같은 것들이다. 차는
«어려웠다»는 신호만 남기고 왜 어려웠는지는 말하지 않는다.

그래서 제보를 «판정»이 아니라 «참고 신호»로 쓴다. 제보가 많다고 취약구간이
되지 않고, 제보가 없다고 후보에서 빠지지도 않는다. 관리자가 현장에 나갈
순서를 정할 때 옆에 놓고 보는 자료다.

접수는 인증 없이 연다. 점검 등록은 시스템 판정을 사람이 뒤집는 행정
행위라 누가 했는지 남아야 하지만, 민원 접수는 판정을 바꾸지 않는다.
공공 민원 창구를 로그인 뒤에 두지 않는 것과 같은 이유다.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .. import errors
from ..deps import cursor

router = APIRouter(prefix="/api", tags=["화면"])

#: 제보 항목. 시민이 «위험도»를 판정하지 않도록 관측한 사실만 고르게 한다.
#: «위험한 도로» 대신 «차선이 안 보인다»를 묻는 것이 이 목록의 요점이다.
CATEGORIES = [
    "차선이 잘 안 보여요",
    "공사로 차선이 바뀌었어요",
    "노면이 파였어요",
    "표지판이 가려져 있어요",
    "신호등이 잘 안 보여요",
    "기타",
]

STATUS_LABELS = {
    "received":  "접수",
    "reviewing": "확인 중",
    "reflected": "점검에 반영",
    "closed":    "종료",
}

#: 제보 좌표를 격자에 붙일 때 허용하는 거리. 격자가 40m 이므로 그 반쯤
#: 되는 값이면 «이 격자를 가리킨 제보»로 봐도 무리가 없다.
SNAP_METERS = 30


class ReportCreate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    category: str
    note: str | None = Field(default=None, max_length=200)


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _row(r: dict) -> dict:
    return {
        "id": r["id"],
        "cell_key": r["cell_key"],
        "lat": r["lat"], "lon": r["lon"],
        "category": r["category"],
        "note": r["note"],
        "status": r["status"],
        "status_label": STATUS_LABELS.get(r["status"], r["status"]),
        "created_at": _iso(r["created_at"]),
        "road_name": r.get("road_name"),
    }


_SELECT = """
select c.*, g.road_name
from citizen_reports c
left join grid_cells g on g.cell_key = c.cell_key
"""


@router.get("/reports/categories", summary="제보 항목")
def categories():
    return {"categories": CATEGORIES}


@router.get("/reports", summary="시민 제보 목록")
def list_reports(cell_key: str | None = None,
                 limit: int = Query(default=50, ge=1, le=200)):
    where, params = [], []
    if cell_key:
        where.append("c.cell_key = %s")
        params.append(cell_key)
    sql = _SELECT + (" where " + " and ".join(where) if where else "")
    sql += " order by c.created_at desc limit %s"
    params.append(limit)
    with cursor() as cur:
        cur.execute(sql, params)
        rows = [_row(r) for r in cur.fetchall()]
    return {
        "reports": rows,
        "total": len(rows),
        "notice": ("시민 제보는 취약구간 판정에 사용하지 않습니다. "
                   "현장점검 순서를 정할 때 참고하는 자료입니다."),
    }


@router.post("/reports", summary="도로 불편 제보", status_code=201)
def create_report(body: ReportCreate):
    if body.category not in CATEGORIES:
        raise errors.bad_request(f"알 수 없는 제보 항목입니다: {body.category}")

    with cursor(commit=True) as cur:
        # 가장 가까운 격자에 붙인다. PostGIS 가 없으므로 위경도 차이를
        # 미터로 환산해 계산한다 — 판교 위도에서 경도 1도는 약 88km 다.
        cur.execute("""
            select cell_key,
                   sqrt(power((center_lat - %s) * 111000, 2)
                      + power((center_lon - %s) * 88000, 2)) as dist_m
            from grid_cells
            order by dist_m
            limit 1
        """, (body.lat, body.lon))
        near = cur.fetchone()
        cell_key = near["cell_key"] if near and near["dist_m"] <= SNAP_METERS else None

        cur.execute("""
            insert into citizen_reports (cell_key, lat, lon, category, note)
            values (%s,%s,%s,%s,%s) returning id
        """, (cell_key, body.lat, body.lon, body.category, body.note))
        new_id = cur.fetchone()["id"]
        cur.execute(_SELECT + " where c.id = %s", (new_id,))
        row = _row(cur.fetchone())

    row["matched"] = cell_key is not None
    row["match_notice"] = (
        "가까운 분석 격자에 연결했습니다." if cell_key
        else f"{SNAP_METERS}m 안에 분석 격자가 없어 위치만 기록했습니다."
    )
    return row


@router.get("/cells/{cell_key}/reports", summary="구간별 시민 제보")
def reports_for_cell(cell_key: str):
    """구간 상세에서 «자율주행 반복 이상» 옆에 함께 놓는 자료."""
    with cursor() as cur:
        cur.execute("select 1 from grid_cells where cell_key = %s", (cell_key,))
        if cur.fetchone() is None:
            raise errors.not_found(f"해당 격자가 없습니다: {cell_key}")
        cur.execute(_SELECT + " where c.cell_key = %s order by c.created_at desc",
                    (cell_key,))
        rows = [_row(r) for r in cur.fetchall()]

    by_category: dict[str, int] = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1

    return {
        "cell_key": cell_key,
        "total": len(rows),
        "by_category": [{"category": k, "count": v}
                        for k, v in sorted(by_category.items(), key=lambda x: -x[1])],
        "reports": rows[:10],
        "notice": "판정 근거가 아니라 현장점검 우선순위를 정할 때 참고하는 신호입니다.",
    }
