"""분석 갈래 — BSM 갈래와 조인 갈래.

파이프라인은 두 갈래로 이벤트를 뽑는다.

    BSM 갈래   비상정지·자율주행 해제 기준 (BSM 단독 세션)
    조인 갈래  저속 정체 기준 (GPS+STATUS 조인 세션, min ve < 2.0m/s)

**이벤트 정의가 다르므로 두 갈래의 이벤트율을 나란히 늘어놓으면 안 된다.**
대표 구간 21:4 는 조인 갈래에서 80.4~87.2% 로 좁게 재현되는데, BSM 갈래
값(0%·100%)과 섞으면 "0.0%, 100.0%, 93.9%" 처럼 보여 재현성 주장이 무너진다.

화면·리포트·엔티티가 각자 이 판단을 재구현하면 한 곳만 고쳐지고 나머지가
어긋난다 — 실제로 화면만 막고 리포트에서 다시 섞였다. 그래서 여기 한 곳에 둔다.
"""
from __future__ import annotations

BSM = "bsm"
JOINED = "joined"

FAMILY_LABEL = {
    BSM: "BSM 갈래 (비상정지·자율주행 해제)",
    JOINED: "조인 갈래 (저속 정체)",
}

#: 짧은 표기 — 문장 안에 넣을 때
FAMILY_SHORT = {
    BSM: "BSM 갈래",
    JOINED: "조인 갈래",
}

_BSM_METRICS = {"emergency", "autonomy_disengage"}
_JOINED_METRICS = {"low_speed", "state_deviation", "obstacle_density"}

NOTICE = ("BSM 갈래와 조인 갈래는 이벤트 정의가 다르므로 이벤트율을 직접 "
          "비교하지 않습니다. 반복성 판정은 갈래를 구분하지 않고 수행하되, "
          "표시할 때는 갈래를 나눠 보여줍니다.")


def family_of(metrics: list[str] | None) -> str | None:
    """세션의 available_metrics → 갈래."""
    m = set(metrics or [])
    if m & _BSM_METRICS:
        return BSM
    if m & _JOINED_METRICS:
        return JOINED
    return None


def group(observations: list[dict], metrics_key: str = "available_metrics") -> dict:
    """관측을 갈래별로 묶는다. 측정 불가·미관측은 제외한다.

    반환 순서는 조인 갈래 우선이다 — 기획서가 주장하는 재현성이 그쪽이라
    화면·리포트에서 먼저 읽혀야 한다.
    """
    out: dict[str, list[dict]] = {}
    for o in observations:
        if o.get("observation_count") is None or not o.get("measurable"):
            continue
        fam = family_of(o.get(metrics_key))
        if fam is None:
            continue
        out.setdefault(fam, []).append(o)
    return {f: out[f] for f in (JOINED, BSM) if f in out}
