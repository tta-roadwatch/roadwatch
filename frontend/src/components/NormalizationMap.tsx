import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type { MapBounds, NormalizationPointCollection } from "../api/types";
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
  bounds: MapBounds | null;
  /** true 면 정규화 적용 결과(3건), false 면 미적용(15,124건) */
  normalized: boolean;
}

export function NormalizationMap({ points, bounds, normalized }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!container.current || map.current) return;

    const c = {
      bg: token("--rw-bg"),
      wrong: token("--rw-intermittent-text"),
      right: token("--rw-low-text"),
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

      m.addSource("pts", { type: "geojson", data: EMPTY_FC as never });
      m.addLayer({
        id: "pts",
        type: "circle",
        source: "pts",
        paint: {
          // 정규화 전은 오판이므로 주의 색, 적용 후 남은 것은 실제 이상이라
          // 다른 색으로 구분한다. 둘 다 danger 를 쓰지 않는 것은 이 서비스가
          // 위험을 단정하지 않기 때문이다.
          "circle-color": normalized ? c.right : c.wrong,
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
    if (!m || !ready || !bounds?.bbox) return;
    m.fitBounds(bounds.bbox as [number, number, number, number], {
      padding: 32,
      duration: 0,
    });
  }, [bounds, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer("pts")) return;
    (m.getSource("pts") as maplibregl.GeoJSONSource | undefined)?.setData(
      (points ?? EMPTY_FC) as never,
    );
    // 마커가 3개로 줄면 눈에 띄어야 하므로 크기·색을 함께 바꾼다
    m.setPaintProperty(
      "pts",
      "circle-color",
      normalized ? token("--rw-low-text") : token("--rw-intermittent-text"),
    );
    m.setPaintProperty("pts", "circle-opacity", normalized ? 0.95 : 0.55);
    m.setPaintProperty("pts", "circle-stroke-width", normalized ? 2 : 0);
    m.setPaintProperty("pts", "circle-stroke-color", token("--rw-surface"));
    m.setPaintProperty("pts", "circle-radius", [
      "interpolate",
      ["linear"],
      ["zoom"],
      11,
      normalized ? 6 : 2,
      16,
      normalized ? 11 : 5,
    ] as never);
  }, [points, normalized, ready]);

  return <div ref={container} className="rw-map rw-map--short" />;
}
