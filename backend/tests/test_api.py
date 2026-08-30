"""조회 API 회귀 테스트.

인수 기준(test_acceptance.py)이 분석 결과를 지킨다면, 이쪽은 그 결과를 표준
형식으로 내보내는 계약을 지킨다. 특히 NGSI-LD 정규 표현법과 Part3 오류 형식은
눈으로 보면 맞아 보이지만 조금씩 어긋나기 쉬워서 고정해둔다.

DB 가 없으면 전부 skip 한다.

    cd backend && ./.venv/bin/python -m pytest tests/ -v
"""
from __future__ import annotations

import pytest

from app import ngsild

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def restores_db():
    """쓰기 테스트가 남긴 흔적을 되돌린다.

    이 API 의 쓰기 경로는 점검 등록 하나뿐이지만, 그게 road_issues.is_candidate
    까지 바꾼다. 정리하지 않으면 두 번째 실행에서 후보 수가 24가 아니라 23이
    되어 대시보드·인수 기준 테스트가 함께 깨진다. 실제로 겪었다.
    """
    from pipeline import db
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("select cell_key, is_candidate from road_issues")
        before = dict(cur.fetchall())
        cur.execute("select coalesce(max(id), 0) from inspections")
        max_id = cur.fetchone()[0]
    conn.commit()
    yield
    with conn.cursor() as cur:
        cur.execute("delete from inspections where id > %s", (max_id,))
        for key, flag in before.items():
            cur.execute("update road_issues set is_candidate = %s where cell_key = %s",
                        (flag, key))
    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def token(client):
    """테스트 로그인으로 발급받은 토큰. 쓰기 경로에 붙인다."""
    r = client.post("/api/auth/demo-login")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    from app.main import app
    from pipeline import db
    try:
        db.connect().close()
    except Exception as e:
        pytest.skip(f"DB에 연결할 수 없다: {e}")
    with TestClient(app) as c:
        yield c


# ── NGSI-LD 정규 표현법 (TTAK.KO-10.1331-Part4/R1) ────────────────────

def test_entity_uses_normalized_representation(client):
    """값을 그냥 넣지 않고 속성 종류를 밝혀야 한다."""
    r = client.get("/ngsi-ld/v1/entities", params={"type": "TrafficEvent", "limit": 1})
    assert r.status_code == 200
    e = r.json()[0]

    assert e["id"].startswith("urn:ngsi-ld:TrafficEvent:")
    assert e["type"] == "TrafficEvent"
    assert "@context" in e and ngsild.CORE_CONTEXT in e["@context"]

    # Property 는 type/value 를 갖는다 — 평탄한 값이면 정규 표현법이 아니다
    assert e["category"]["type"] == "Property"
    assert e["category"]["value"] == "roadCondition"


def test_location_is_geoproperty_with_lon_lat_order(client):
    """GeoJSON 은 [경도, 위도] 다. 뒤집히면 판교가 바다로 간다."""
    r = client.get("/ngsi-ld/v1/entities", params={"type": "TrafficEvent", "limit": 20})
    for e in r.json():
        loc = e.get("location")
        if loc is None:
            continue
        assert loc["type"] == "GeoProperty"
        assert loc["value"]["type"] == "Point"
        lon, lat = loc["value"]["coordinates"]
        assert 126.9 < lon < 127.3, f"경도 자리에 위도가 들어갔다: {lon}"
        assert 37.3 < lat < 37.5, f"위도 자리에 경도가 들어갔다: {lat}"


def test_vehicle_traffic_links_to_event_and_dataset(client):
    """관측은 어느 구간·어느 데이터세트의 것인지 Relationship 으로 가리킨다."""
    r = client.get("/ngsi-ld/v1/entities",
                   params={"type": "VehicleTraffic", "limit": 1})
    e = r.json()[0]
    assert e["refTrafficEvent"]["type"] == "Relationship"
    assert e["refTrafficEvent"]["object"].startswith("urn:ngsi-ld:TrafficEvent:")
    assert e["refDataset"]["object"].startswith("urn:ngsi-ld:Dataset:")


def test_key_values_flattens(client):
    """options=keyValues 는 축약형 — 화면이 .value 를 파고들지 않게 한다."""
    r = client.get("/ngsi-ld/v1/entities",
                   params={"type": "TrafficEvent", "limit": 1, "options": "keyValues"})
    e = r.json()[0]
    assert e["category"] == "roadCondition"          # dict 가 아니라 값
    assert "@context" not in e


def test_service_context_is_served(client):
    """엔티티의 @context 가 가리키는 경로가 실제로 서빙돼야 한다.

    깨진 컨텍스트 URI 를 싣는 건 표준을 지킨 게 아니다.
    """
    r = client.get(ngsild.SERVICE_CONTEXT_PATH)
    assert r.status_code == 200
    ctx = r.json()["@context"]
    # 코어에 없는 용어는 전부 여기 정의돼 있어야 한다
    for term in ("eventRate", "measurable", "refTrafficEvent"):
        assert term in ctx


def test_entity_roundtrip_by_urn(client):
    r = client.get("/ngsi-ld/v1/entities", params={"type": "TrafficEvent", "limit": 1})
    urn = r.json()[0]["id"]
    one = client.get(f"/ngsi-ld/v1/entities/{urn}")
    assert one.status_code == 200
    assert one.json()["id"] == urn


# ── 데이터세트 메타데이터 (TTAK.KO-10.1398) ───────────────────────────

def test_datasets_expose_measured_quality_problems(client):
    """5.4절에서 실측한 문제를 감추지 않고 메타데이터로 드러내야 한다."""
    r = client.get("/ngsi-ld/v1/datasets")
    assert r.status_code == 200
    ds = r.json()
    assert len(ds) == 8

    mismatched = [d for d in ds if d["dataQuality"]["labelMismatch"]]
    assert len(mismatched) == 4, "라벨 불일치 4개 세션이 드러나야 한다"

    for d in mismatched:
        # temporal 은 라벨이 아니라 복원한 실제 시각이어야 한다
        start = d["temporal"]["startDate"]
        assert start and not start.startswith(str(d["dataQuality"]["labelDate"])[:4])
        assert d["dataQuality"]["labelMismatchNote"]


def test_dataset_without_metrics_is_marked_unmeasurable(client):
    """측정 불가와 이벤트 0% 를 구분한다 — 혼동되면 빈 세션이 안전해 보인다."""
    ds = client.get("/ngsi-ld/v1/datasets").json()
    empty = [d for d in ds if not d["dataQuality"]["availableMetrics"]]
    assert empty, "지표가 없는 세션이 있어야 한다 (2022-06-16 · 2022-07-06)"
    for d in empty:
        assert d["dataQuality"]["measurable"] is False
        assert "측정 불가" in d["dataQuality"]["measurableNote"]


# ── Part3 5장 오류 형식 ───────────────────────────────────────────────

@pytest.mark.parametrize("path,status", [
    ("/api/cells/99:99", 404),
    ("/ngsi-ld/v1/datasets/9999-99-99", 404),
    ("/ngsi-ld/v1/entities?type=Nope", 400),
    ("/ngsi-ld/v1/entities/not-a-urn", 400),
])
def test_errors_use_problem_details(client, path, status):
    """FastAPI 기본 {"detail": ...} 이 아니라 ProblemDetails 여야 한다."""
    r = client.get(path)
    assert r.status_code == status
    b = r.json()
    assert set(b) >= {"type", "title", "status", "detail"}
    assert b["type"].startswith(ngsild.CORE_CONTEXT.rsplit("/v1/", 1)[0])
    assert b["status"] == status


# ── 화면 계약 ─────────────────────────────────────────────────────────

def test_dashboard_matches_pipeline(client):
    """화면 수치가 파이프라인 인수 기준과 같아야 한다."""
    d = client.get("/api/dashboard").json()
    assert d["stats"]["records"] == 843_734
    assert d["stats"]["sessions"] == 8
    assert d["stats"]["cells"] == 89
    assert d["classification"] == {"intermittent": 24, "always_manual": 0, "low": 18}


def test_dashboard_ranks_by_repeatability(client):
    """최댓값이 아니라 반복성 순이어야 한다.

    max 로 줄세우면 상위가 전부 1.0 이 되어 순위가 무의미해진다.
    """
    top = client.get("/api/dashboard").json()["top_candidates"]
    counts = [t["session_count"] for t in top]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] >= 4, "가장 여러 세션에서 반복된 구간이 먼저 와야 한다"


def test_normalization_reports_verified_numbers(client):
    """데모 하이라이트의 수치는 파이프라인 실측값과 같은 출처를 써야 한다."""
    n = client.get("/api/normalization").json()["normalization"]
    assert n["without_codebook"] == 15_588
    assert n["with_codebook"] == 3
    assert n["corrected"] == 15_585
    assert n["session_codebook"]["2022-10-03"] == "inverted"


def test_cell_detail_separates_metric_families(client):
    """BSM 갈래와 조인 갈래는 이벤트 정의가 달라 나란히 비교하면 안 된다.

    섞으면 대표 구간 21:4 가 0~100% 로 보여 재현성 주장이 무너진다.
    """
    d = client.get("/api/cells/21:4").json()
    fams = d["by_family"]
    assert set(fams) == {"joined", "bsm"}

    joined = fams["joined"]
    assert joined["min_event_rate"] > 0.75, "조인 갈래는 좁은 고이벤트 구간이어야 한다"
    assert joined["max_event_rate"] < 0.95
    # 기획서가 주장하는 두 세션이 여기 들어 있어야 한다
    ids = {s["session_id"] for s in joined["sessions"]}
    assert {"2022-05-16", "2022-08-05"} <= ids


def test_cell_detail_distinguishes_unobserved_from_zero(client):
    """관측 없음 · 측정 불가 · 이벤트 0% 는 서로 다른 상태다."""
    obs = client.get("/api/cells/21:4").json()["observations"]
    assert len(obs) == 8, "관측되지 않은 세션도 행으로 나와야 한다"
    assert any(o["observed"] is False for o in obs)
    for o in obs:
        if not o["observed"]:
            assert o["event_rate"] is None, "관측이 없으면 이벤트율이 0이 아니라 없음이다"


def test_comparison_marks_after_as_simulated(client):
    """조치 후 값을 실측처럼 보이게 하면 안 된다."""
    c = client.get("/api/cells/21:4/comparison").json()
    assert c["before"]["simulated"] is False
    assert c["after"]["simulated"] is True
    assert "시뮬레이션" in c["simulation_notice"]


# ── 점검 (유일한 쓰기 경로) ───────────────────────────────────────────

def test_inspection_lifecycle_and_false_positive_override(client, restores_db,
                                                        auth_headers):
    """사람이 시스템 판정을 뒤집을 수 있어야 한다.

    '상시 수동 운행 구간(도로 문제 아님)' 을 고르면 후보에서 내려간다.
    이 번복 가능성이 '원인을 단정하지 않는다'는 원칙의 실제 구현이다.
    """
    from app.routers.inspections import NOT_A_ROAD_ISSUE

    # 후보인 셀 하나를 고른다
    cells = client.get("/api/cells", params={"candidates_only": True}).json()
    target = cells[-1]["cell_key"]

    created = client.post("/api/inspections", headers=auth_headers, json={
        "cell_key": target, "findings": ["차선 마모"], "action": "재도색 요청",
    })
    assert created.status_code == 201
    iid = created.json()["id"]
    assert created.json()["status"] == "inspecting"

    # 오탐으로 번복
    upd = client.patch(f"/api/inspections/{iid}", headers=auth_headers, json={
        "findings": [NOT_A_ROAD_ISSUE], "status": "not_applicable"})
    assert upd.status_code == 200

    after = client.get(f"/api/cells/{target}").json()["cell"]
    assert after["is_candidate"] is False, "도로 문제 아님을 고르면 후보에서 내려가야 한다"
    # 분류 자체는 분석 결과이므로 사람이 바꾸지 않는다
    assert after["classification"] is not None


def test_inspection_rejects_unknown_finding(client, auth_headers):
    r = client.post("/api/inspections", headers=auth_headers,
                    json={"cell_key": "21:4", "findings": ["없는항목"]})
    assert r.status_code == 400
    assert r.json()["type"].endswith("BadRequestData")


# ── AI 리포트 ─────────────────────────────────────────────────────────

def test_report_falls_back_to_template_without_key(client, monkeypatch):
    """심사자가 키 없이 클론해도 화면이 깨지면 안 된다."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    r = client.post("/api/cells/21:4/report")
    assert r.status_code == 200
    b = r.json()
    assert b["generated_by"] == "template"
    assert b["text"].strip()
    assert "원인을 진단하지 않으며" in b["text"]


def test_report_does_not_assert_causes(client, monkeypatch):
    """리포트가 원인을 단정하면 서비스의 설계 원칙이 화면에서 무너진다."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    text = client.post("/api/cells/21:4/report").json()["text"]
    for banned in ("마모되었습니다", "때문입니다", "원인은 ", "확인되었습니다"):
        assert banned not in text, f"원인을 단정하는 표현이 있다: {banned}"


def test_report_percentages_match_documents(client, monkeypatch):
    """52/64 = 81.25% 를 문서는 81.3% 로 적는다. API 도 같아야 한다.

    파이썬 기본 포매팅(half-even)은 81.2 를 내므로 half-up 으로 맞춰뒀다.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    facts = client.post("/api/cells/21:4/report").json()["facts"]
    assert "81.3%" in facts
    assert "81.2%" not in facts


# ── 지도 레이어 (SCR-05) ──────────────────────────────────────────────

def test_cell_polygons_are_40m(client):
    """화면이 격자 규약을 몰라도 셀을 그릴 수 있어야 한다.

    중심점만 주면 프론트가 DLAT/DLON/LAT0/LON0 을 알아야 하는데, 그건
    캘리브레이션으로 정한 분석 규약이지 화면이 알 일이 아니다.
    """
    import math

    gj = client.get("/api/geo/cells").json()
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 89

    f = gj["features"][0]
    assert f["geometry"]["type"] == "Polygon"
    ring = f["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1], "폴리곤 링은 닫혀야 한다"

    (w, s), (e, n) = ring[0], ring[2]
    height = (n - s) * 111_320
    width = (e - w) * 111_320 * math.cos(math.radians(s))
    assert 38 < width < 42, f"셀 가로가 40m 가 아니다: {width:.1f}m"
    assert 38 < height < 42, f"셀 세로가 40m 가 아니다: {height:.1f}m"


def test_roadlinks_served_for_map(client):
    """도로망은 저장소에 있지만 Vite 가 frontend/ 밖을 서빙하지 않는다.

    파일을 복사하면 같은 데이터가 두 벌이 되므로 API 가 낸다.
    """
    gj = client.get("/api/geo/roadlinks").json()
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 1087
    assert gj["features"][0]["geometry"]["type"] == "LineString"

    named = client.get("/api/geo/roadlinks", params={"named_only": True}).json()
    assert 0 < len(named["features"]) < len(gj["features"])


def test_bounds_cover_all_cells(client):
    """지도 초기 뷰포트가 셀을 다 담아야 한다."""
    b = client.get("/api/geo/bounds").json()
    w, s, e, n = b["bbox"]
    for f in client.get("/api/geo/cells").json()["features"]:
        lon, lat = f["properties"]["center"]
        assert w <= lon <= e and s <= lat <= n


# ── 표준 적용 현황 (SCR-09) ───────────────────────────────────────────

def test_standards_distinguish_implemented_from_referenced(client):
    """표준 적용을 과장하지 않는다 — 구현과 인용을 구분해야 한다."""
    d = client.get("/api/standards").json()
    by_id = {s["id"]: s for s in d["standards"]}

    assert by_id["TTAK.KO-10.1331-Part3"]["status"] == "implemented"
    assert by_id["TTAK.KO-10.1398"]["status"] == "implemented"
    # 0580 은 BSM 파싱까지다. 메시지 규격 구현은 없다.
    assert by_id["TTAK.KO-06.0580"]["status"] == "partial"
    # Part2 는 설계 근거일 뿐 코드 산출물이 없다.
    assert by_id["TTAK.KO-10.1331-Part2"]["status"] == "reference"


def test_standards_evidence_paths_actually_work(client):
    """근거로 제시한 경로가 실제로 응답해야 한다.

    화면에서 눌렀을 때 404 가 뜨면 표준 준수 주장이 오히려 역효과다.
    """
    for s in client.get("/api/standards").json()["standards"]:
        if s["evidence"]:
            assert client.get(s["evidence"]).status_code == 200, s["id"]


# ── 인증 ──────────────────────────────────────────────────────────────

def test_reads_stay_open_without_auth(client):
    """조회는 공개 데이터다. 인증을 걸면 표준 준수를 확인할 방법도 함께 막힌다."""
    for path in ("/api/dashboard", "/api/cells", "/api/geo/cells",
                 "/api/inspections", "/api/standards",
                 "/ngsi-ld/v1/entities?type=TrafficEvent&limit=1",
                 "/ngsi-ld/v1/datasets"):
        assert client.get(path).status_code == 200, path


def test_write_requires_auth(client):
    """현장점검 등록은 시스템 판정을 사람이 번복하는 지점이라 신원이 남아야 한다."""
    r = client.post("/api/inspections",
                    json={"cell_key": "21:4", "findings": ["차선 마모"]})
    assert r.status_code == 401
    assert r.json()["status"] == 401

    r = client.patch("/api/inspections/1", json={"status": "resolved"})
    assert r.status_code == 401


def test_demo_login_issues_real_token(client):
    """테스트 로그인은 인증 우회가 아니라 데모 계정의 정상 발급이다."""
    b = client.post("/api/auth/demo-login").json()
    assert b["token_type"] == "Bearer"
    assert b["user"]["is_demo"] is True
    assert b["user"]["role"] == "inspector", "데모라고 권한을 더 주지 않는다"

    me = client.get("/api/auth/me",
                    headers={"Authorization": f"Bearer {b['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "demo"


def test_login_with_credentials(client):
    r = client.post("/api/auth/login",
                    json={"username": "admin", "password": "roadwatch2026!"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"


@pytest.mark.parametrize("body", [
    {"username": "admin", "password": "wrong"},
    {"username": "nobody", "password": "roadwatch2026!"},
])
def test_login_failures_do_not_leak_account_existence(client, body):
    """계정 존재 여부가 새어나가면 그 자체가 정보다 — 두 경우의 응답이 같아야 한다."""
    r = client.post("/api/auth/login", json=body)
    assert r.status_code == 401
    assert r.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."


def test_bad_token_rejected(client):
    for header in ("Bearer not-a-token", "Basic abc", "Bearer "):
        r = client.post("/api/inspections", headers={"Authorization": header},
                        json={"cell_key": "21:4", "findings": ["차선 마모"]})
        assert r.status_code == 401, header


def test_inspector_comes_from_token_not_client(client, restores_db, auth_headers):
    """클라이언트가 아무 이름이나 적게 두면 기록으로서 의미가 없다."""
    r = client.post("/api/inspections", headers=auth_headers, json={
        "cell_key": "21:4", "findings": ["노면 상태"],
        "inspector": "위조된이름",          # 무시돼야 한다
    })
    assert r.status_code == 201
    assert r.json()["inspector"] == "데모 사용자"


def test_password_hashing_roundtrip():
    """저장된 해시로 원문을 되돌릴 수 없고, 같은 비밀번호도 매번 다른 해시가 된다."""
    from app.auth import hash_password, verify_password

    h1 = hash_password("roadwatch2026")
    h2 = hash_password("roadwatch2026")
    assert h1 != h2, "salt 가 매번 달라야 한다"
    assert "roadwatch2026" not in h1
    assert verify_password("roadwatch2026", h1)
    assert not verify_password("roadwatch2027", h1)
    assert not verify_password("roadwatch2026", "깨진해시")


def test_auth_config_discloses_dev_secret(client):
    """개발 기본 비밀키를 쓰는 중이면 숨기지 않는다.

    이 값이면 토큰을 누구나 위조할 수 있다 — 공개 저장소에 있는 값이기 때문이다.
    """
    c = client.get("/api/auth/config").json()
    assert c["demo_login_available"] is True
    assert "dev_secret_in_use" in c


def test_empty_jwt_secret_env_falls_back(monkeypatch):
    """`JWT_SECRET=` 로 배포되는 .env.example 을 그대로 쓰면 빈 키가 된다.

    os.environ.get 의 기본값은 '키 없음'에만 걸리고 '빈 값'에는 안 걸리므로,
    빈 문자열을 미설정으로 취급해야 한다. 안 그러면 예제 파일을 복사한
    사람의 로그인이 통째로 깨진다.
    """
    import importlib

    from app import auth as auth_mod

    monkeypatch.setenv("JWT_SECRET", "")
    reloaded = importlib.reload(auth_mod)
    try:
        assert reloaded.SECRET == reloaded.DEV_SECRET
        token, _ = reloaded.issue_token({"username": "demo"})
        assert reloaded.decode_token(token)["sub"] == "demo"
    finally:
        monkeypatch.delenv("JWT_SECRET", raising=False)
        importlib.reload(auth_mod)


def test_report_never_flattens_metric_families(client, monkeypatch):
    """리포트 본문이 갈래를 다시 합치면 안 된다.

    화면(by_family)만 막고 리포트를 놓쳐서 "81.3%, 80.4%, 87.2%, 0.0%,
    100.0%, 93.9%" 처럼 한 줄로 늘어놓던 버그가 있었다. 이벤트 정의가 다른
    값을 나란히 세운 것이라 재현성 주장이 무너진다.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    b = client.post("/api/cells/21:4/report").json()

    # 모델에 넘기는 사실도, 사람이 읽는 본문도 갈래를 밝혀야 한다
    assert "[조인 갈래" in b["facts"] and "[BSM 갈래" in b["facts"]
    assert "비교하지 마세요" in b["facts"]
    assert "조인 갈래" in b["text"] and "BSM 갈래" in b["text"]
    assert "비교하지 않습니다" in b["text"]

    # 갈래 표기 없이 여러 비율이 연달아 나열되면 섞인 것이다
    import re
    flat = re.search(r"(\d+\.\d%,\s*){3,}", b["text"])
    assert flat is None, f"갈래 구분 없이 나열됐다: {flat.group() if flat else ''}"


def test_family_grouping_is_shared_not_duplicated():
    """화면과 리포트가 같은 판단을 쓰는지.

    각자 재구현하면 한 곳만 고쳐지고 나머지가 어긋난다 — 실제로 그랬다.
    """
    from app import families
    from app.routers import screens

    assert screens.families is families
    assert families.family_of(["low_speed"]) == families.JOINED
    assert families.family_of(["emergency"]) == families.BSM
    assert families.family_of([]) is None
    # 조인 갈래가 먼저 온다 — 기획서가 주장하는 재현성이 그쪽이다
    grouped = families.group([
        {"observation_count": 1, "measurable": True, "available_metrics": ["emergency"]},
        {"observation_count": 1, "measurable": True, "available_metrics": ["low_speed"]},
    ])
    assert list(grouped) == [families.JOINED, families.BSM]


# ── 시연 레이어 (SCR-03 · SCR-05) ─────────────────────────────────────

def test_normalization_toggle_collapses_map(client):
    """데모 하이라이트 — 토글 하나로 지도가 뒤덮였다가 3개만 남는다.

    숫자 15,585 가 바뀌는 것보다 지도가 비워지는 장면이 같은 사실을 훨씬
    강하게 전달한다. 그 장면이 실제로 성립하는지 고정한다.
    """
    before = client.get("/api/geo/normalization").json()
    after = client.get("/api/geo/normalization",
                       params={"normalized": True}).json()

    assert len(before["features"]) == 15_124
    assert len(after["features"]) == 3
    assert len(before["features"]) > len(after["features"]) * 1000

    # 남은 3건은 실제 센서 이상이다 — 정규화가 진짜를 지우지 않았다는 근거
    for f in after["features"]:
        assert f["properties"]["flags"] == ["snsr_trb_flg"]


def test_normalization_map_does_not_overclaim(client):
    """지도에 찍히는 수(15,124)와 실측 오판 수(15,588)가 다르다.

    차이 464 는 좌표가 유효하지 않은 BSM 레코드다. 화면이 '15,588개 마커'라고
    말하면 과장이므로, 응답이 두 수를 모두 싣고 차이를 설명해야 한다.
    """
    m = client.get("/api/geo/normalization").json()["metadata"]
    assert m["misjudged_total"] == 15_588
    assert m["mapped_raw"] == 15_124
    assert m["not_mappable"] == 464
    assert m["misjudged_total"] - m["mapped_raw"] == m["not_mappable"]
    assert "표시할 수 없어" in m["coverage_note"]


def test_trajectories_are_drawable_lines(client):
    """격자 사각형이 아니라 실제로 지나간 경로."""
    gj = client.get("/api/geo/trajectories").json()
    assert gj["features"], "궤적이 있어야 한다"
    for f in gj["features"]:
        assert f["geometry"]["type"] == "LineString"
        pts = f["geometry"]["coordinates"]
        assert len(pts) > 1, "선을 그리려면 점이 둘 이상이어야 한다"
        for lon, lat in pts:
            assert 126.9 < lon < 127.3 and 37.3 < lat < 37.5

    one = client.get("/api/geo/trajectories",
                     params={"session_id": "2022-05-16"}).json()
    assert len(one["features"]) == 1


def test_trajectory_covers_target_cell(client):
    """대표 구간 21:4 위를 실제로 지나가야 셀이 허공에 뜬 게 아님이 보인다."""
    cell = client.get("/api/geo/cells").json()
    box = next(f for f in cell["features"] if f["properties"]["cell_key"] == "21:4")
    ring = box["geometry"]["coordinates"][0]
    (w, s), (e, n) = ring[0], ring[2]

    traj = client.get("/api/geo/trajectories",
                      params={"session_id": "2022-05-16"}).json()
    pts = traj["features"][0]["geometry"]["coordinates"]
    inside = [p for p in pts if w <= p[0] <= e and s <= p[1] <= n]
    assert inside, "05-16 주행이 21:4 셀을 지나가야 한다"


def test_normalization_slim_keeps_what_matters(client):
    """15,124점에 속성을 실으면 응답이 3.9MB 다. 지도는 점만 찍으므로 뺀다.

    다만 정규화 후 3건은 '어떤 플래그가 남았는지'가 근거라서 slim 이어도 싣는다.
    """
    slim = client.get("/api/geo/normalization").json()
    full = client.get("/api/geo/normalization", params={"slim": False}).json()
    assert len(slim["features"]) == len(full["features"]) == 15_124
    assert slim["features"][0]["properties"] == {}
    assert full["features"][0]["properties"]["session_id"]

    after = client.get("/api/geo/normalization", params={"normalized": True}).json()
    for f in after["features"]:
        assert f["properties"]["flags"] == ["snsr_trb_flg"]
