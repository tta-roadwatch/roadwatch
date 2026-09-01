import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import type { CitizenReport } from "../api/types";
import { Alert } from "../components/Alert";
import { Card } from "../components/Card";
import { Logo } from "../components/Logo";
import { ReportMap } from "../components/ReportMap";
import { ErrorState, Loading } from "../components/States";
import { day } from "../lib/format";

type Picked = { lat: number; lon: number } | null;

/** 시민 도로 불편 제보.
 *
 * 로그인 밖에 둔다. 점검 등록은 시스템 판정을 사람이 뒤집는 행정 행위라
 * 누가 했는지 남아야 하지만, 민원 접수는 판정을 바꾸지 않는다. 공공 민원
 * 창구를 로그인 뒤에 두지 않는 것과 같다.
 *
 * 묻는 것은 «무엇을 보셨나»이지 «여기가 위험한가»가 아니다. 그래서 항목이
 * 전부 관측한 사실이고, 위험도를 고르는 자리가 없다. 시민이 위험을
 * 판정하면 이 서비스가 원인을 단정하지 않는다는 원칙이 무너진다.
 */
export function ReportForm() {
  const [picked, setPicked] = useState<Picked>(null);
  const [category, setCategory] = useState<string>("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState<CitizenReport | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi(
    () => api.reportCategories(),
    [],
  );

  useEffect(() => {
    if (data && !category) setCategory(data.categories[0]);
  }, [data, category]);

  if (loading) return <Loading label="제보 화면을 준비하는 중입니다" />;
  if (error || !data) {
    return <ErrorState message={error ?? "불러오지 못했습니다"} onRetry={reload} />;
  }

  async function submit() {
    if (!picked || !category) return;
    setSending(true);
    setFailed(null);
    try {
      const r = await api.createReport({
        lat: picked.lat,
        lon: picked.lon,
        category,
        note: note.trim() || null,
      });
      setDone(r);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "접수하지 못했습니다");
    } finally {
      setSending(false);
    }
  }

  function again() {
    setDone(null);
    setPicked(null);
    setNote("");
    setFailed(null);
  }

  return (
    <div className="rw-public">
      <header className="rw-public__head">
        <Link to="/" className="rw-public__brand">
          <Logo size={28} />
          <span>RoadWatch</span>
        </Link>
        <Link to="/login" className="rw-btn rw-btn--ghost rw-btn--sm">
          도로관리자 로그인
        </Link>
      </header>

      <main className="rw-public__body">
        <h1 className="rw-public__title">도로 불편 제보</h1>
        <p className="rw-public__lead">
          자율주행 데이터로는 알기 어려운 현장 사정을 알려주세요. 접수된 제보는
          도로관리자가 현장점검 순서를 정할 때 참고합니다.
        </p>

        {done ? (
          <Card
            title="접수되었습니다"
            footer="제보는 취약구간 판정에 사용하지 않습니다. 현장점검 순서를 정할 때 참고하는 자료입니다."
          >
            <div className="rw-dl">
              <dt>접수번호</dt>
              <dd>{done.id}</dd>
              <dt>항목</dt>
              <dd>{done.category}</dd>
              <dt>위치</dt>
              <dd>
                {done.road_name ?? `${done.lat.toFixed(5)}, ${done.lon.toFixed(5)}`}
              </dd>
              <dt>접수일</dt>
              <dd>{day(done.created_at)}</dd>
            </div>
            <p className="rw-note">{done.match_notice}</p>
            <button type="button" className="rw-btn rw-btn--secondary" onClick={again}>
              다른 곳 제보하기
            </button>
          </Card>
        ) : (
          <>
            <Card title="① 위치를 눌러 주세요">
              <ReportMap picked={picked} onPick={setPicked} />
              <p className="rw-meta">
                {picked
                  ? `선택한 위치 ${picked.lat.toFixed(5)}, ${picked.lon.toFixed(5)}`
                  : "지도를 눌러 불편했던 곳을 짚어 주세요."}
              </p>
            </Card>

            <Card title="② 무엇을 보셨나요?">
              <div className="rw-choices" role="radiogroup" aria-label="제보 항목">
                {data.categories.map((c) => (
                  <label key={c} className="rw-choice">
                    <input
                      type="radio"
                      name="category"
                      value={c}
                      checked={category === c}
                      onChange={() => setCategory(c)}
                    />
                    <span>{c}</span>
                  </label>
                ))}
              </div>

              <div className="rw-field">
                <label className="rw-label" htmlFor="note">
                  덧붙일 말 (선택)
                </label>
                <input
                  id="note"
                  className="rw-input"
                  maxLength={200}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="예) 비 오는 날 특히 안 보입니다"
                />
              </div>
            </Card>

            {failed && (
              <Alert severity="caution" title="접수하지 못했습니다">
                {failed}
              </Alert>
            )}

            <button
              type="button"
              className="rw-btn rw-btn--primary rw-btn--block"
              disabled={!picked || !category || sending}
              onClick={submit}
            >
              {sending ? "접수하는 중…" : "제보하기"}
            </button>
            {!picked && (
              <p className="rw-meta">위치를 먼저 지정해 주세요.</p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
