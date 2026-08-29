"""데이터셋 인터페이스 — TTAK.KO-10.1331-Part3 6.2 + TTAK.KO-10.1398.

Part3 6.2 는 데이터를 데이터세트 단위로 조회·관리하는 리소스를 규정하고,
1398 은 그 데이터세트의 메타데이터 항목을 DCAT 기반으로 정의한다
("동일한 데이터 모델에 해당하는 데이터 인스턴스의 집합").

본 서비스는 8개 주행 세션을 각각 데이터세트로 등록한다. 중요한 건 5.4절에서
실측한 문제들을 메타데이터로 드러낸다는 점이다.

  - 파일 라벨의 날짜와 실제 수집시각이 최대 2년 어긋난다(4개 세션).
    temporal 에는 ss_num 에서 복원한 실제 시각을 싣고, 라벨은 별도 항목으로
    남겨 불일치를 감춘 게 아니라 기록했음을 보인다.
  - 세션마다 보유 데이터셋이 달라 산출 가능한 지표가 다르다.
    availableMetrics 가 비면 '측정 불가' 이지 '이벤트 0%' 가 아니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from .. import errors, ngsild
from ..deps import cursor

router = APIRouter(prefix="/ngsi-ld/v1", tags=["Part3 6.2 데이터셋 인터페이스"])

PUBLISHER = "국토교통부 공간정보 오픈플랫폼 공간데이터마켓"
SOURCE_URL = "https://geomarket.kr"
LICENSE = "공공누리 제1유형 (출처표시)"

_SQL = """
select s.id, s.actual_start, s.actual_end, s.has_ss_num,
       s.label_date, s.label_mismatch, s.available_metrics,
       s.codebook, s.ingested_at,
       coalesce(sum(f.record_count), 0)          as record_count,
       count(f.id)                                as file_count,
       array_agg(distinct f.dataset_kind)         as dataset_kinds,
       array_agg(f.source_file order by f.source_file) as source_files
from sessions s
left join session_files f on f.session_id = s.id
group by s.id
"""

#: 원본 데이터셋 종류 → 사람이 읽는 이름
KIND_LABEL = {
    "BSM": "기본안전메시지(BSM)",
    "GPS": "차량 GPS·INS",
    "STATUS": "차량 상태정보",
    "OBJECT": "차량 객체인식",
    "CONTROL": "차량 제어정보",
}

METRIC_LABEL = {
    "low_speed": "저속 정체",
    "state_deviation": "주행상태 코드 이탈",
    "obstacle_density": "경로 장애물 밀집",
    "emergency": "비상정지",
    "autonomy_disengage": "자율주행 해제",
}


def _dcat(row: dict) -> dict:
    """세션 하나 → 1398 데이터세트 메타데이터 (DCAT 기반)."""
    sid = row["id"]
    kinds = [k for k in (row.get("dataset_kinds") or []) if k]
    metrics = row.get("available_metrics") or []
    return {
        "id": ngsild.urn("Dataset", sid),
        "type": "Dataset",
        # ── DCAT 핵심 항목 ──
        "identifier": sid,
        "title": f"판교 제로시티 자율주행 주행 세션 {sid}",
        "description": (
            f"{sid} 수집 주행 세션. 원본 {row['file_count']}개 파일 "
            f"{row['record_count']:,}건. 보유 데이터셋: "
            + ", ".join(KIND_LABEL.get(k, k) for k in sorted(kinds))
        ),
        "publisher": PUBLISHER,
        "landingPage": SOURCE_URL,
        "license": LICENSE,
        "issued": _iso(row.get("ingested_at")),
        # 실제 수집시각 — 파일 라벨이 아니라 ss_num 에서 복원한 값이다
        "temporal": {"startDate": _iso(row.get("actual_start")),
                     "endDate": _iso(row.get("actual_end"))},
        "spatial": {"placeName": "경기도 성남시 분당구 판교 제로시티"},
        "keyword": [METRIC_LABEL.get(m, m) for m in metrics],
        "distribution": [
            {"title": f, "mediaType": "application/json", "accessService": SOURCE_URL}
            for f in (row.get("source_files") or []) if f
        ],
        # ── 품질 메타데이터 (5.4절 실측 결과) ──
        "dataQuality": {
            "timeSourceRestored": bool(row.get("has_ss_num")),
            "labelDate": _iso(row.get("label_date")),
            "labelMismatch": bool(row.get("label_mismatch")),
            "labelMismatchNote": (
                "파일 라벨의 연도가 실제 수집시각과 다릅니다. temporal 은 "
                "ss_num(epoch)에서 복원한 실제 시각입니다."
                if row.get("label_mismatch") else None
            ),
            "codebook": row.get("codebook"),
            "codebookNote": (
                "이 세션은 플래그 코드 체계가 다른 세션과 반대여서 정규화를 "
                "적용했습니다."
                if row.get("codebook") == "inverted" else None
            ),
            "availableMetrics": metrics,
            "measurable": bool(metrics),
            "measurableNote": (
                None if metrics else
                "산출 가능한 지표가 없습니다. '이벤트 0%' 가 아니라 '측정 불가' 입니다."
            ),
        },
    }


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


@router.get("/datasets", summary="데이터세트 목록 조회")
def list_datasets(measurable: bool | None = Query(None, description="측정 가능 여부로 필터")):
    with cursor() as cur:
        cur.execute(_SQL + " order by s.id")
        rows = cur.fetchall()
    out = [_dcat(r) for r in rows]
    if measurable is not None:
        out = [d for d in out if d["dataQuality"]["measurable"] is measurable]
    return out


@router.get("/datasets/{dataset_id:path}", summary="데이터세트 단건 조회")
def get_dataset(dataset_id: str):
    # URN 으로도 세션 ID 로도 조회할 수 있게 한다
    sid = dataset_id.rsplit(":", 1)[-1] if dataset_id.startswith("urn:") else dataset_id
    with cursor() as cur:
        cur.execute(_SQL + " having s.id = %s", (sid,))
        row = cur.fetchone()
    if row is None:
        raise errors.not_found(f"해당 데이터세트가 없습니다: {dataset_id}")
    return _dcat(row)
