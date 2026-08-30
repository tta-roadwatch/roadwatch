"""정규화 실측 사실 — SCR-03 화면이 쓰는 값.

수치를 여기서 다시 계산하지 않는다. pipeline.codebook.VERIFIED 는 파이프라인
실행 중 실측해 고정한 값이고, tests/test_acceptance.py 가 그 값을 지킨다.
화면이 별도 계산을 하면 두 숫자가 갈라질 수 있으므로 같은 출처를 쓴다.
"""
from __future__ import annotations

from pipeline.codebook import (
    EMERGENCY_FLAGS,
    INVERTED,
    SESSION_CODEBOOK,
    STANDARD,
    VERIFIED,
)

#: 코드북별로 '이상'으로 보는 값. 세션마다 이게 반대라는 게 문제의 핵심이다.
_CODEBOOKS = {
    "standard": {"name": "standard", "abnormal": STANDARD.abnormal},
    "inverted": {"name": "inverted", "abnormal": INVERTED.abnormal},
}

#: BSM 좌표 유효성 실측값. driving_records 를 세지 않는다 — 시드 DB 는 세션당
#: 1,000건 샘플이라 100.0% 가 나오고, 시연 화면에 틀린 숫자가 뜬다. 실제로 겪었다.
#: 이 값은 인수 기준(run.py)이 지키는 수치와 같은 출처다.
COORD_VALIDITY = {
    "valid": 39_546,
    "total": 40_010,
    "rate": round(39_546 / 40_010, 4),
    "note": "BSM 전체 40,010건 중 39,546건이 유효 좌표입니다.",
}

NORMALIZATION = {
    "source": VERIFIED["source"],
    "without_codebook": VERIFIED["emergency_without_codebook"],
    "with_codebook": VERIFIED["emergency_with_codebook"],
    "corrected": VERIFIED["corrected_misjudgements"],
    "headline": (
        f"표준 정규화를 적용하지 않으면 "
        f"{VERIFIED['corrected_misjudgements']:,}건이 "
        f'"비상정지 발생"으로 잘못 판정됩니다'
    ),
    "explanation": (
        "같은 TTA 표준 필드인데 세션마다 코드 체계가 반대입니다. "
        "2022-10-03 세션은 mnl_emg_flg=0 이 '비상정지 발생'이고, "
        "나머지 두 세션은 1이 발생입니다."
    ),
    "emergency_flags": list(EMERGENCY_FLAGS),
    "codebooks": {
        k: {"name": v["name"],
            "abnormal": {f: sorted(vals) for f, vals in v["abnormal"].items()}}
        for k, v in _CODEBOOKS.items()
    },
    "session_codebook": {sid: cb.name for sid, cb in SESSION_CODEBOOK.items()},
    # 화면의 토글이 보여줄 원본 → 정규화 대비 예시
    "example": {
        "session_id": "2022-10-03",
        "raw": {"mnl_emg_flg": 1, "auto_emg_flg": 1, "snsr_trb_flg": 1},
        "raw_note": "이 세션에서는 1 = 정상",
        "normalized": {
            "manualEmergencyStop": {"type": "Property", "value": False,
                                    "observedAt": "2022-10-03T10:46:03+09:00"},
            "automaticEmergencyStop": {"type": "Property", "value": False,
                                       "observedAt": "2022-10-03T10:46:03+09:00"},
            "sensorTrouble": {"type": "Property", "value": False,
                              "observedAt": "2022-10-03T10:46:03+09:00"},
        },
    },
}
