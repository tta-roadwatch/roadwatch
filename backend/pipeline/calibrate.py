"""Phase 5 캘리브레이션 1단계 — 격자 규약 탐색.

관측초(분모)는 이벤트 정의와 무관하게 격자 규약에만 의존한다.
목표 셀에서 05-16=64초, 08-05=133초가 나오는 규약을 찾는다.

실행:  python -m pipeline.calibrate
"""
from __future__ import annotations

import collections
import math
from dataclasses import dataclass

from . import db, events

#: 기획서 실측 목표 (셀 좌표 → {세션: (이벤트초, 관측초)})
TARGETS = {
    (37.40342, 127.10473): {"2022-05-16": (53, 64), "2022-08-05": (113, 133)},
    (37.39622, 127.10878): {"2022-05-16": (47, 60), "2022-08-05": (34, 50)},
}

M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class GridSpec:
    name: str
    dlat: float
    dlon: float
    lat0: float = 0.0     # 앵커(원점)
    lon0: float = 0.0

    def cell(self, lat: float, lon: float) -> tuple[int, int]:
        return (math.floor((lat - self.lat0) / self.dlat),
                math.floor((lon - self.lon0) / self.dlon))


def specs(size_m: float = 40.0) -> list[GridSpec]:
    """격자 규약 후보."""
    ref_lat = 37.40
    exact_lat = size_m / M_PER_DEG_LAT                                  # 3.5932e-4
    exact_lon = size_m / (M_PER_DEG_LAT * math.cos(math.radians(ref_lat)))  # 4.5218e-4
    round_lat, round_lon = 0.00036, 0.00045
    # 판교 영역 좌하단 앵커 (지도 뷰포트 최소값)
    anc_lat, anc_lon = 37.3957615, 127.1027615

    out = [
        GridSpec("C1 정확·원점0", exact_lat, exact_lon),
        GridSpec("C2 반올림·원점0", round_lat, round_lon),
        GridSpec("C3 정확·판교앵커", exact_lat, exact_lon, anc_lat, anc_lon),
        GridSpec("C4 반올림·판교앵커", round_lat, round_lon, anc_lat, anc_lon),
        # 경도도 위도와 같은 상수를 쓰는(코사인 미보정) 흔한 구현
        GridSpec("C5 정사각도·원점0", exact_lat, exact_lat),
        GridSpec("C6 반올림정사각·원점0", round_lat, round_lat),
    ]
    return out


def counts_for(spec: GridSpec, obs_by_session: dict[str, list]) -> dict:
    """세션별 셀→관측초 수."""
    out = {}
    for sid, obs in obs_by_session.items():
        c = collections.Counter(spec.cell(o.lat, o.lon) for o in obs)
        out[sid] = c
    return out


def report(size_m: float = 40.0) -> None:
    with db.connect() as conn:
        obs_by_session = {sid: events.observations(conn, sid)
                          for sid in ("2022-05-16", "2022-08-05")}

    print(f"■ 격자 {size_m:.0f}m — 세션 관측초: " +
          " · ".join(f"{s}={len(o)}" for s, o in obs_by_session.items()))
    print()

    for spec in specs(size_m):
        cnt = counts_for(spec, obs_by_session)
        print(f"── {spec.name}  Δlat={spec.dlat:.6f} Δlon={spec.dlon:.6f}")
        for (tlat, tlon), want in TARGETS.items():
            key = spec.cell(tlat, tlon)
            line = f"   ({tlat}, {tlon}) → cell {key[0]}:{key[1]}"
            hits = []
            for sid, (_, want_obs) in want.items():
                got = cnt[sid].get(key, 0)
                mark = "✓" if got == want_obs else " "
                hits.append(f"{sid[5:]} {got:>4}/{want_obs:<4}{mark}")
            print(line + "   " + "  ".join(hits))
        # 각 세션의 최대 밀집 셀 — 목표값과 비슷한 규모가 존재하는지
        for sid in obs_by_session:
            top = cnt[sid].most_common(3)
            s = "  ".join(f"{k[0]}:{k[1]}={v}" for k, v in top)
            print(f"   상위 밀집 [{sid}]  {s}")
        print()


if __name__ == "__main__":
    report(40.0)
