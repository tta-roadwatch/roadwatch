"""⑨ 시연용 지도 레이어 추출.

분석에는 쓰이지 않는다. 분석 결과를 **눈으로 보이게** 만드는 단계다.

집계된 숫자는 머리로는 이해되지만 눈에 꽂히지 않는다. "15,585건이 오판된다"는
문장보다, 판교 지도가 비상정지 마커로 뒤덮였다가 토글 하나로 3개만 남는 장면이
같은 사실을 훨씬 강하게 전달한다. 그 장면에 필요한 좌표를 여기서 뽑는다.

두 가지를 만든다.

  normalization_points  같은 BSM 레코드를 두 코드북으로 판정한 결과 + 좌표.
                        정규화 안 함 15,588건 / 정규화 3건.
  trajectories          초당 대표 위치. 격자 사각형이 아니라 차량이 실제로
                        지나간 경로를 그리기 위한 것.
"""
from __future__ import annotations

import psycopg

from . import sources as S
from .codebook import EMERGENCY_FLAGS, SESSION_CODEBOOK, STANDARD, detect

#: 한국 영역 대략 경계 — ingest 와 같은 기준
LAT_RANGE = (33.0, 39.0)
LON_RANGE = (124.0, 132.0)

#: 코드북 판별용 표본 (ingest 와 동일)
DETECT_SAMPLE = 2000


def _valid(lat, lon) -> bool:
    if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
        return False
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── 정규화 대비 지점 ──────────────────────────────────────────────────

def normalization_points(conn: psycopg.Connection) -> dict:
    """BSM 원본을 두 번 판정해 좌표와 함께 적재한다.

    '정규화 안 함' 은 표준 체계(1 = 발생)를 전 세션에 그대로 적용한 것이다.
    세션마다 코드가 반대라는 사실을 모르면 누구나 이렇게 판정한다 — 그게
    바로 이 서비스가 보여주려는 함정이다.
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE normalization_points RESTART IDENTITY")

    counts = {"raw": 0, "normalized": 0, "rows": 0}
    for src in S.all_sources():
        if src.kind != S.BSM:
            continue
        path = S.raw_path(src)
        if not path.exists():
            continue

        stream = S.stream(path)
        head = []
        for rec in stream:
            head.append(rec)
            if len(head) >= DETECT_SAMPLE:
                break
        if not head:
            continue
        cb = SESSION_CODEBOOK.get(src.session_id) or detect(head)

        rows = []
        for rec in (r for chunk in (head, stream) for r in chunk):
            lat, lon = _f(rec.get("la")), _f(rec.get("lo"))
            if not _valid(lat, lon):
                continue

            hit_raw, hit_norm, names = False, False, []
            for f in EMERGENCY_FLAGS:
                v = rec.get(f)
                if STANDARD.flag(f, v):
                    hit_raw = True
                    names.append(f)
                if cb.flag(f, v):
                    hit_norm = True
            if not (hit_raw or hit_norm):
                continue

            counts["raw"] += hit_raw
            counts["normalized"] += hit_norm
            rows.append((src.session_id, S.observed_at(S.BSM, rec), lat, lon,
                         cb.name, hit_raw, hit_norm, names))

        if rows:
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY normalization_points (session_id, observed_at, lat, lon, "
                    "codebook, raw_emergency, normalized_emergency, flags) FROM STDIN"
                ) as cp:
                    for r in rows:
                        cp.write_row(r)
            counts["rows"] += len(rows)
    conn.commit()
    return counts


# ── 주행 궤적 ─────────────────────────────────────────────────────────

def trajectories(conn: psycopg.Connection) -> dict:
    """초당 대표 위치. 초의 첫 좌표를 쓴다.

    격자 집계에서는 한 초가 셀 경계에 걸치면 양쪽 모두에서 센다(§F-1). 하지만
    선을 그릴 때는 초마다 점이 하나여야 경로가 끊기지 않으므로 여기서는
    첫 좌표만 쓴다. 목적이 다르므로 규칙도 다르다.
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE trajectories RESTART IDENTITY")

    out: dict[str, int] = {}
    for src in S.all_sources():
        if src.kind != S.GPS:
            continue
        path = S.raw_path(src)
        if not path.exists():
            continue

        seen: dict[int, tuple] = {}
        for rec in S.stream(path):
            lat, lon = _f(rec.get("la")), _f(rec.get("lo"))
            if not _valid(lat, lon):
                continue
            dt = S.observed_at(S.GPS, rec)
            if dt is None:
                continue
            sec = int(dt.timestamp())
            if sec not in seen:
                seen[sec] = (src.session_id, sec, dt, lat, lon)

        if seen:
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY trajectories (session_id, obs_second, observed_at, lat, lon) "
                    "FROM STDIN"
                ) as cp:
                    for sec in sorted(seen):
                        cp.write_row(seen[sec])
            out[src.session_id] = len(seen)
    conn.commit()
    return out


def run(conn: psycopg.Connection) -> dict:
    n = normalization_points(conn)
    t = trajectories(conn)
    return {"정규화대비": n, "궤적": t}
