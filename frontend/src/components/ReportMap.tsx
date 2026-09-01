import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { VWORLD_KEY } from "./VulnerabilityMap";

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

interface Props {
  /** 시민이 찍은 위치. 아직 안 찍었으면 null */
  picked: { lat: number; lon: number } | null;
  onPick: (p: { lat: number; lon: number }) => void;
}

/** 제보할 위치를 찍는 지도.
 *
 * 관리자 지도(VulnerabilityMap)와 달리 격자도 분류색도 올리지 않는다.
 * 시민에게 «여기는 87.2% 구간입니다»를 보여주면 제보가 그 판정에 끌려간다.
 * 물어야 할 것은 «무엇을 보셨나»이지 «여기가 위험한가»가 아니다.
 *
 * 배경지도 키가 없어도 동작한다. 그때는 빈 바탕에 표식만 남는데, 위치를
 * 찍는 데는 지장이 없고 주소는 서버가 격자에 붙여 돌려준다.
 */
export function ReportMap({ picked, onPick }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;

    const m = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: "bg",
            type: "background",
            paint: { "background-color": token("--rw-bg") },
          },
        ],
      },
      center: [127.1048, 37.4035],
      zoom: 14,
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: VWORLD_KEY ? "지도 © VWorld" : "",
      }),
    );

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
    });

    m.on("click", (e) => {
      onPick({ lat: e.lngLat.lat, lon: e.lngLat.lng });
    });
    m.getCanvas().style.cursor = "crosshair";

    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
    // onPick 은 부모가 매 렌더 새로 만들 수 있어 의존성에 넣지 않는다.
    // 지도를 다시 만들면 찍어둔 위치가 사라진다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 표식은 지도 재생성 없이 옮긴다
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!picked) {
      marker.current?.remove();
      marker.current = null;
      return;
    }
    if (!marker.current) {
      marker.current = new maplibregl.Marker({ color: token("--rw-primary") });
    }
    marker.current.setLngLat([picked.lon, picked.lat]).addTo(m);
  }, [picked]);

  return (
    <div
      ref={container}
      className="rw-map rw-map--short"
      role="application"
      aria-label="제보할 위치를 고르는 지도. 지도를 눌러 위치를 지정합니다."
    />
  );
}
