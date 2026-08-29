"""파이프라인 오케스트레이션 · 인수 검증 · 시드 덤프.

    python -m pipeline.run --all           ①→⑧ 전체
    python -m pipeline.run --step grid     단계별
    python -m pipeline.run --verify        인수 기준 검사 (실패 시 exit 1)
    python -m pipeline.run --dump-seed     db/02_seed.sql 생성
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

from . import db, demo_layers, grid, ingest, nodelink, quality, repeat
from .codebook import VERIFIED

STEPS = {
    "ingest": ("① 적재·세션식별", ingest.run),
    "quality": ("③ 품질검증", quality.run),
    "grid": ("⑥ 격자집계", grid.run),
    "repeat": ("⑦ 반복성판정", repeat.run),
    "nodelink": ("⑧ 도로명매핑", nodelink.run),
    "demo": ("⑨ 시연 레이어", demo_layers.run),
}


# ── 인수 기준 ─────────────────────────────────────────────────────────
# 1차는 기획서 실측값, 2차는 파이프라인 실행 결과를 회귀 기준선으로 고정한다.
# 2차가 기획서와 다른 항목은 docs/thresholds.md §F의 폴백 절차로 채택된 값이다.

def _one(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def is_seed_only(conn: psycopg.Connection) -> bool:
    """시드로만 채워진 DB인가.

    02_seed.sql은 집계 테이블은 전량, driving_records는 세션별 샘플만 담는다.
    원본 레코드 수를 세는 검사는 이 상태에서 의미가 없으므로 건너뛴다.
    """
    with conn.cursor() as cur:
        loaded = _one(cur,
            """select coalesce(sum(record_count),0) from session_files
               where loaded_to_db""") or 0
        actual = _one(cur, "select count(*) from driving_records") or 0
    return actual < loaded


def checks(conn: psycopg.Connection) -> list[tuple[str, str, object, object]]:
    """(등급, 항목, 실측, 기대). 시드 DB에서는 원본 기준 항목을 뺀다."""
    out = []
    raw = not is_seed_only(conn)
    with conn.cursor() as cur:
        out.append(("1차", "4종 적재 합계", _one(cur,
            "select coalesce(sum(record_count),0) from session_files where dataset_kind <> 'CONTROL'"),
            843_734))
        out.append(("1차", "세션 수", _one(cur, "select count(*) from sessions"), 8))
        out.append(("1차", "라벨 불일치 세션", _one(cur,
            "select count(*) from sessions where label_mismatch"), 4))
        if raw:
            out.append(("1차", "BSM 좌표 유효", _one(cur,
                """select count(*) from driving_records
                   where dataset_kind='BSM' and valid_coord"""), 39_546))
            out.append(("1차", "BSM 전체", _one(cur,
                "select count(*) from driving_records where dataset_kind='BSM'"), 40_010))
            # 이벤트 추출 단계에서 센다. 격자 집계 후에는 관측 30건 미만 셀이
            # 걸러지므로 셀 기준으로 세면 실제보다 적게 나온다.
            out.append(("1차", "잔존 emergency", _one(cur,
                """select count(*) from (
                     select session_id, obs_second from driving_records
                     where dataset_kind='BSM' and valid_coord and obs_second is not null
                     group by session_id, obs_second
                     having bool_or(coalesce(f_manual_emg,false)
                                    or coalesce(f_auto_emg,false)
                                    or coalesce(f_sensor_trb,false))
                   ) t"""), 3))
        out.append(("1차", "정규화 오판 보정", VERIFIED["corrected_misjudgements"], 15_585))
        for cell, sid, want in (("21:4", "2022-05-16", 64), ("21:4", "2022-08-05", 133),
                                ("1:13", "2022-05-16", 60)):
            out.append(("1차", f"관측초 {cell}/{sid[5:]}", _one(cur,
                "select observation_count from cell_observations where cell_key=%s and session_id=%s",
                (cell, sid)), want))

        for cell, sid, want in (("21:4", "2022-05-16", 52), ("21:4", "2022-08-05", 116),
                                ("1:13", "2022-05-16", 47), ("1:13", "2022-08-05", 37)):
            out.append(("2차", f"이벤트초 {cell}/{sid[5:]}", _one(cur,
                "select event_count from cell_observations where cell_key=%s and session_id=%s",
                (cell, sid)), want))
        out.append(("2차", "취약구간 후보", _one(cur,
            "select count(*) from road_issues where is_candidate"), 24))
        out.append(("2차", "낮음", _one(cur,
            "select count(*) from road_issues where classification='low'"), 18))
        out.append(("2차", "도로망 밖(>50m)", _one(cur,
            "select count(*) from grid_cells where link_dist_m > 50"), 0))
        # 전 셀이 링크에 매핑돼야 한다. 그중 13곳은 노드링크에 도로명이 없는
        # 무명 구간이라 road_name이 NULL이다 — 매핑 실패가 아니다.
        out.append(("2차", "링크 매핑된 셀", _one(cur,
            "select count(*) from grid_cells where link_id is not null"), 89))
        out.append(("2차", "도로명 있는 셀", _one(cur,
            "select count(*) from grid_cells where road_name is not null"), 76))
        # ⑨ 시연 레이어 — 지도에 찍히는 수는 좌표 유효분만이라 15,588 과 다르다
        out.append(("2차", "정규화전 지도표시", _one(cur,
            "select count(*) from normalization_points where raw_emergency"), 15_124))
        out.append(("2차", "정규화후 지도표시", _one(cur,
            "select count(*) from normalization_points where normalized_emergency"), 3))
        out.append(("2차", "궤적 점", _one(cur,
            "select count(*) from trajectories"), 2_945))
    return out


def verify(conn: psycopg.Connection) -> bool:
    rows = checks(conn)
    if is_seed_only(conn):
        print("  ※ 시드 DB — 원본 레코드 기준 항목은 검사하지 않는다 (make ingest 후 재실행)")
    print(f"{'':4}{'항목':<26}{'실측':>10}{'기대':>10}")
    print("─" * 54)
    ok = True
    for grade, name, got, want in rows:
        hit = got == want
        if grade == "1차" and not hit:
            ok = False
        mark = "✓" if hit else ("✗" if grade == "1차" else "△")
        g = f"{got:,}" if isinstance(got, int) else str(got)
        w = f"{want:,}" if isinstance(want, int) else str(want)
        print(f"{mark:<4}{name:<26}{g:>10}{w:>10}  {grade}")
    print("─" * 54)
    print("1차 인수 기준 " + ("전부 통과" if ok else "미달 — 파이프라인 재확인 필요"))
    return ok


# ── 시드 덤프 ─────────────────────────────────────────────────────────
#: 덤프 순서와 각 테이블의 정렬 키. Postgres는 ORDER BY 없이는 heap 순서로
#: 돌려주므로, 같은 데이터라도 재덤프할 때마다 행 순서가 바뀐다. 시드를
#: 저장소에 커밋하는 이상 diff가 깨끗해야 하므로 정렬을 고정한다.
SEED_TABLES = (
    ("sessions", "id"),
    ("session_files", "id"),
    ("quality_checks", "id"),
    ("grid_cells", "cell_key"),
    ("cell_observations", "id"),
    ("road_issues", "cell_key"),
    ("inspections", "id"),
    ("normalization_points", "id"),
    ("trajectories", "id"),
)
SAMPLE_PER_SESSION = 1_000


def _lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        # TEXT[] 컬럼(available_metrics·event_types)은 JSON이 아니라 배열 리터럴이어야
        # psql이 읽는다. json.dumps로 내면 initdb가 malformed array literal로 죽는다.
        if not v:
            return "'{}'::text[]"
        return "ARRAY[" + ", ".join(_lit(x) for x in v) + "]::text[]"
    if isinstance(v, dict):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'"
    return "'" + str(v).replace("'", "''") + "'"


def _dump_table(cur, table: str, clause: str = "") -> list[str]:
    cur.execute(f"select * from {table} {clause}")
    cols = [d.name for d in cur.description]
    lines = []
    for row in cur.fetchall():
        vals = ", ".join(_lit(v) for v in row)
        lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});")
    return lines


def dump_seed(conn: psycopg.Connection, path: Path) -> int:
    parts = ["-- 자동 생성 — pipeline.run --dump-seed 로만 만든다 (수동 편집 금지)",
             "-- 집계 테이블은 전량, driving_records는 세션별 샘플만 담는다.",
             "-- 전량 재현은 make ingest 가 담당한다.", ""]
    with conn.cursor() as cur:
        for t, key in SEED_TABLES:
            parts.append(f"-- {t}")
            parts += _dump_table(cur, t, f"order by {key}")
            parts.append("")
        parts.append("-- driving_records (세션별 샘플)")
        cur.execute("select id from sessions order by id")
        for (sid,) in cur.fetchall():
            parts += _dump_table(
                cur, "driving_records",
                f"where session_id = '{sid}' order by id limit {SAMPLE_PER_SESSION}")
        parts.append("")
        # 시퀀스 정렬
        for t in ("session_files", "quality_checks", "cell_observations",
                  "inspections", "driving_records"):
            parts.append(
                f"SELECT setval(pg_get_serial_sequence('{t}','id'), "
                f"coalesce((SELECT max(id) FROM {t}), 1));")
    text = "\n".join(parts) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text)


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(prog="pipeline.run")
    ap.add_argument("--all", action="store_true", help="①→⑧ 전체 실행")
    ap.add_argument("--step", choices=list(STEPS), help="단계 하나만 실행")
    ap.add_argument("--verify", action="store_true", help="인수 기준 검사")
    ap.add_argument("--dump-seed", action="store_true", help="db/02_seed.sql 생성")
    a = ap.parse_args()
    if not (a.all or a.step or a.verify or a.dump_seed):
        ap.print_help()
        return 2

    with db.connect() as conn:
        if a.all or a.step:
            names = list(STEPS) if a.all else [a.step]
            for n in names:
                label, fn = STEPS[n]
                r = fn(conn)
                extra = ""
                if isinstance(r, dict) and r:
                    extra = "  " + str(r)[:90]
                elif isinstance(r, list):
                    extra = f"  {len(r)}건"
                print(f"  {label}{extra}")
        if a.dump_seed:
            p = Path(__file__).resolve().parents[1] / "db" / "02_seed.sql"
            n = dump_seed(conn, p)
            print(f"  시드 생성 {p.name}  {n/1024:.0f} KB")
        if a.verify:
            return 0 if verify(conn) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
