"""현장점검 — SCR-07.

이 서비스에서 유일한 쓰기 경로다. 분석 결과는 판정이지 결론이 아니고,
도로관리자가 현장에서 확인해 확정하거나 뒤집는다. 그 번복 지점이 여기다.

체크리스트에 '상시 수동 운행 구간(도로 문제 아님)' 항목이 있는 것이 핵심이다.
시스템이 취약구간으로 올린 것을 사람이 오탐으로 내릴 수 있어야, AI가 원인을
단정하지 않는다는 주장이 화면에서 실제로 성립한다.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import auth, errors
from ..deps import cursor

router = APIRouter(prefix="/api", tags=["화면"])

#: 점검 결과 선택지. '도로 문제 아님' 항목이 오탐 배제용이다.
FINDINGS = [
    "차선 마모", "표지판 가림", "신호등 시인성", "공사구간", "노면 상태",
    "상시 수동 운행 구간 (도로 문제 아님)", "특이사항 없음", "기타",
]

#: 이 항목이 선택되면 도로 문제가 아니므로 후보에서 내린다
NOT_A_ROAD_ISSUE = "상시 수동 운행 구간 (도로 문제 아님)"

#: 업무 흐름. 순서가 곧 관리자의 하루다 — 후보로 올라오면 담당자를 정하고,
#: 현장을 보고, 고칠 것이 있으면 조치를 기다렸다가 끝낸다.
#: not_applicable 은 흐름 밖이다. 도로 문제가 아니라고 확인된 것이라
#: 어느 단계에서든 여기로 빠질 수 있다.
WORKFLOW = ("recommended", "scheduled", "inspecting", "action_needed", "resolved")
STATUSES = (*WORKFLOW, "not_applicable")

#: 아직 담당자 손에 걸려 있는 상태. resolved·not_applicable 은 끝난 것이라
#: 여기 들지 않는다 — 끝난 뒤에는 같은 구간에 새 점검을 시작할 수 있다.
OPEN_STATUSES = ("recommended", "scheduled", "inspecting", "action_needed")

STATUS_LABELS = {
    "recommended":    "신규 후보",
    "scheduled":      "점검 예정",
    "inspecting":     "점검 중",
    "action_needed":  "조치 필요",
    "resolved":       "조치 완료",
    "not_applicable": "도로 문제 아님",
}


class InspectionCreate(BaseModel):
    cell_key: str
    findings: list[str] = Field(default_factory=list)
    action: str | None = None
    cause: str | None = None
    assignee: str | None = None
    scheduled_for: date | None = None
    status: str = "inspecting"
    # inspector 는 받지 않는다. 누가 판정을 뒤집었는지는 토큰에서 채워야
    # 기록으로서 의미가 있다 — 클라이언트가 아무 이름이나 적게 두면 안 된다.


class InspectionUpdate(BaseModel):
    findings: list[str] | None = None
    action: str | None = None
    cause: str | None = None
    assignee: str | None = None
    scheduled_for: date | None = None
    completed_on: date | None = None
    status: str | None = None


def _row(r: dict) -> dict:
    return {
        "id": r["id"], "cell_key": r["cell_key"], "status": r["status"],
        "findings": r["findings"], "action": r["action"], "inspector": r["inspector"],
        "inspected_at": _iso(r["inspected_at"]), "created_at": _iso(r["created_at"]),
        "cause": r.get("cause"),
        "assignee": r.get("assignee"),
        "scheduled_for": _iso(r.get("scheduled_for")),
        "completed_on": _iso(r.get("completed_on")),
        "status_label": STATUS_LABELS.get(r["status"], r["status"]),
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


@router.get("/inspections/workbox", summary="점검·조치 업무함")
def workbox():
    """상태별 건수와 오늘 할 일.

    대시보드가 «권고 24곳»만 보여주면 어제와 오늘이 같아 보인다. 관리자에게
    필요한 것은 총계가 아니라 «지금 내 손에 뭐가 걸려 있나»다. 그래서
    업무 흐름 순서대로 세고, 기한이 지난 것과 오늘 예정을 따로 뽑는다.
    """
    with cursor() as cur:
        cur.execute("select status, count(*) n from inspections group by status")
        counts = {r["status"]: r["n"] for r in cur.fetchall()}

        # 예정일이 지났는데 아직 안 끝난 것 — 가장 먼저 봐야 할 줄
        cur.execute(_SELECT + """
            where i.scheduled_for < current_date
              and i.status in ('scheduled', 'inspecting', 'action_needed')
            order by i.scheduled_for
        """)
        overdue = [_row(r) for r in cur.fetchall()]

        cur.execute(_SELECT + """
            where i.scheduled_for = current_date
              and i.status in ('scheduled', 'inspecting', 'action_needed')
            order by i.cell_key
        """)
        today = [_row(r) for r in cur.fetchall()]

    stages = [{"status": st, "label": STATUS_LABELS[st], "count": counts.get(st, 0)}
              for st in WORKFLOW]
    return {
        "stages": stages,
        "not_applicable": counts.get("not_applicable", 0),
        "open_total": sum(counts.get(st, 0) for st in WORKFLOW if st != "resolved"),
        "overdue": overdue,
        "today": today,
        "notice": ("업무함은 시스템 판정이 아니라 담당자의 처리 상태를 관리합니다. "
                   "«조치 완료»는 현장 조치가 끝났다는 뜻이며, 이벤트율이 실제로 "
                   "줄었는지는 신규 주행 데이터로 다시 확인합니다."),
    }


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


@router.post("/inspections", summary="점검 등록·진행", status_code=201)
def create_inspection(body: InspectionCreate, user: dict = auth.RequireUser):
    if body.status not in STATUSES:
        raise errors.bad_request(f"알 수 없는 상태입니다: {body.status}")
    bad = [f for f in body.findings if f not in FINDINGS]
    if bad:
        raise errors.bad_request(f"알 수 없는 점검 항목입니다: {', '.join(bad)}")

    with cursor(commit=True) as cur:
        cur.execute("select 1 from grid_cells where cell_key = %s", (body.cell_key,))
        if cur.fetchone() is None:
            raise errors.not_found(f"해당 격자가 없습니다: {body.cell_key}")

        # 같은 구간에 진행 중인 점검이 있으면 새로 만들지 않고 그것을 진행시킨다.
        #
        # 한 자리가 «신규 후보»와 «점검 중»에 동시에 놓이면 업무함이 같은
        # 장소를 두 번 세어, 담당자가 실제보다 많은 일이 걸려 있다고 읽는다.
        # 후보로 올라온 기록이 이미 있으므로, 현장에 다녀온 사람은 새 기록을
        # 만드는 게 아니라 그 기록을 채우는 것이 맞다.
        cur.execute(
            """select id from inspections
               where cell_key = %s and status = any(%s)
               order by created_at limit 1""",
            (body.cell_key, list(OPEN_STATUSES)),
        )
        open_row = cur.fetchone()
        if open_row:
            cur.execute(
                """update inspections
                   set status = %s, findings = %s, action = %s, cause = %s,
                       assignee = coalesce(%s, assignee),
                       scheduled_for = coalesce(%s, scheduled_for),
                       inspector = %s, inspected_at = %s,
                       completed_on = case when %s = 'resolved'
                                           then coalesce(completed_on, %s)
                                           else completed_on end
                   where id = %s""",
                (body.status, body.findings, body.action, body.cause,
                 body.assignee, body.scheduled_for,
                 user["display_name"] or user["username"],
                 datetime.now(timezone.utc),
                 body.status, date.today(), open_row["id"]),
            )
            _apply_not_a_road_issue(cur, body.cell_key, body.findings)
            cur.execute(_SELECT + " where i.id = %s", (open_row["id"],))
            return _row(cur.fetchone())

        cur.execute(
            """insert into inspections (cell_key, status, findings, action, cause,
                                        assignee, scheduled_for, inspector,
                                        inspected_at, completed_on)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
            (body.cell_key, body.status, body.findings, body.action, body.cause,
             body.assignee, body.scheduled_for,
             user["display_name"] or user["username"],
             datetime.now(timezone.utc) if body.status != "recommended" else None,
             # 조치 완료로 바로 등록하면 그날을 완료일로 잡는다. 개선 전·후
             # 비교가 이 날짜를 기준선으로 삼는다.
             date.today() if body.status == "resolved" else None),
        )
        new_id = cur.fetchone()["id"]
        _apply_not_a_road_issue(cur, body.cell_key, body.findings)
        cur.execute(_SELECT + " where i.id = %s", (new_id,))
        return _row(cur.fetchone())


@router.patch("/inspections/{inspection_id}", summary="점검 상태 변경")
def update_inspection(inspection_id: int, body: InspectionUpdate,
                      user: dict = auth.RequireUser):
    if body.status is not None and body.status not in STATUSES:
        raise errors.bad_request(f"알 수 없는 상태입니다: {body.status}")

    sets, params = [], []
    for col, val in (("status", body.status), ("action", body.action),
                     ("findings", body.findings), ("cause", body.cause),
                     ("assignee", body.assignee), ("scheduled_for", body.scheduled_for),
                     ("completed_on", body.completed_on)):
        if val is not None:
            sets.append(f"{col} = %s")
            params.append(val)
    if not sets:
        raise errors.bad_request("변경할 항목이 없습니다")
    # 조치 완료로 넘길 때 완료일을 안 주면 오늘로 잡는다. 이 날짜가
    # 개선 전·후 비교의 기준선이라 비워두면 비교를 못 한다.
    if body.status == "resolved" and body.completed_on is None:
        sets.append("completed_on = coalesce(completed_on, %s)")
        params.append(date.today())
    # 손댄 사람과 시각은 항상 갱신한다. 누가 뒤집었는지가 기록의 핵심이다.
    sets += ["inspector = %s", "inspected_at = %s"]
    params += [user["display_name"] or user["username"], datetime.now(timezone.utc),
               inspection_id]

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
