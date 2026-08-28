"""③.5 분포 분석 — 이벤트 임계값을 정하기 위한 1회성 탐색.

계획 §3.4의 미결정 5건을 수치 근거로 확정한다. 결과는 docs/thresholds.md에 기록.
실행:  python -m pipeline.explore
"""
from __future__ import annotations

import collections
import statistics
from dataclasses import dataclass, field

from . import sources as S


def pct(xs: list[float], ps=(10, 50, 90, 95, 99)) -> dict[int, float]:
    if not xs:
        return {}
    xs = sorted(xs)
    out = {}
    for p in ps:
        i = min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))
        out[p] = xs[i]
    return out


def fmt_pct(d: dict[int, float]) -> str:
    return "  ".join(f"p{p}={v:.2f}" for p, v in d.items())


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── A. autonm_flg × 속도 (BSM) ────────────────────────────────────────

def analyze_bsm() -> None:
    print("━━ A. autonm_flg 의미 판별 (BSM) ━━")
    print(f"{'세션':<12}{'값':>4}{'건수':>9}{'비중':>8}   속도 분포(m/s)")
    for src in [s for s in S.SOURCES if s.kind == S.BSM]:
        groups: dict[str, list[float]] = collections.defaultdict(list)
        moving: dict[str, int] = collections.Counter()
        for rec in S.stream(S.raw_path(src)):
            a = str(rec.get("autonm_flg", "")).strip()
            v = _f(rec.get("ve"))
            if v is not None:
                groups[a].append(v)
                if v > 1.0:
                    moving[a] += 1
        total = sum(len(v) for v in groups.values())
        for a in sorted(groups):
            xs = groups[a]
            mv = moving[a] / len(xs) * 100
            print(f"{src.session_id:<12}{a:>4}{len(xs):>9,}{len(xs)/total*100:>7.1f}%"
                  f"   {fmt_pct(pct(xs, (50, 90)))}  주행중(>1m/s) {mv:.0f}%")
    print()


# ── B. STATUS 상태 코드 3종 ───────────────────────────────────────────

def analyze_status() -> None:
    print("━━ B. auto_sttus / ster_sttus / ve_sttus 값 분포 (STATUS) ━━")
    for src in [s for s in S.SOURCES if s.kind == S.STATUS]:
        c: dict[str, collections.Counter] = {k: collections.Counter() for k in
                                             ("auto_sttus", "ster_sttus", "ve_sttus")}
        combo = collections.Counter()
        n = 0
        for rec in S.stream(S.raw_path(src)):
            n += 1
            vals = tuple(str(rec.get(k, "")).strip() for k in c)
            for k, v in zip(c, vals):
                c[k][v] += 1
            combo[vals] += 1
        print(f"[{src.session_id}]  {n:,}건")
        for k, cnt in c.items():
            tops = "  ".join(f"{v!r}:{cn:,}" for v, cn in cnt.most_common(4))
            print(f"  {k:<12} 고유 {len(cnt):>2}  {tops}")
        print(f"  조합 상위: ", end="")
        print("  ".join(f"{v}:{cn:,}" for v, cn in combo.most_common(3)))
    print()


# ── C. ve vs goal_ve (STATUS) ─────────────────────────────────────────

def analyze_speed() -> None:
    print("━━ C. 목표속도 미달 (ve / goal_ve, STATUS) ━━")
    for src in [s for s in S.SOURCES if s.kind == S.STATUS]:
        ratios, zero_goal, n = [], 0, 0
        for rec in S.stream(S.raw_path(src)):
            n += 1
            gv, v = _f(rec.get("goal_ve")), _f(rec.get("ve"))
            if gv is None or v is None:
                continue
            if gv <= 0.5:          # 목표 자체가 정지·서행이면 미달 개념 없음
                zero_goal += 1
                continue
            ratios.append(v / gv)
        print(f"[{src.session_id}]  {n:,}건 · 목표≤0.5m/s {zero_goal/n*100:.0f}% 제외 · "
              f"비교대상 {len(ratios):,}건")
        print(f"  ve/goal_ve  {fmt_pct(pct(ratios, (5, 10, 25, 50, 90)))}")
        for th in (0.3, 0.5, 0.7):
            below = sum(1 for r in ratios if r < th)
            print(f"  임계 <{th}: {below:,}건 ({below/len(ratios)*100:.1f}%)")
    print()


# ── D. obcl_nmbr (OBJECT) ────────────────────────────────────────────

def analyze_objects() -> None:
    print("━━ D. 경로 장애물 밀집 (obcl_nmbr, OBJECT — 조인 대상 세션만) ━━")
    for src in [s for s in S.SOURCES if s.kind == S.OBJECT
                and s.session_id in ("2022-05-16", "2022-08-05")]:
        per_sec_max: dict[int, float] = {}
        per_sec_cnt = collections.Counter()
        vals = []
        for rec in S.stream(S.raw_path(src)):
            sec_dt = S.parse_ss_num(rec.get("ss_num"))
            v = _f(rec.get("obcl_nmbr"))
            if v is not None:
                vals.append(v)
            if sec_dt and v is not None:
                sec = int(sec_dt.timestamp())
                per_sec_cnt[sec] += 1
                per_sec_max[sec] = max(per_sec_max.get(sec, 0), v)
        mx = list(per_sec_max.values())
        print(f"[{src.session_id}]  레코드 {len(vals):,} · 관측 {len(per_sec_max):,}초 · "
              f"초당 레코드 {fmt_pct(pct([float(c) for c in per_sec_cnt.values()], (50, 90)))}")
        print(f"  obcl_nmbr(레코드)  {fmt_pct(pct(vals, (50, 90, 95, 99)))}")
        print(f"  초당 최대          {fmt_pct(pct(mx, (50, 75, 90, 95)))}")
        for th in (5, 10, 15, 20):
            above = sum(1 for m in mx if m >= th)
            print(f"  임계 ≥{th}: {above:,}초 ({above/len(mx)*100:.1f}%)")
    print()


# ── E. GPS 초당 레코드 수 ─────────────────────────────────────────────

def analyze_gps() -> None:
    print("━━ E. GPS 초당 레코드 수 (초 대표 위치 규칙) ━━")
    for src in [s for s in S.SOURCES if s.kind == S.GPS]:
        per_sec = collections.Counter()
        spread = []          # 같은 초 안에서 좌표가 얼마나 움직이는가 (m)
        cur_sec, lats, lons = None, [], []
        for rec in S.stream(S.raw_path(src)):
            dt = S.parse_ss_num(rec.get("ss_num"))
            la, lo = _f(rec.get("la")), _f(rec.get("lo"))
            if dt is None or la is None:
                continue
            sec = int(dt.timestamp())
            per_sec[sec] += 1
            if sec != cur_sec:
                if len(lats) > 1:
                    dm = ((max(lats) - min(lats)) * 111_320,
                          (max(lons) - min(lons)) * 88_430)
                    spread.append(max(dm))
                cur_sec, lats, lons = sec, [], []
            lats.append(la); lons.append(lo)
        cnts = [float(c) for c in per_sec.values()]
        print(f"[{src.session_id}]  관측 {len(per_sec):,}초 · "
              f"초당 레코드 {fmt_pct(pct(cnts, (10, 50, 90)))} · "
              f"초내 좌표 이동 {fmt_pct(pct(spread, (50, 90, 99)))}m")
    print()


if __name__ == "__main__":
    analyze_bsm()
    analyze_status()
    analyze_speed()
    analyze_objects()
    analyze_gps()
