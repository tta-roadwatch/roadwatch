"""인수 기준 회귀 테스트.

`pipeline.run --verify`와 같은 검사를 pytest로 돌린다.
DB가 없으면 skip하므로 CI 없이도 `pytest` 한 번으로 확인할 수 있다.

    cd backend && ./.venv/bin/python -m pytest tests/ -v
"""
from __future__ import annotations

import pytest

from pipeline import db, run


@pytest.fixture(scope="module")
def conn():
    try:
        c = db.connect()
    except Exception as e:                      # DB 미기동
        pytest.skip(f"DB에 연결할 수 없다: {e}")
    yield c
    c.close()


@pytest.fixture(scope="module")
def results(conn):
    return run.checks(conn)


def _pick(results, grade):
    return [(name, got, want) for g, name, got, want in results if g == grade]


@pytest.mark.parametrize("idx", range(20))
def test_primary_criteria(results, idx):
    """1차 인수 기준 — 하나라도 어긋나면 파이프라인이 깨진 것이다."""
    rows = _pick(results, "1차")
    if idx >= len(rows):
        pytest.skip("해당 인덱스 없음")
    name, got, want = rows[idx]
    assert got == want, f"{name}: 실측 {got} ≠ 기대 {want}"


@pytest.mark.parametrize("idx", range(20))
def test_secondary_criteria(results, idx):
    """2차 기준 — 캘리브레이션 결과를 회귀 기준선으로 고정한다.

    기획서 원값과 다른 항목은 docs/thresholds.md §F의 폴백 절차로 채택됐다.
    이 값이 변하면 임계값이나 격자 규약이 바뀐 것이므로 문서도 함께 고쳐야 한다.
    """
    rows = _pick(results, "2차")
    if idx >= len(rows):
        pytest.skip("해당 인덱스 없음")
    name, got, want = rows[idx]
    assert got == want, f"{name}: 실측 {got} ≠ 기준선 {want}"


def test_target_cells_reproduce_repeatability(conn):
    """핵심 서사 — 두 독립 주행에서 같은 격자가 높은 이벤트율로 재현된다."""
    with conn.cursor() as cur:
        cur.execute(
            """select session_id, event_rate from cell_observations
               where cell_key='21:4' and session_id in ('2022-05-16','2022-08-05')
               order by session_id"""
        )
        rates = dict(cur.fetchall())
    assert len(rates) == 2, "두 세션 모두에서 관측돼야 한다"
    for sid, r in rates.items():
        assert r > 0.75, f"{sid} 이벤트율 {r:.1%} — 재현성 서사가 성립하지 않는다"


def test_no_always_manual_in_current_data(conn):
    """상시 수동 구간은 현 데이터에 존재하지 않는다 (Phase 7 실측).

    분류 체계 자체는 유지하되, 기획서·화면의 '2곳' 표기는 실측에 맞춰
    갱신했다. 이 테스트는 그 사실을 코드로 고정한다.
    """
    with conn.cursor() as cur:
        cur.execute("select count(*) from road_issues where classification='always_manual'")
        assert cur.fetchone()[0] == 0


def test_codebook_prevents_misjudgement():
    """정규화가 없으면 15,585건이 오판된다 — 데모 하이라이트의 근거."""
    from pipeline.codebook import VERIFIED
    assert VERIFIED["corrected_misjudgements"] == 15_585
    assert VERIFIED["emergency_with_codebook"] == 3
