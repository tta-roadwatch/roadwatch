"""③ 품질검증 5종.

기획서 5.4절에서 실측한 데이터 품질 문제를 그대로 검증 규칙으로 옮겼다.
검증 규칙의 근거는 TTAK.KO-10.1331-Part4/R1 5.3의 속성 명세(필수여부·데이터 타입)다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg

from . import sources as S

PASS, WARN, EXCLUDED = "pass", "warn", "excluded"

#: 데이터셋별 필수 필드 (공간데이터마켓 스키마 기준)
REQUIRED: dict[str, tuple[str, ...]] = {
    S.BSM: ("colct_dt", "vhcl_id", "la", "lo", "ve",
            "mnl_emg_flg", "auto_emg_flg", "snsr_trb_flg", "vhcl_sttus_flg", "autonm_flg"),
    S.GPS: ("colct_dt", "la", "lo", "ss_num"),
    S.STATUS: ("colct_dt", "ss_num", "ve", "goal_ve",
               "auto_sttus", "ster_sttus", "ve_sttus"),
    S.OBJECT: ("colct_dt", "ss_num", "obcl_nmbr"),
    S.CONTROL: ("colct_dt", "ss_num"),
}

#: 상수 판정에서 제외할 필드 — 이 필드들의 상수성은 코드북 판별 근거이지
#: 정보 없음의 신호가 아니다 (기획서 5.4절 (1) 참조)
CODEBOOK_FIELDS = frozenset({
    "mnl_emg_flg", "auto_emg_flg", "snsr_trb_flg", "vhcl_sttus_flg",
})


@dataclass
class Check:
    session_id: str
    name: str
    status: str
    detail: dict


# ── 파일 스캔 : 필수 필드 + 상수 필드 (한 번의 패스로 둘 다) ──────────────

def scan_file(src: S.SourceFile) -> tuple[int, dict[str, int], dict[str, str]]:
    """(총 건수, 필수필드별 결측 수, 상수 필드→값)."""
    required = REQUIRED.get(src.kind, ())
    missing = {f: 0 for f in required}

    total = 0
    # 상수 후보 : 두 번째 값이 나오면 즉시 탈락시켜 비용을 줄인다
    candidates: dict[str, str] | None = None
    dropped: set[str] = set()

    for rec in S.stream(S.raw_path(src)):
        total += 1
        for f in required:
            v = rec.get(f)
            if v is None or (isinstance(v, str) and not v.strip()):
                missing[f] += 1
        if candidates is None:
            candidates = {k: str(v) for k, v in rec.items()}
        else:
            for k in list(candidates):
                if k in dropped:
                    continue
                if str(rec.get(k)) != candidates[k]:
                    dropped.add(k)
                    del candidates[k]
    return total, missing, (candidates or {})


def run(conn: psycopg.Connection) -> list[Check]:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE quality_checks RESTART IDENTITY")

    # 세션별로 파일을 모은다
    by_session: dict[str, list[S.SourceFile]] = {}
    for src in S.SOURCES:
        by_session.setdefault(src.session_id, []).append(src)

    checks: list[Check] = []

    for sid, srcs in sorted(by_session.items()):
        miss_total: dict[str, int] = {}
        const_by_kind: dict[str, dict[str, str]] = {}
        counts: dict[str, int] = {}

        for src in srcs:
            total, missing, consts = scan_file(src)
            counts[src.filename] = total
            for f, n in missing.items():
                if n:
                    miss_total[f"{src.kind}.{f}"] = n
            consts = {k: v for k, v in consts.items() if k not in CODEBOOK_FIELDS}
            if consts:
                const_by_kind[src.kind] = consts

        # ① 필수 필드
        checks.append(Check(sid, "required_fields",
                            WARN if miss_total else PASS,
                            {"missing": miss_total, "files": counts}))

        # ② 상수 필드
        flat = sorted({f"{k}.{f}" for k, d in const_by_kind.items() for f in d})
        checks.append(Check(sid, "constant_fields",
                            WARN if flat else PASS,
                            {"fields": flat,
                             "values": {k: d for k, d in const_by_kind.items()},
                             "note": "전 레코드 동일값 — 분석에서 제외"}))

    # ③ 좌표 유효 범위 · ④ 라벨 정합 · ⑤ 측정 가능 지표 — DB에서
    with conn.cursor() as cur:
        cur.execute("""
            select s.id, s.label_date, s.actual_start, s.label_mismatch,
                   s.available_metrics,
                   count(d.id) filter (where d.id is not null) as total,
                   count(d.id) filter (where d.valid_coord) as valid
            from sessions s
            left join driving_records d on d.session_id = s.id
            group by s.id, s.label_date, s.actual_start, s.label_mismatch, s.available_metrics
            order by s.id
        """)
        for sid, label, start, mismatch, metrics, total, valid in cur.fetchall():
            if total:
                rate = valid / total
                checks.append(Check(sid, "coord_range",
                                    PASS if valid == total else WARN,
                                    {"valid": valid, "total": total,
                                     "rate": round(rate * 100, 1),
                                     "invalid": total - valid}))
            else:
                checks.append(Check(sid, "coord_range", EXCLUDED,
                                    {"note": "좌표 보유 데이터셋 없음 (조인 대상)"}))

            checks.append(Check(sid, "label_consistency",
                                WARN if mismatch else PASS,
                                {"label_date": str(label) if label else None,
                                 "actual_year": start.year if start else None,
                                 "gap_years": (start.year - label.year) if (start and label) else 0}))

            n = len(metrics or [])
            checks.append(Check(sid, "metric_availability",
                                PASS if n >= 4 else (EXCLUDED if n == 0 else WARN),
                                {"count": n, "metrics": list(metrics or []),
                                 "note": "측정 불가와 이벤트 0%를 구분한다"}))

    with conn.cursor() as cur:
        for c in checks:
            cur.execute(
                "INSERT INTO quality_checks (session_id, check_name, status, detail) "
                "VALUES (%s,%s,%s,%s)",
                (c.session_id, c.name, c.status, json.dumps(c.detail, ensure_ascii=False)),
            )
    conn.commit()
    return checks
