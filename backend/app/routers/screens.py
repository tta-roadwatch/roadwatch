"""화면 전용 조회.

Part3 인터페이스가 표준 준수 경로라면 이쪽은 화면 편의 경로다. 표준 응답을
화면에서 매번 재가공하면 프론트에 도메인 지식이 새어나가므로, 집계는 여기서
끝내고 화면은 그리기만 하게 한다.

수치의 출처는 전부 파이프라인이 이미 계산해둔 테이블이다. 여기서 새로
분석하지 않는다.
"""
from __future__ import annotations

from fastapi import APIRouter

from .. import errors
from ..deps import cursor
from .. import families
from ..codebook_facts import COORD_VALIDITY, NORMALIZATION

router = APIRouter(prefix="/api", tags=["화면"])

METRIC_LABEL = {
    "low_speed": "저속 정체",
    "state_deviation": "주행상태 코드 이탈",
    "obstacle_density": "경로 장애물 밀집",
    "emergency": "비상정지",
    "autonomy_disengage": "자율주행 해제",
}

CLASS_LABEL = {
    "intermittent": "간헐 발생 · 점검 권고",
    "always_manual": "상시 수동 · 후보 아님",
    "low": "낮음 · 관찰",
}

@router.get("/dashboard", summary="SCR-01 대시보드")
def dashboard():
    """첫 화면은 통계가 아니라 과업을 제시한다 — '오늘 점검할 곳이 N곳'."""
    with cursor() as cur:
        cur.execute("""
            select
              (select count(*) from road_issues where is_candidate)          as candidates,
              (select count(*) from road_issues where classification='low')  as low,
              (select count(*) from road_issues
                 where classification='always_manual')                        as always_manual,
              (select count(*) from sessions)                                 as sessions,
              (select count(*) from grid_cells)                               as cells,
              (select coalesce(sum(record_count),0) from session_files
                 where dataset_kind <> 'CONTROL')                             as records,
              (select count(*) from inspections where status='recommended')   as pending,
              (select count(*) from inspections where status='resolved')      as resolved,
              (select count(*) from sessions where label_mismatch)            as label_mismatch
        """)
        s = cur.fetchone()

        # 최댓값이 아니라 '반복성' 순으로 정렬한다.
        # 한 세션에서만 100% 인 셀은 흔해서 max 로 줄세우면 상위가 전부 1.0 이 되고
        # 순위가 무의미해진다. 이 서비스의 주장은 '여러 주행에서 반복된다'는 것이므로
        # 관측 세션 수를 먼저 보고, 그다음 최저 이벤트율(=꾸준함)로 가른다.
        cur.execute("""
            select r.cell_key, g.road_name, r.session_count,
                   r.min_event_rate, r.max_event_rate
            from road_issues r join grid_cells g using (cell_key)
            where r.is_candidate
            order by r.session_count desc, r.min_event_rate desc
            limit 5
        """)
        top = cur.fetchall()

    return {
        "headline": f"현장점검이 권고된 구간이 {s['candidates']}곳 있습니다",
        "subtext": ("서로 다른 주행 세션에서 이상 이벤트가 반복 검출된 구간입니다. "
                    "원인은 현장 확인 후 확정됩니다."),
        "stats": {
            "records": s["records"],
            "sessions": s["sessions"],
            "cells": s["cells"],
            "candidates": s["candidates"],
            "pending_inspections": s["pending"],
            "resolved_inspections": s["resolved"],
        },
        "classification": {
            "intermittent": s["candidates"],
            "always_manual": s["always_manual"],
            "low": s["low"],
        },
        "quality_flag": {
            "label_mismatch_sessions": s["label_mismatch"],
            "note": ("파일 라벨의 연도가 실제 수집시각과 다른 세션이 있습니다. "
                     "실제 시각으로 보정해 분석했습니다."),
        },
        "top_candidates": [
            {"cell_key": r["cell_key"], "road_name": r["road_name"],
             "session_count": r["session_count"],
             "min_event_rate": _r(r["min_event_rate"]),
             "max_event_rate": _r(r["max_event_rate"])}
            for r in top
        ],
    }


@router.get("/normalization", summary="SCR-03 표준 정규화")
def normalization():
    """데모 하이라이트. 토글 하나로 15,585건의 판정이 뒤집히는 장면.

    수치는 파이프라인 실행 중 실측해 codebook.VERIFIED 에 고정한 값이다.
    """
    with cursor() as cur:
        cur.execute("""
            select dataset_kind, sum(record_count) as n, count(*) as files
            from session_files group by dataset_kind order by dataset_kind
        """)
        by_kind = cur.fetchall()
        cur.execute("""
            select id, codebook, label_mismatch, label_date, actual_start
            from sessions where codebook is not null order by id
        """)
        sessions = cur.fetchall()

    return {
        "ingest": {
            "by_kind": [
                {"kind": r["dataset_kind"], "files": r["files"], "records": int(r["n"])}
                for r in by_kind
            ],
            "total": sum(int(r["n"]) for r in by_kind if r["dataset_kind"] != "CONTROL"),
        },
        "normalization": NORMALIZATION,
        "sessions": [
            {"session_id": r["id"], "codebook": r["codebook"],
             "inverted": r["codebook"] == "inverted",
             "label_date": _iso(r["label_date"]),
             "actual_start": _iso(r["actual_start"]),
             "label_mismatch": r["label_mismatch"]}
            for r in sessions
        ],
        "coord_validity": COORD_VALIDITY,
    }


@router.get("/quality", summary="SCR-04 품질검증")
def quality():
    with cursor() as cur:
        cur.execute("""
            select session_id, check_name, status, detail
            from quality_checks order by session_id, check_name
        """)
        rows = cur.fetchall()
        cur.execute("""
            select status, count(*) as n from quality_checks group by status
        """)
        summary = {r["status"]: r["n"] for r in cur.fetchall()}
    return {
        "summary": summary,
        "total": len(rows),
        "checks": [
            {"session_id": r["session_id"], "check_name": r["check_name"],
             "status": r["status"], "detail": r["detail"]}
            for r in rows
        ],
    }


@router.get("/cells", summary="SCR-05 격자 목록")
def cells(candidates_only: bool = False):
    """지도에 뿌릴 격자. 판정이 없는 셀(관측 1세션)도 회색으로 보여야 하므로
    grid_cells 를 기준으로 left join 한다."""
    sql = """
        select g.cell_key, g.center_lat, g.center_lon, g.road_name, g.address,
               g.link_id, g.lanes, g.max_speed, g.link_dist_m,
               r.classification, r.session_count, r.min_event_rate, r.max_event_rate,
               r.is_candidate,
               (select count(*) from cell_observations o
                  where o.cell_key = g.cell_key) as observed_sessions,
               (select status from inspections i
                  where i.cell_key = g.cell_key
                  order by i.created_at desc limit 1) as inspection_status
        from grid_cells g left join road_issues r using (cell_key)
    """
    if candidates_only:
        sql += " where r.is_candidate"
    sql += " order by r.max_event_rate desc nulls last, g.cell_key"
    with cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        {
            "cell_key": r["cell_key"],
            "lat": r["center_lat"], "lon": r["center_lon"],
            "road_name": r["road_name"], "address": r["address"],
            "link_id": r["link_id"], "lanes": r["lanes"],
            "max_speed": r["max_speed"], "link_dist_m": r["link_dist_m"],
            "classification": r["classification"],
            "classification_label": CLASS_LABEL.get(r["classification"]),
            "session_count": r["session_count"],
            "observed_sessions": r["observed_sessions"],
            "min_event_rate": _r(r["min_event_rate"]),
            "max_event_rate": _r(r["max_event_rate"]),
            "is_candidate": bool(r["is_candidate"]),
            "inspection_status": r["inspection_status"],
        }
        for r in rows
    ]


@router.get("/cells/{cell_key}", summary="SCR-06 구간 상세")
def cell_detail(cell_key: str):
    with cursor() as cur:
        cur.execute("""
            select g.cell_key, g.center_lat, g.center_lon, g.road_name, g.address,
                   g.link_id, g.lanes, g.max_speed, g.link_dist_m,
                   r.classification, r.session_count,
                   r.min_event_rate, r.max_event_rate, r.is_candidate
            from grid_cells g left join road_issues r using (cell_key)
            where g.cell_key = %s
        """, (cell_key,))
        cell = cur.fetchone()
        if cell is None:
            raise errors.not_found(f"해당 격자가 없습니다: {cell_key}")

        # 관측된 세션 + 관측 안 된 세션을 모두 보여줘야 '측정 불가' 가 드러난다
        cur.execute("""
            select s.id as session_id, s.actual_start, s.available_metrics,
                   o.observation_count, o.event_count, o.event_rate,
                   o.event_types, o.measurable
            from sessions s
            left join cell_observations o
                   on o.session_id = s.id and o.cell_key = %s
            order by s.id
        """, (cell_key,))
        obs = cur.fetchall()

        cur.execute("""
            select id, status, findings, action, inspector, inspected_at, created_at
            from inspections where cell_key = %s order by created_at desc
        """, (cell_key,))
        insp = cur.fetchall()

    return {
        "cell": {
            "cell_key": cell["cell_key"],
            "lat": cell["center_lat"], "lon": cell["center_lon"],
            "road_name": cell["road_name"], "address": cell["address"],
            "link_id": cell["link_id"], "lanes": cell["lanes"],
            "max_speed": cell["max_speed"], "link_dist_m": cell["link_dist_m"],
            "classification": cell["classification"],
            "classification_label": CLASS_LABEL.get(cell["classification"]),
            "session_count": cell["session_count"],
            "min_event_rate": _r(cell["min_event_rate"]),
            "max_event_rate": _r(cell["max_event_rate"]),
            "is_candidate": bool(cell["is_candidate"]),
        },
        "observations": [
            {
                "session_id": o["session_id"],
                "observed_at": _iso(o["actual_start"]),
                # 관측 자체가 없으면 measurable 이 아니라 observed 가 False 다.
                # 둘 다 '이벤트 0%' 로 보이면 안 되므로 화면에 그대로 넘긴다.
                "observed": o["observation_count"] is not None,
                "measurable": bool(o["measurable"]) if o["measurable"] is not None else False,
                "observation_count": o["observation_count"],
                "event_count": o["event_count"],
                "event_rate": _r(o["event_rate"]),
                "event_types": o["event_types"],
                "metric_family": families.family_of(o["available_metrics"]),
                "metric_family_label": families.FAMILY_LABEL.get(families.family_of(o["available_metrics"])),
                "available_metrics": [
                    METRIC_LABEL.get(m, m) for m in (o["available_metrics"] or [])
                ],
            }
            for o in obs
        ],
        "inspections": [_inspection(i) for i in insp],
        # 갈래별 요약. 화면은 이걸로 "같은 정의끼리" 비교해 보여준다.
        "by_family": _family_summary(obs),
        "family_notice": families.NOTICE,
    }


def _family_summary(obs: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for o in obs:
        if o["observation_count"] is None or not o["measurable"]:
            continue
        fam = families.family_of(o["available_metrics"])
        if fam is None:
            continue
        b = out.setdefault(fam, {"label": families.FAMILY_LABEL[fam], "sessions": [],
                                 "min_event_rate": None, "max_event_rate": None})
        rate = o["event_rate"] or 0
        b["sessions"].append({"session_id": o["session_id"],
                              "event_rate": _r(rate),
                              "event_count": o["event_count"],
                              "observation_count": o["observation_count"]})
        b["min_event_rate"] = rate if b["min_event_rate"] is None else min(b["min_event_rate"], rate)
        b["max_event_rate"] = rate if b["max_event_rate"] is None else max(b["max_event_rate"], rate)
    for b in out.values():
        b["min_event_rate"] = _r(b["min_event_rate"])
        b["max_event_rate"] = _r(b["max_event_rate"])
    return out


@router.get("/cells/{cell_key}/comparison", summary="SCR-08 조치 전·후")
def comparison(cell_key: str):
    """조치일을 기준으로 관측을 양쪽으로 갈라 보여준다.

    이 구간에 «조치 완료»로 기록된 점검이 있으면 그 완료일이 기준선이 된다.
    완료일 앞뒤로 실제 주행 세션이 모두 있으면 양쪽 다 실측값이다 —
    시뮬레이션이 아니다.

    한쪽에만 세션이 있으면(대개 조치 후 데이터가 아직 없다) 비교를 만들지
    않고 «재측정 대기»로 둔다. 없는 값을 지어내는 대신 무엇을 기다리는지
    밝히는 편이 낫다.

    조치 기록이 아예 없으면 비교할 기준선이 없으므로 관측 이력만 돌려준다.

    주의: 앞뒤 값이 달라도 그것이 조치 «때문»이라고 말하지 않는다. 계절·
    시간대·교통량이 함께 달라졌을 수 있다. 이 서비스는 원인을 단정하지
    않으므로 여기서도 관측 사실까지만 보여준다.
    """
    with cursor() as cur:
        cur.execute("select road_name from grid_cells where cell_key = %s", (cell_key,))
        g = cur.fetchone()
        if g is None:
            raise errors.not_found(f"해당 격자가 없습니다: {cell_key}")

        cur.execute("""
            select o.session_id, o.observation_count, o.event_count, o.event_rate,
                   s.actual_start
            from cell_observations o join sessions s on s.id = o.session_id
            where o.cell_key = %s and o.measurable
            order by s.actual_start
        """, (cell_key,))
        obs = cur.fetchall()
        if not obs:
            raise errors.not_found(f"비교할 관측이 없습니다: {cell_key}")

        cur.execute("""
            select id, status, findings, action, cause, inspector,
                   inspected_at, created_at, completed_on
            from inspections
            where cell_key = %s
            order by created_at
        """, (cell_key,))
        insp = cur.fetchall()

    def _obs(o):
        return {"session_id": o["session_id"], "observed_at": _iso(o["actual_start"]),
                "event_rate": _r(o["event_rate"]), "event_count": o["event_count"],
                "observation_count": o["observation_count"]}

    def _side(rows):
        """여러 세션을 한쪽 값으로 묶는다 — 관측 수로 가중 평균한다.

        단순 평균을 내면 3초만 관측된 세션과 300초 관측된 세션이 같은
        무게를 갖는다. 이벤트율은 관측 대비 비율이므로 관측 수로 눌러야
        맞다.
        """
        obs_n = sum(r["observation_count"] or 0 for r in rows)
        ev_n = sum(r["event_count"] or 0 for r in rows)
        return {
            "sessions": [_obs(r) for r in rows],
            "session_count": len(rows),
            "event_count": ev_n,
            "observation_count": obs_n,
            "event_rate": _r(ev_n / obs_n) if obs_n else None,
            "measured": True,
        }

    # 조치가 끝난 기록 가운데 가장 최근 완료일을 기준선으로 잡는다
    done = [i for i in insp if i["status"] == "resolved" and i["completed_on"]]
    baseline = max((i["completed_on"] for i in done), default=None)

    result = {
        "cell_key": cell_key,
        "road_name": g["road_name"],
        "baseline": _iso(baseline),
        "history": [
            {"status": i["status"], "findings": i["findings"], "action": i["action"],
             "cause": i["cause"], "completed_on": _iso(i["completed_on"]),
             "at": _iso(i["inspected_at"] or i["created_at"])}
            for i in insp
        ],
        "measured_sessions": [_obs(o) for o in obs],
    }

    if baseline is None:
        result |= {
            "state": "no_action",
            "before": None, "after": None,
            "notice": ("이 구간에는 완료된 조치 기록이 없습니다. 조치를 «조치 완료»로 "
                       "등록하면 그 날짜를 기준으로 전·후 관측을 비교합니다."),
        }
        return result

    before = [o for o in obs if o["actual_start"].date() < baseline]
    after = [o for o in obs if o["actual_start"].date() >= baseline]

    if not before or not after:
        result |= {
            "state": "awaiting_remeasure",
            "before": _side(before) if before else None,
            "after": _side(after) if after else None,
            "notice": ("조치일 이후의 주행 세션이 아직 없어 비교할 수 없습니다. "
                       "신규 주행 데이터가 공개되면 자동으로 재측정합니다."
                       if not after else
                       "조치일 이전의 주행 세션이 없어 비교할 수 없습니다."),
        }
        return result

    b, a = _side(before), _side(after)
    delta = None
    if b["event_rate"] is not None and a["event_rate"] is not None:
        delta = _r(a["event_rate"] - b["event_rate"])

    result |= {
        "state": "compared",
        "before": b, "after": a,
        "delta": delta,
        "notice": ("조치일을 기준으로 나눈 실제 관측값입니다. 값의 변화가 조치 "
                   "때문인지는 확정하지 않습니다 — 계절·시간대·교통량이 함께 "
                   "달라졌을 수 있습니다."),
    }
    return result


# ── 공용 ──────────────────────────────────────────────────────────────

def _inspection(r: dict) -> dict:
    return {
        "id": r["id"], "status": r["status"], "findings": r["findings"],
        "action": r["action"], "inspector": r["inspector"],
        "inspected_at": _iso(r["inspected_at"]), "created_at": _iso(r["created_at"]),
    }


def _r(v):
    return round(v, 4) if isinstance(v, (int, float)) else v


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v
