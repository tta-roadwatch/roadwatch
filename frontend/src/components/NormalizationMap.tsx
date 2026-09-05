import { useEffect, useRef, useState } from "react";
// maplibre-gl 6 부터 기본 export 가 없다. 네임스페이스로 받아
// maplibregl.Map 처럼 쓰던 코드를 그대로 둔다.
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type {
  MapBounds,
  NormalizationPointCollection,
  RoadLinkCollection,
} from "../api/types";
import { VWORLD_KEY } from "./VulnerabilityMap";

/** SCR-03 데모 하이라이트 — 정규화 전·후를 지도로 보여준다.
 *
 * 숫자 15,585 가 바뀌는 것보다 판교 지도가 비상정지 마커로 뒤덮였다가 토글
 * 하나로 3개만 남는 장면이 같은 사실을 훨씬 강하게 전달한다.
 *
 * 마커를 클러스터로 묶지 않는 것이 중요하다. 클러스터는 점이 많을 때 읽기
 * 쉬우라고 쓰는 것인데, 여기서는 "뒤덮인다"는 감각 자체가 요점이다.
 */

function token(name: string): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

const EMPTY_FC = { type: "FeatureCollection", features: [] };

interface Props {
  points: NormalizationPointCollection | null;
  /** 도로망이 없으면 점들이 허공의 낙서처럼 보인다. 배경이 있어야 "주행
   * 경로가 통째로 칠해졌다"는 게 읽힌다. */
  roads: RoadLinkCollection | null;
  bounds: MapBounds | null;
  /** true 면 정규화 적용 결과(3건), false 면 미적용(15,124건) */
  normalized: boolean;
}

export function NormalizationMap({ points, roads, bounds, normalized }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!container.current || map.current) return;

    const c = {
      bg: token("--rw-bg"),
      road: token("--rw-border-strong"),
      // 두 상태의 색을 같게 둔다. 남은 3건은 '정상'이 아니라 실제 센서
      // 이상이라, 성공 색(초록)으로 칠하면 이 앱의 범례("낮음·관찰")와
      // 정반대로 읽힌다. 달라지는 건 색이 아니라 개수이고, 그게 요점이다.
      mark: token("--rw-intermittent-text"),
      halo: token("--rw-surface"),
    };

    const m = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          { id: "bg", type: "background", paint: { "background-color": c.bg } },
        ],
      },
      center: [127.1048, 37.4035],
      zoom: 13,
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    m.on("load", () => {
      if (VWORLD_KEY) {
        m.addSource("vworld", {
          type: "raster",
          tiles: [
            `https://api.vworld.kr/req/wmts/1.0.0/${VWORLD_KEY}/Base/{z}/{y}/{x}.png`,
          ],
          tileSize: 256,
        });
        m.addLayer({ id: "vworld", type: "raster", source: "vworld" });
      }

      // 도로망을 먼저 깔아 배경을 만든다
      m.addSource("roads", { type: "geojson", data: EMPTY_FC as never });
      m.addLayer({
        id: "roads",
        type: "line",
        source: "roads",
        paint: {
          "line-color": c.road,
          "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 16, 2],
          "line-opacity": VWORLD_KEY ? 0.3 : 0.7,
        },
      });

      m.addSource("pts", { type: "geojson", data: EMPTY_FC as never });
      m.addLayer({
        id: "pts",
        type: "circle",
        source: "pts",
        paint: {
          // danger 를 쓰지 않는 것은 이 서비스가 위험을 단정하지 않기 때문이다.
          "circle-color": c.mark,
          // 점이 많을수록 작게. 15,124개를 큰 점으로 찍으면 지도가 아니라
          // 색면이 되어 어디가 덮였는지 알 수 없다.
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2, 16, 5],
          "circle-opacity": 0.55,
          "circle-stroke-width": 0,
        },
      });
      setReady(true);
      m.resize();
    });

    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      setReady(false);
    };
    // 지도는 한 번만 만든다. 데이터·색 변경은 아래 훅이 반영한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer("roads")) return;
    (m.getSource("roads") as maplibregl.GeoJSONSource | undefined)?.setData(
      (roads ?? EMPTY_FC) as never,
    );
  }, [roads, ready]);

  // 뷰포트는 격자 범위가 아니라 점 자체에 맞춘다. BSM 세션의 주행 경로는
  // 격자 분석 영역과 범위가 달라서, 격자에 맞추면 경로가 구석에 몰린다.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const pts = points?.features ?? [];
    if (pts.length) {
      let w = 180, s2 = 90, e = -180, n = -90;
      for (const f of pts) {
        const [lon, lat] = f.geometry.coordinates;
        if (lon < w) w = lon;
        if (lon > e) e = lon;
        if (lat < s2) s2 = lat;
        if (lat > n) n = lat;
      }
      // 점이 몇 개뿐이면 너무 확대돼 맥락이 사라지므로 최소 범위를 준다
      const padLon = Math.max((e - w) * 0.15, 0.004);
      const padLat = Math.max((n - s2) * 0.15, 0.003);
      m.fitBounds(
        [w - padLon, s2 - padLat, e + padLon, n + padLat] as [
          number, number, number, number,
        ],
        { padding: 24, duration: 400, maxZoom: 15 },
      );
    } else if (bounds?.bbox) {
      m.fitBounds(bounds.bbox as [number, number, number, number], {
        padding: 32,
        duration: 0,
      });
    }
  }, [points, bounds, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer("pts")) return;
    (m.getSource("pts") as maplibregl.GeoJSONSource | undefined)?.setData(
      (points ?? EMPTY_FC) as never,
    );
    // 3개로 줄면 눈에 띄어야 하므로 크기·테두리로 가른다. 색은 같게 둔다.
    m.setPaintProperty("pts", "circle-opacity", normalized ? 0.95 : 0.65);
    m.setPaintProperty("pts", "circle-stroke-width", normalized ? 2 : 0);
    m.setPaintProperty("pts", "circle-stroke-color", token("--rw-surface"));
    m.setPaintProperty("pts", "circle-radius", [
      "interpolate",
      ["linear"],
      ["zoom"],
      11,
      normalized ? 7 : 3.5,
      16,
      normalized ? 13 : 7,
    ] as never);
  }, [points, normalized, ready]);

  return <div ref={container} className="rw-map rw-map--short" />;
}
