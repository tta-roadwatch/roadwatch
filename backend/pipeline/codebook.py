"""
세션별 코드북 — TTA 표준 기반 정규화의 핵심.

공간데이터마켓 판교제로시티 개방데이터는 같은 BSM 표준 필드인데도
세션마다 '정상'을 뜻하는 코드값이 반대다. 이를 정규화하지 않고 합치면
2022-10-03 세션 15,585건 전체가 "비상정지 발생"으로 오판된다.

아래 표는 원본 16개 파일(843,734건)을 직접 집계해 확인한 실측값이다.

    세션          mnl_emg_flg   auto_emg_flg  snsr_trb_flg   vhcl_sttus_flg
    2022-10-03    1: 15,585     1: 15,585     1: 15,585      0: 12,570 / 1: 3,015
    2023-02-23    0: 14,425     0: 14,425     0: 14,425      1: 14,425
    2024-01-02    0: 10,000     0: 10,000     0: 9,997 / 1:3  1: 10,000

즉 2022-10-03만 `1 = 정상`이고 나머지 두 세션은 `0 = 정상`이다.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Codebook:
    """한 세션의 플래그 코드 체계."""

    name: str
    #: 이상(abnormal)을 뜻하는 값. 여기 해당하면 True(이벤트 발생)로 정규화한다.
    abnormal: dict[str, set[str]] = field(default_factory=dict)
    note: str = ""

    def flag(self, field_name: str, raw) -> bool | None:
        """원본 코드값을 '이상 발생 여부' boolean으로 정규화한다."""
        if raw is None:
            return None
        rule = self.abnormal.get(field_name)
        if rule is None:
            return None
        return str(raw).strip() in rule


# 표준 체계 : 0 = 정상, 1 = 이상 / 단 vhcl_sttus_flg는 1 = 정상
STANDARD = Codebook(
    name="standard",
    abnormal={
        "mnl_emg_flg": {"1"},
        "auto_emg_flg": {"1"},
        "snsr_trb_flg": {"1"},
        "vhcl_sttus_flg": {"0"},
    },
    note="2023-02-23 · 2024-01-02 세션에서 확인된 체계",
)

# 반전 체계 : 1 = 정상, 0 = 이상 / vhcl_sttus_flg는 0 = 정상
INVERTED = Codebook(
    name="inverted",
    abnormal={
        "mnl_emg_flg": {"0"},
        "auto_emg_flg": {"0"},
        "snsr_trb_flg": {"0"},
        "vhcl_sttus_flg": {"1"},
    },
    note="2022-10-03 세션 전용. 정규화하지 않으면 15,585건이 전량 오판된다.",
)

#: 세션 ID → 코드북. 신규 세션은 detect() 로 판별한다.
SESSION_CODEBOOK: dict[str, Codebook] = {
    "2022-10-03": INVERTED,
    "2023-02-23": STANDARD,
    "2024-01-02": STANDARD,
}


def detect(records: list[dict]) -> Codebook:
    """세션 코드북을 데이터에서 추론한다.

    판별 근거: 비상정지·센서장애가 전 레코드에서 동시에 1이라면
    그것은 '항상 비상정지 중'이 아니라 1이 정상을 뜻하는 체계다.
    """
    if not records:
        return STANDARD
    keys = ("mnl_emg_flg", "auto_emg_flg", "snsr_trb_flg")
    for k in keys:
        vals = {str(r.get(k)).strip() for r in records if r.get(k) is not None}
        if vals == {"1"}:
            return INVERTED
    return STANDARD


def normalize_vehicle_id(raw) -> str | None:
    """차량 ID 체계 통일.

    세션마다 타입과 의미가 다르다 (실측):
        2022-10-03  str  "ZERO_001", "ZERO_002"   고유 2개
        2023-02-23  int  1 … 7358                 고유 7,358개 (사실상 메시지 일련번호)
        2024-01-02  int  3, 4                     고유 2개
    문자열로 통일하되, 정수형은 ZERO_%03d 형태로 맞춘다.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        # 고유값이 매우 많은 세션은 차량 식별자가 아니므로 원본을 보존한다
        return f"ZERO_{n:03d}" if n <= 99 else s
    return s


# ── 이벤트 분류 ────────────────────────────────────────────────
# 비상정지·센서장애와 차량상태는 별개 지표다. 둘을 섞어 세면
# 기획서의 "15,585건 오판" 수치가 재현되지 않는다.
EMERGENCY_FLAGS = ("mnl_emg_flg", "auto_emg_flg", "snsr_trb_flg")
STATE_FLAGS = ("vhcl_sttus_flg",)

# 원본 40,010건(BSM 3세션)으로 검증한 결과 :
#
#   비상정지·센서장애 3종
#     정규화 미적용  15,588건 이상 판정   (2022-10-03의 15,585건 전량 + 2024-01-02의 3건)
#     정규화 적용         3건 이상 판정   (2024-01-02 센서장애 3건만 남는다)
#     → 바로잡은 오판 15,585건. 기획서 수치와 일치.
#
#   2024-01-02에 남는 3건은 실제 센서장애이며, 기획서 17절 한계 2의
#   "센서장애 3건이 전부"라는 서술과 같은 값이다.
VERIFIED = {
    "source": "BSM 3세션 40,010건",
    "emergency_without_codebook": 15588,
    "emergency_with_codebook": 3,
    "corrected_misjudgements": 15585,
}


# ── autonm_flg : 자율주행 해제 판정 ─────────────────────────────────
# 값이 0/1이 아니라 1/2다. 전체 분포 분석(docs/thresholds.md §A) 결과
# 세 세션의 패턴이 동일하다 — 값 2가 소수(14~24%)이고 주행 중 비율이 높다.
# 초기 3건 표본에서 의심했던 세션별 반전은 전체 분포에서는 나타나지 않았다.
AUTONOMY_DISENGAGED_VALUE = "2"    # 수동 운행 (자율주행 해제)


def autonomy_disengaged(raw) -> bool | None:
    """autonm_flg → 해제 여부. 전 세션 공통 규칙 (코드북 불필요)."""
    if raw is None:
        return None
    return str(raw).strip() == AUTONOMY_DISENGAGED_VALUE
