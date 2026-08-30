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
from pipeline.codebook import VERIFIED
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


# ── 정규화 대비 (SCR-03 데모 하이라이트) ──────────────────────────────
#: 정규화 없이 판정했을 때의 오판 건수. 실측값이며 codebook.VERIFIED 와 같은 출처다.
MISJUDGED_TOTAL = VERIFIED["emergency_without_codebook"]

@router.get("/normalization", summary="정규화 전·후 비상정지 지점 (GeoJSON)")
def normalization_points(
    normalized: bool = Query(
        False, description="false=정규화 안 함(지도가 뒤덮임), true=정규화 적용"),
    slim: bool = Query(
        True, description="점별 속성을 빼고 좌표만 — 15,124점을 그릴 때 응답이 3.9MB→1.3MB"),
):
    """토글 하나로 판정이 뒤집히는 장면을 지도로 보여준다.

    같은 BSM 레코드를 두 번 판정한 결과다. 정규화하지 않으면 표준 체계(1=발생)를
    전 세션에 그대로 적용하게 되는데, 2022-10-03 세션은 1이 '정상'이라 그 세션
    전체가 비상정지로 뒤집힌다.
    """
    col = "normalized_emergency" if normalized else "raw_emergency"
    with cursor() as cur:
        cur.execute(
            f"""select session_id, lat, lon, observed_at, codebook, flags
                from normalization_points where {col}
                order by session_id, observed_at""")
        rows = cur.fetchall()
        cur.execute("""
            select count(*) filter (where raw_emergency)        as raw,
                   count(*) filter (where normalized_emergency) as norm
            from normalization_points""")
        c = cur.fetchone()
    # driving_records 에서 세지 않는다. 시드 DB 는 세션당 1,000건 샘플만 담고
    # 있어서 0 이 나오고, 그러면 시연 화면에 "0건은 좌표가 없어서"라는 틀린
    # 문장이 뜬다. 두 수의 차이로 구하면 DB 상태와 무관하게 항상 맞다.
    no_coord = MISJUDGED_TOTAL - c["raw"]

    return {
        "type": "FeatureCollection",
        # 15,124점을 그릴 때는 점마다 속성을 실으면 응답이 3.9MB 가 된다.
        # 지도는 점을 찍기만 하고 속성을 읽지 않으므로 기본은 좌표만 보낸다.
        # 정규화 후 3건은 어떤 플래그였는지가 중요하므로 slim 이어도 싣는다.
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
             "properties": ({} if slim and not normalized else {
                 "session_id": r["session_id"],
                 "observed_at": _iso(r["observed_at"]),
                 "codebook": r["codebook"],
                 "flags": r["flags"]})}
            for r in rows
        ],
        "metadata": {
            "normalized": normalized,
            "mapped": len(rows),
            "mapped_raw": c["raw"],
            "mapped_normalized": c["norm"],
            # 실측 오판 건수와 지도에 찍히는 수가 다르다. 숨기지 않는다.
            "misjudged_total": MISJUDGED_TOTAL,
            "not_mappable": no_coord,
            "coverage_note": (
                f"정규화 없이 판정하면 {MISJUDGED_TOTAL:,}건이 비상정지로 잡힙니다. 그중 "
                f"{no_coord}건은 좌표가 유효하지 않아 지도에 표시할 수 없어 "
                f"{c['raw']}개만 찍힙니다. 정규화를 적용하면 {c['norm']}건만 남습니다."),
        },
    }


@router.get("/trajectories", summary="주행 궤적 (GeoJSON)")
def trajectories(session_id: str | None = Query(None, description="특정 세션만")):
    """차량이 실제로 지나간 경로.

    격자 사각형은 분석 단위지 주행이 아니다. 실제 궤적을 함께 그리면 셀이
    허공에 뜬 게 아니라 주행 경로 위에 얹혀 있음이 눈으로 확인된다.
    """
    sql = ("select session_id, lon, lat, obs_second from trajectories "
           + ("where session_id = %s " if session_id else "")
           + "order by session_id, obs_second")
    with cursor() as cur:
        cur.execute(sql, (session_id,) if session_id else ())
        rows = cur.fetchall()

    lines: dict[str, list] = {}
    for r in rows:
        lines.setdefault(r["session_id"], []).append([r["lon"], r["lat"]])
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "LineString", "coordinates": pts},
             "properties": {"session_id": sid, "seconds": len(pts)}}
            for sid, pts in sorted(lines.items()) if len(pts) > 1
        ],
        "metadata": {"sessions": len(lines), "points": len(rows),
                     "note": "초당 대표 위치. GPS 원본은 100Hz 이나 지도에는 초당 1점이면 충분하다."},
    }


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v
