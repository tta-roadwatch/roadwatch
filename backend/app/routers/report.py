"""AI 점검 리포트 초안 — SCR-06.

ANTHROPIC_API_KEY 가 있으면 Claude 를 실제로 호출하고, 없으면 규칙 기반
템플릿으로 자동 대체한다. 심사자가 키 없이 클론해도 화면이 깨지지 않아야
하므로 폴백이 기본 동작이고, 응답의 generated_by 로 어느 쪽인지 밝힌다.

프롬프트에서 가장 중요한 건 **원인을 단정하지 못하게 막는 것**이다.
이 서비스의 설계 원칙(기획서 3.3)이 "관측은 보고하되 원인은 단정하지 않는다"
인데, 리포트가 "차선이 마모되었습니다"라고 써버리면 그 원칙이 화면에서
무너진다. 점검 우선순위 제안까지만 하게 한다.
"""
from __future__ import annotations

import os
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter

from .. import errors
from ..deps import cursor

router = APIRouter(prefix="/api", tags=["화면"])

MODEL = "claude-sonnet-5"
MAX_TOKENS = 700

SYSTEM = """당신은 도로관리자를 돕는 분석 보조입니다. 자율주행 주행 데이터에서
검출된 취약구간에 대해 현장점검 리포트 초안을 씁니다.

반드시 지킬 것:
- 원인을 단정하지 마세요. "차선이 마모되었습니다" 같은 단정은 금지입니다.
  데이터는 이상 이벤트가 반복 관측되었다는 사실만 말해줍니다.
- 대신 어떤 점검 항목을 우선 확인하면 좋을지 제안하세요.
- 주어진 수치만 쓰고, 없는 값을 지어내지 마세요.
- 측정 불가와 이벤트 0%를 혼동하지 마세요.
- 한국어 존댓말로, 공문서 톤으로, 4~6문장으로 쓰세요.
- 마지막 줄에 "※ 본 리포트는 원인을 진단하지 않으며 점검 우선순위를 제안합니다."
  를 그대로 넣으세요."""


def _facts(cell_key: str) -> dict:
    with cursor() as cur:
        cur.execute("""
            select g.cell_key, g.road_name, g.lanes, g.max_speed, g.link_dist_m,
                   r.classification, r.session_count,
                   r.min_event_rate, r.max_event_rate
            from grid_cells g left join road_issues r using (cell_key)
            where g.cell_key = %s
        """, (cell_key,))
        cell = cur.fetchone()
        if cell is None:
            raise errors.not_found(f"해당 격자가 없습니다: {cell_key}")
        cur.execute("""
            select o.session_id, o.observation_count, o.event_count, o.event_rate,
                   o.event_types, o.measurable, s.actual_start
            from cell_observations o join sessions s on s.id = o.session_id
            where o.cell_key = %s order by s.actual_start
        """, (cell_key,))
        cell["observations"] = cur.fetchall()
    return cell


def _event_type_summary(observations: list[dict]) -> tuple[list[str], list[str]]:
    """이벤트 유형을 판정용과 참고용으로 나눈다.

    파이프라인은 참고 지표를 'ref:' 접두사로 기록한다. 판정 근거가 아닌 것을
    근거처럼 쓰면 안 되므로 리포트에서도 구분해 넘긴다.
    """
    primary, refs = set(), set()
    for o in observations:
        for t in (o.get("event_types") or {}):
            (refs if str(t).startswith("ref:") else primary).add(str(t).removeprefix("ref:"))
    return sorted(primary), sorted(refs - primary)


def pct(rate) -> str:
    """비율 → 백분율 문자열. 반올림은 half-up 이다.

    파이썬 기본 포매팅은 half-even 이라 52/64 = 81.25% 를 "81.2" 로 내리는데,
    기획서·README·thresholds.md 는 전부 81.3% 로 적혀 있고 화면(JS toFixed)도
    81.3 을 낸다. 문서·화면·API 가 서로 다른 숫자를 보이면 안 되므로 맞춘다.
    """
    if not isinstance(rate, (int, float)):
        return "-"
    return f"{Decimal(rate * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}"


LABEL = {
    "low_speed": "저속 정체(초당 최저 속도 2.0m/s 미만)",
    "state_deviation": "주행상태 코드 이탈",
    "obstacle_density": "경로 장애물 밀집",
    "emergency": "비상정지",
    "autonomy_disengage": "자율주행 해제",
}


def _brief(f: dict) -> str:
    """모델에 넘길 사실 요약. 여기 없는 값은 모델도 모른다."""
    lines = [
        f"구간: {f.get('road_name') or '도로명 미상'} (격자 {f['cell_key']})",
        f"도로: {f.get('lanes') or '?'}차로, 제한속도 {f.get('max_speed') or '?'}km/h",
        f"분류: {f.get('classification') or '판정 없음'}"
        f" (관측 세션 {f.get('session_count') or 0}개)",
    ]
    for o in f["observations"]:
        if not o["measurable"]:
            lines.append(f"- {o['session_id']}: 측정 불가 (해당 세션에 필요한 데이터셋 없음)")
            continue
        lines.append(
            f"- {o['session_id']}: 이벤트 {o['event_count']}초 / 관측 "
            f"{o['observation_count']}초 = {pct(o['event_rate'] or 0)}%")
    primary, refs = _event_type_summary(f["observations"])
    if primary:
        lines.append("판정 이벤트: " + ", ".join(LABEL.get(t, t) for t in primary))
    if refs:
        lines.append("참고 지표(판정 근거 아님): "
                     + ", ".join(LABEL.get(t, t) for t in refs))
    return "\n".join(lines)


def _template(f: dict) -> str:
    """폴백. 수치를 문장에 채워 넣되 원인은 단정하지 않는다."""
    measured = [o for o in f["observations"] if o["measurable"]]
    road = f.get("road_name") or f"격자 {f['cell_key']}"
    if len(measured) >= 2:
        lo, hi = measured[0], measured[-1]
        rates = ", ".join(pct(o["event_rate"] or 0) + "%" for o in measured)
        head = (
            f"{road} 구간은 서로 다른 {len(measured)}개 주행 세션에서 이상 이벤트가 "
            f"반복 검출되었습니다. {lo['session_id']}부터 {hi['session_id']}까지 "
            f"세션별 이벤트율은 {rates}입니다.")
    elif measured:
        o = measured[0]
        head = (f"{road} 구간은 {o['session_id']} 주행에서 "
                f"{pct(o['event_rate'] or 0)}%의 이상 이벤트율을 보였습니다.")
    else:
        head = f"{road} 구간은 아직 측정 가능한 관측이 없습니다."

    primary, refs = _event_type_summary(f["observations"])
    mid = ""
    if primary:
        mid = ("주로 " + ", ".join(LABEL.get(t, t) for t in primary)
               + "이 반복 관측되었습니다. ")
    if refs:
        mid += ("참고로 " + ", ".join(LABEL.get(t, t) for t in refs)
                + " 신호도 함께 나타났으나 판정 근거로는 사용하지 않았습니다. ")

    unmeasured = [o["session_id"] for o in f["observations"] if not o["measurable"]]
    tail = ""
    if unmeasured:
        tail = (f"{', '.join(unmeasured)} 세션은 필요한 데이터셋이 없어 측정 "
                f"불가이며, 이벤트가 없었다는 뜻이 아닙니다. ")

    return (
        f"{head} {mid}{tail}"
        f"반복성이 확인된 구간이므로 시야 확보, 노면 상태, 차선 시인성 등 "
        f"주행 환경 관련 점검 항목을 우선 확인하시기를 권고드립니다. "
        f"현장 확인 결과에 따라 원인이 확정됩니다.\n"
        f"※ 본 리포트는 원인을 진단하지 않으며 점검 우선순위를 제안합니다."
    )


def _claude(brief: str) -> str | None:
    """실호출. 키가 없거나 어떤 이유로든 실패하면 None → 템플릿으로 넘어간다."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
            messages=[{"role": "user",
                       "content": f"아래 관측 사실로 점검 리포트 초안을 써주세요.\n\n{brief}"}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip() or None
    except Exception:
        # 심사 시연 중 네트워크·쿼터 문제로 화면이 깨지면 안 된다
        return None


@router.post("/cells/{cell_key}/report", summary="SCR-06 AI 점검 리포트 초안")
def report(cell_key: str):
    f = _facts(cell_key)
    brief = _brief(f)
    text = _claude(brief)
    return {
        "cell_key": cell_key,
        "road_name": f.get("road_name"),
        "text": text or _template(f),
        "generated_by": "claude" if text else "template",
        "model": MODEL if text else None,
        "facts": brief,
        "disclaimer": "본 리포트는 원인을 진단하지 않으며 점검 우선순위를 제안합니다.",
    }
