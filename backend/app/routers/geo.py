"""지도 레이어 — SCR-05.

MapLibre 는 GeoJSON 을 그대로 소비하므로 지도용 데이터는 GeoJSON 으로 낸다.

이 라우터가 있는 이유는 두 가지다.

  격자 폴리곤 — 화면이 40m 셀을 그리려면 셀의 경계가 필요하다. 중심점만 주면
  프론트가 DLAT/DLON/LAT0/LON0 을 알아야 하는데, 그건 캘리브레이션으로 정한
  분석 규약이지 화면이 알 일이 아니다. 규약이 바뀌면 화면도 같이 틀어진다.
  경계를 서버에서 계산해 내려보낸다.

  도로망 — data/nodelink/*.geojson 은 저장소에는 있지만 프론트에서 접근할 수
  없다(Vite 는 frontend/ 밖을 서빙하지 않는다). 파일을 frontend/public 으로
  복사하면 같은 데이터가 두 벌이 되고 갱신 시 어긋난다. API 가 서빙한다.
"""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import APIRouter, Query

from ..deps import cursor
from pipeline import sources as S
from pipeline.grid import DLAT, DLON, LAT0, LON0

router = APIRouter(prefix="/api/geo", tags=["지도"])


def _cell_bounds(cell_key: str) -> list[list[float]] | None:
    """격자 키 → 폴리곤 링 ([경도, 위도] 순, 닫힌 링)."""
    try:
        iy, ix = (int(v) for v in cell_key.split(":"))
    except ValueError:
        return None
    s, w = LAT0 + iy * DLAT, LON0 + ix * DLON
    n, e = s + DLAT, w + DLON
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


@router.get("/cells", summary="격자 셀 폴리곤 (GeoJSON)")
def cells_geojson(candidates_only: bool = False):
    """지도에 칠할 40m 격자.

    분류가 없는 셀(관측 1세션)도 내려보낸다 — 화면에서 회색으로 그려야
    '판정할 만큼 관측되지 않았다'와 '문제없다'가 구분된다.
    """
    sql = """
        select g.cell_key, g.center_lat, g.center_lon, g.road_name, g.address,
               g.lanes, g.max_speed,
               r.classification, r.session_count,
               r.min_event_rate, r.max_event_rate, r.is_candidate,
               (select count(*) from cell_observations o
                  where o.cell_key = g.cell_key) as observed_sessions,
               (select status from inspections i
                  where i.cell_key = g.cell_key
                  order by i.created_at desc limit 1) as inspection_status
        from grid_cells g left join road_issues r using (cell_key)
    """
    if candidates_only:
        sql += " where r.is_candidate"
    with cursor() as cur:
        cur.execute(sql + " order by g.cell_key")
        rows = cur.fetchall()

    feats = []
    for r in rows:
        ring = _cell_bounds(r["cell_key"])
        if ring is None:
            continue
        feats.append({
            "type": "Feature",
            "id": r["cell_key"],
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "cell_key": r["cell_key"],
                "center": [r["center_lon"], r["center_lat"]],
                "road_name": r["road_name"],
                "address": r["address"],
                "lanes": r["lanes"],
                "max_speed": r["max_speed"],
                "classification": r["classification"],
                "session_count": r["session_count"],
                "observed_sessions": r["observed_sessions"],
                "min_event_rate": _r(r["min_event_rate"]),
                "max_event_rate": _r(r["max_event_rate"]),
                "is_candidate": bool(r["is_candidate"]),
                "inspection_status": r["inspection_status"],
            },
        })
    return {
        "type": "FeatureCollection",
        "features": feats,
        # 화면이 격자 규약을 되계산하지 않도록 참고값만 함께 준다
        "metadata": {"cell_size_m": 40, "d_lat": DLAT, "d_lon": DLON,
                     "count": len(feats)},
    }


@lru_cache(maxsize=1)
def _links() -> dict:
    """노드링크는 475KB 짜리 정적 파일이라 한 번만 읽어 캐시한다."""
    p = S.data_dir() / "nodelink" / "pangyo_links.geojson"
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/roadlinks", summary="도로망 링크 (GeoJSON)")
def roadlinks(named_only: bool = Query(False, description="도로명 있는 링크만")):
    """ITS 전국표준노드링크에서 추출한 판교 일대 1,087개 링크.

    격자 셀의 도로명·차로수·제한속도가 이 링크에서 온 값이므로, 지도에서
    셀이 어느 도로 위에 얹혀 있는지 눈으로 확인할 수 있어야 한다.
    """
    gj = _links()
    feats = gj["features"]
    if named_only:
        feats = [f for f in feats
                 if (f["properties"].get("ROAD_NAME") or "").strip() not in ("", "-")]
    return {
        "type": "FeatureCollection",
        "features": feats,
        "metadata": {
            "source": "ITS 국가교통정보센터 전국표준노드링크 (2026-08-12판)",
            "crs_note": "원본 EPSG:5186 → WGS84 변환 완료",
            "count": len(feats),
        },
    }


@router.get("/bounds", summary="분석 영역 경계")
def bounds():
    """지도 초기 뷰포트. 화면이 판교 좌표를 하드코딩하지 않게 한다."""
    with cursor() as cur:
        cur.execute("""
            select min(center_lat) as s, max(center_lat) as n,
                   min(center_lon) as w, max(center_lon) as e,
                   avg(center_lat) as clat, avg(center_lon) as clon
            from grid_cells
        """)
        b = cur.fetchone()
    if b["s"] is None:
        return {"bbox": None, "center": None}
    pad_lat, pad_lon = DLAT * 2, DLON * 2
    return {
        "bbox": [b["w"] - pad_lon, b["s"] - pad_lat,
                 b["e"] + pad_lon, b["n"] + pad_lat],
        "center": [b["clon"], b["clat"]],
        "place_name": "경기도 성남시 분당구 판교 제로시티",
    }


def _r(v):
    return round(v, 4) if isinstance(v, (int, float)) else v
