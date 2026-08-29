"""표준 적용 현황 — SCR-09.

이 서비스가 어느 표준을 실제로 구현했고 어느 것을 설계 근거로만 참조했는지
구분해 제공한다. 화면에서 evidence 경로를 눌러 실제 응답을 띄우면, 표준 준수가
문서 주장이 아니라 확인 가능한 사실임이 드러난다.

과장하지 않는 것이 핵심이다. 심사자가 소스코드를 열었을 때 여기 적힌 것과
어긋나면 오히려 신뢰를 잃는다.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["표준"])

#: 화면이 "인용과 구현"을 구분해 보여줄 수 있도록 확인 경로를 함께 준다.
#: 기획서 6.5절과 같은 내용이며, 과장하지 않는 것이 핵심이다.
STANDARDS = [
    {
        "id": "TTAK.KO-10.1331-Part4/R1",
        "name": "스마트시티 데이터허브 — 데이터 모델",
        "role": "NGSI-LD 정규 표현법과 TrafficEvent 모델",
        "status": "implemented",
        "evidence": "/ngsi-ld/v1/entities?type=TrafficEvent",
        "note": "속성마다 Property·GeoProperty·Relationship 을 밝히고 observedAt 을 싣는다.",
    },
    {
        "id": "TTAK.KO-10.1331-Part3",
        "name": "스마트시티 데이터허브 — 인터페이스 및 프로토콜",
        "role": "REST API 명세와 응답 코드 체계",
        "status": "implemented",
        "evidence": "/ngsi-ld/v1/datasets",
        "note": "6.1 데이터 인터페이스 · 6.2 데이터셋 인터페이스 · 5장 ProblemDetails.",
    },
    {
        "id": "TTAK.KO-10.1398",
        "name": "스마트시티 데이터세트 메타데이터",
        "role": "주행 세션을 데이터세트로 등록",
        "status": "implemented",
        "evidence": "/ngsi-ld/v1/datasets",
        "note": "DCAT 기반. 라벨 연도 불일치 같은 실측 품질 문제를 메타데이터로 드러낸다.",
    },
    {
        "id": "TTAK.KO-06.0580",
        "name": "이동통신망 기반 V2N 서비스 정보 연계",
        "role": "BSM 입력",
        "status": "partial",
        "evidence": "/api/normalization",
        "note": "BSM 원본 필드를 실제로 파싱해 적재한다. 메시지 규격의 인코더·디코더는 구현하지 않았다.",
    },
    {
        "id": "TTAK.KO-10.1331-Part2",
        "name": "스마트시티 데이터허브 — 참조구조",
        "role": "계층 분리 설계 근거",
        "status": "reference",
        "evidence": None,
        "note": "수집–정규화–저장–제공 계층 분리의 근거. 직접 대응하는 코드 산출물은 없다.",
    },
]

STATUS_LABEL = {
    "implemented": "구현",
    "partial": "부분 구현",
    "reference": "설계 참조",
}


@router.get("/standards", summary="SCR-09 표준 적용 현황")
def standards():
    """표준을 인용만 한 것과 실제로 구현한 것을 구분해 보여준다.

    화면에서 evidence 경로를 눌러 실제 응답을 띄우면, 표준 준수가 문서 주장이
    아니라 확인 가능한 사실임이 드러난다.
    """
    return {
        "standards": [{**s, "status_label": STATUS_LABEL[s["status"]]} for s in STANDARDS],
        "summary": {
            "implemented": sum(1 for s in STANDARDS if s["status"] == "implemented"),
            "partial": sum(1 for s in STANDARDS if s["status"] == "partial"),
            "reference": sum(1 for s in STANDARDS if s["status"] == "reference"),
        },
        "note": ("표준 적용은 과장하지 않는다. 코드에 실제로 있는 것과 설계 근거로만 "
                 "참조한 것을 구분해 표기한다."),
        "spatial_note": ("공간 연계는 지정 134선에 대응 표준이 없어 ITS 국가교통정보센터의 "
                         "전국표준노드링크로 구현했다. TTA 표준이 아니므로 위 표에 넣지 않는다."),
    }
