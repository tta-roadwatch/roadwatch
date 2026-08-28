"""⑧ 도로명 매핑 — ITS 전국표준노드링크.

data/nodelink/pangyo_links.geojson (판교 일대 742링크, 2026-08-12판에서 추출,
EPSG:5186 → WGS84 변환 완료본)을 로드해 각 격자 셀 중심의 최근접 링크를 찾는다.
TrafficEvent 모델의 name·address 속성(TTAK.KO-10.1331-Part4/R1 7.2.2)을 채운다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import psycopg

from . import sources as S

#: 최근접 링크가 이보다 멀면 도로망 밖으로 본다 (기획서 실측: 1건이 ≈53m)
OFF_ROAD_M = 50.0

M_PER_DEG_LAT = 111_320.0


def _links() -> list[dict]:
    p = S.data_dir() / "nodelink" / "pangyo_links.geojson"
    gj = json.loads(Path(p).read_text(encoding="utf-8"))
    return gj["features"]


def _seg_dist_m(plat: float, plon: float,
                a: tuple[float, float], b: tuple[float, float],
                m_per_deg_lon: float) -> float:
    """점–선분 거리 (equirectangular 미터 근사 — 판교 반경 2km 내 오차 무시 가능)."""
    ax, ay = a[0] * m_per_deg_lon, a[1] * M_PER_DEG_LAT
    bx, by = b[0] * m_per_deg_lon, b[1] * M_PER_DEG_LAT
    px, py = plon * m_per_deg_lon, plat * M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def nearest_link(lat: float, lon: float, links: list[dict]) -> tuple[dict, float]:
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(lat))
    best, best_d = None, float("inf")
    for f in links:
        coords = f["geometry"]["coordinates"]        # [[lon, lat], …]
        for i in range(len(coords) - 1):
            d = _seg_dist_m(lat, lon, coords[i], coords[i + 1], m_per_deg_lon)
            if d < best_d:
                best, best_d = f, d
    return best, best_d


def run(conn: psycopg.Connection) -> dict:
    links = _links()
    with conn.cursor() as cur:
        cur.execute("select cell_key, center_lat, center_lon from grid_cells")
        cells = cur.fetchall()

        off_road = []
        for cell_key, lat, lon in cells:
            f, dist = nearest_link(lat, lon, links)
            p = f["properties"]
            name = (p.get("ROAD_NAME") or "").strip()
            if not name or name == "-":
                name = None
            cur.execute(
                """update grid_cells set
                     road_name=%s, address=%s, link_id=%s,
                     lanes=%s, max_speed=%s, link_dist_m=%s
                   where cell_key=%s""",
                (name,
                 f"경기도 성남시 분당구 {name}" if name else "경기도 성남시 분당구",
                 p.get("LINK_ID"),
                 p.get("LANES"),
                 int(p["MAX_SPD"]) if str(p.get("MAX_SPD", "")).strip().isdigit() else None,
                 round(dist, 1),
                 cell_key),
            )
            if dist > OFF_ROAD_M:
                off_road.append((cell_key, round(dist, 1)))
    conn.commit()
    return {"cells": len(cells), "links": len(links), "off_road": off_road}
