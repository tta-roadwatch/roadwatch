"""⑦ 반복성 판정 — 3단계 분류.

분석 A(BSM)와 분석 B(조인)를 같은 격자 위에서 병합한다. 셀별로 그 셀을
관측한 모든 measurable 세션의 이벤트율을 모아 판정한다.

분류 규칙 (경계 명시 — 계획 §3.9):
    always_manual : 모든 세션 rate ≥ 0.95   → 운영 정책 가능성, 후보 아님
    low           : 모든 세션 rate < 0.25   → 관찰
    intermittent  : 그 외 전부 (혼합 포함)   → 취약구간 후보

캘리브레이션 참고 (docs/thresholds.md §F):
    격자 규약은 BSM 3세션의 '공통 관측 셀 10곳'(기획서 5.3 분석 A)을
    독립적으로 재현했다. 분류 분포는 실측(0/10/0)이 기획서(2/6/2)와 다르며
    폴백 원칙에 따라 실측을 채택, 문서·화면을 Phase 8에서 갱신한다.
"""
from __future__ import annotations

import psycopg

ALWAYS, INTER, LOW = "always_manual", "intermittent", "low"

#: 후보 셀에 자동 생성되는 점검 권고 상태
RECOMMENDED = "recommended"


def classify(rates: list[float]) -> str:
    if all(r >= 0.95 for r in rates):
        return ALWAYS
    if all(r < 0.25 for r in rates):
        return LOW
    return INTER


def run(conn: psycopg.Connection) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE road_issues CASCADE")
        cur.execute("TRUNCATE inspections RESTART IDENTITY")

        cur.execute(
            """select cell_key,
                      array_agg(event_rate order by session_id) as rates,
                      count(*) as n
               from cell_observations
               where measurable
               group by cell_key
               having count(*) >= 2"""
        )
        rows = cur.fetchall()

        summary = {ALWAYS: 0, INTER: 0, LOW: 0}
        for cell_key, rates, n in rows:
            cls = classify(list(rates))
            summary[cls] += 1
            cur.execute(
                """insert into road_issues
                   (cell_key, classification, session_count,
                    min_event_rate, max_event_rate, is_candidate)
                   values (%s,%s,%s,%s,%s,%s)""",
                (cell_key, cls, n, min(rates), max(rates), cls == INTER),
            )
            if cls == INTER:
                cur.execute(
                    "insert into inspections (cell_key, status) values (%s,%s)",
                    (cell_key, RECOMMENDED),
                )
    conn.commit()
    return summary
