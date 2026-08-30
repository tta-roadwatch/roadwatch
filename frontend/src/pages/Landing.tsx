import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Logo } from "../components/Logo";
import { num } from "../lib/format";

/** 랜딩 — 로그인 앞 공개 페이지.
 *
 * 심사자가 처음 만나는 화면이라 "무엇을 하는 서비스인가"가 3초 안에 읽혀야
 * 한다. 대시보드는 이미 업무를 아는 사람을 위한 화면이라 그 역할을 못 한다.
 *
 * 수치는 API 에서 받아 쓰되, 랜딩은 API 가 죽어도 떠야 하므로 실측 상수를
 * 폴백으로 둔다. 두 값은 같은 실행 결과이며 인수 기준이 지키는 수치다.
 */

/** API 실패 시 쓰는 값. docs/thresholds.md 와 인수 기준의 실측치와 같다. */
const FALLBACK = { records: 843_734, sessions: 8, cells: 89, candidates: 24 };

const NAV = [
  { href: "#problem", label: "왜 필요한가" },
  { href: "#how", label: "어떻게 찾는가" },
  { href: "#evidence", label: "실증 결과" },
  { href: "#faq", label: "자주 묻는 질문" },
];

const FEATURES = [
  {
    step: "01",
    title: "표준으로 데이터를 맞춥니다",
    body: "같은 TTA 표준 필드인데 수집 세션마다 코드 체계가 반대인 경우가 있습니다. 그대로 합치면 15,585건이 «비상정지»로 잘못 판정됩니다. 세션별 코드북을 적용해 바로잡습니다.",
    tag: "TTAK.KO-10.1331-Part4/R1",
  },
  {
    step: "02",
    title: "반복되는 구간만 골라냅니다",
    body: "한 번의 이상은 그날의 사정일 수 있습니다. 40m 격자로 나눠 서로 다른 주행에서 같은 자리가 반복해 걸리는지 봅니다. 우연과 구조적 문제를 가르는 기준입니다.",
    tag: "40m 격자 · 세션 교차",
  },
  {
    step: "03",
    title: "원인은 단정하지 않습니다",
    body: "데이터가 말해주는 것은 «여기서 반복해서 어려움을 겪었다»까지입니다. 차선이 지워졌는지 표지판이 가렸는지는 현장에서 확인할 일입니다. 점검 우선순위만 제안합니다.",
    tag: "현장점검 권고",
  },
  {
    step: "04",
    title: "조치 결과가 되돌아옵니다",
    body: "점검 결과를 등록하면 «도로 문제 아님»으로 후보에서 내릴 수 있습니다. 개선 후 같은 구간을 다시 측정해 효과를 확인합니다. 분석에서 끝나지 않습니다.",
    tag: "개선 전·후 비교",
  },
];

const FAQ = [
  {
    q: "자율주행 데이터로 도로 문제를 찾는다는 게 무슨 뜻인가요?",
    a: "자율주행차는 주행 중 위치·속도·상태를 초 단위로 기록합니다. 차선이 지워졌거나 시야가 가린 구간에서는 차가 속도를 줄이거나 이상 신호를 남깁니다. 서로 다른 날 주행한 차량들이 같은 자리에서 똑같이 걸린다면, 그건 그날의 사정이 아니라 도로 쪽 문제일 가능성이 큽니다. 그 지점을 찾아 현장점검을 권고합니다.",
  },
  {
    q: "사고가 난 곳을 표시하는 사고지도와 무엇이 다른가요?",
    a: "사고지도는 이미 사고가 난 뒤에 그려집니다. 이 서비스는 사고가 나기 전, 자율주행차가 «어려움을 겪은» 기록에서 출발합니다. 사고 통계에 잡히지 않는 구간도 반복성이 확인되면 후보가 됩니다.",
  },
  {
    q: "AI가 도로에 문제가 있다고 판단하는 건가요?",
    a: "아닙니다. 원인을 단정하지 않는 것이 이 서비스의 설계 원칙입니다. 시스템이 제공하는 것은 «서로 다른 주행에서 반복 검출되었다»는 관측 사실과 점검 우선순위 제안까지입니다. 확정은 도로관리자의 현장점검이 합니다. 점검 결과 도로 문제가 아니라고 판단되면 사람이 후보에서 내릴 수 있습니다.",
  },
  {
    q: "새로 센서를 설치해야 하나요? 도입 비용이 얼마나 드나요?",
    a: "설치할 것이 없습니다. 국토교통부 공간데이터마켓과 ITS 국가교통정보센터가 공개한 무료 개방데이터만 사용합니다. 표준 기반이라 특정 차량 제조사나 장비 업체에 종속되지 않습니다. 예산이 부족한 지자체도 같은 분석 결과를 얻습니다.",
  },
  {
    q: "분석 결과를 믿을 수 있나요?",
    a: "판단 근거를 전부 공개합니다. 임계값을 왜 그 숫자로 정했는지, 무엇을 시도했다 버렸는지까지 저장소에 기록했습니다. 분석 파이프라인은 명령 한 번으로 전 과정이 재현되며, 22개 인수 기준을 통과해야 배포됩니다. 결과가 마음에 들도록 숫자를 맞추지 않았습니다.",
  },
];

export function Landing() {
  const { data } = useApi(() => api.dashboard().catch(() => null), []);
  const s = data?.stats ?? FALLBACK;

  return (
    <div className="rw-lp">
      <LandingHeader />

      {/* ── Hero ── */}
      <section className="rw-lp-hero">
        <div className="rw-lp-hero__inner">
          <p className="rw-lp-eyebrow">자율주행 데이터 기반 도로환경 분석</p>
          <h1 className="rw-lp-hero__title">
            자율주행차가 반복해서 멈춘 도로,
            <br />
            사고가 나기 전에 찾아냅니다
          </h1>
          <p className="rw-lp-hero__lead">
            판교 제로시티 개방데이터 {num(s.records)}건을 분석해, 서로 다른 주행에서
            같은 자리가 반복해 걸린 구간을 도로관리자에게 알려드립니다.
          </p>
          <div className="rw-lp-hero__cta">
            <Link to="/dashboard" className="rw-lp-btn rw-lp-btn--primary">
              점검할 구간 보기 <span aria-hidden="true">→</span>
            </Link>
            <a href="#how" className="rw-lp-btn rw-lp-btn--ghost">
              어떻게 찾는지 보기
            </a>
          </div>
        </div>

        <dl className="rw-lp-stats">
          <Stat value={num(s.records)} label="분석한 주행 기록" />
          <Stat value={`${s.sessions}회`} label="서로 다른 주행 세션" />
          <Stat value={`${s.candidates}곳`} label="현장점검 권고 구간" highlight />
          <Stat value="98.8%" label="좌표 유효율" />
        </dl>
      </section>

      {/* ── 문제 제기 ── */}
      <section id="problem" className="rw-lp-section">
        <div className="rw-lp-section__head">
          <h2>지워진 차선은 사고가 나야 발견됩니다</h2>
          <p>그런데 자율주행차는 매일 그 길을 지나며 기록을 남기고 있습니다.</p>
        </div>

        <div className="rw-lp-problem">
          <div className="rw-lp-problem__now">
            <p className="rw-lp-label">지금</p>
            <ul>
              <li>민원이 들어와야 점검 대상이 됩니다</li>
              <li>사고 통계에 잡히지 않으면 우선순위에서 밀립니다</li>
              <li>도로는 길고 점검 인력과 예산은 한정돼 있습니다</li>
            </ul>
          </div>
          <div className="rw-lp-problem__arrow" aria-hidden="true">
            →
          </div>
          <div className="rw-lp-problem__next">
            <p className="rw-lp-label">이 서비스</p>
            <ul>
              <li>이미 공개된 주행 데이터에서 이상 구간을 찾습니다</li>
              <li>여러 주행에서 반복된 곳만 후보로 올립니다</li>
              <li>어디부터 나가볼지 순서를 제안합니다</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ── 작동 방식 ── */}
      <section id="how" className="rw-lp-section rw-lp-section--sunken">
        <div className="rw-lp-section__head">
          <h2>네 단계로 찾아냅니다</h2>
          <p>복잡한 자율주행 AI가 아니라, 표준과 반복성으로 판단합니다.</p>
        </div>

        <div className="rw-lp-features">
          {FEATURES.map((f) => (
            <article key={f.step} className="rw-lp-feature">
              <p className="rw-lp-feature__step">{f.step}</p>
              <h3>{f.title}</h3>
              <p className="rw-lp-feature__body">{f.body}</p>
              <p className="rw-lp-feature__tag">{f.tag}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── 실증 ── */}
      <section id="evidence" className="rw-lp-section">
        <div className="rw-lp-section__head">
          <h2>실제 데이터로 확인했습니다</h2>
          <p>가정이 아니라 공개된 주행 기록을 분석한 결과입니다.</p>
        </div>

        <div className="rw-lp-evidence">
          <div className="rw-lp-evidence__main">
            <p className="rw-lp-label">대왕판교로 · 3차로 · 제한속도 60km/h</p>
            <p className="rw-lp-evidence__rates">
              <span>81.3%</span>
              <em>2022-05-16</em>
              <span>87.2%</span>
              <em>2022-08-05</em>
            </p>
            <p className="rw-lp-evidence__note">
              약 3개월 간격의 서로 다른 두 주행에서 같은 격자가 비슷한 비율로
              걸렸습니다. 우연으로 보기 어려운 재현성입니다.
            </p>
          </div>

          <ul className="rw-lp-evidence__list">
            <li>
              <strong>{num(s.cells)}곳</strong>
              <span>분석한 40m 격자</span>
            </li>
            <li>
              <strong>{num(s.candidates)}곳</strong>
              <span>반복 검출된 점검 권고 구간</span>
            </li>
            <li>
              <strong>15,585건</strong>
              <span>표준 정규화로 바로잡은 오판</span>
            </li>
            <li>
              <strong>1,087개</strong>
              <span>매핑한 표준 도로망 링크</span>
            </li>
          </ul>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="rw-lp-cta">
        <h2>오늘 점검할 구간이 {s.candidates}곳 있습니다</h2>
        <p>
          로그인 없이 분석 결과를 둘러볼 수 있습니다. 현장점검 등록만 로그인이
          필요합니다.
        </p>
        <Link to="/dashboard" className="rw-lp-btn rw-lp-btn--onfill">
          점검할 구간 보기 <span aria-hidden="true">→</span>
        </Link>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="rw-lp-section">
        <div className="rw-lp-section__head">
          <h2>자주 묻는 질문</h2>
          <p>서비스에 대해 궁금하신 점을 확인해 보세요.</p>
        </div>
        <div className="rw-lp-faq">
          {FAQ.map((item, i) => (
            <FaqItem key={item.q} {...item} defaultOpen={i === 0} />
          ))}
        </div>
      </section>

      <LandingFooter />
    </div>
  );
}

function Stat({
  value,
  label,
  highlight = false,
}: {
  value: string;
  label: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rw-lp-stat${highlight ? " rw-lp-stat--hl" : ""}`}>
      <dt className="rw-lp-stat__label">{label}</dt>
      <dd className="rw-lp-stat__value">{value}</dd>
    </div>
  );
}

/** 아코디언. details/summary 를 쓰면 키보드 조작과 스크린리더 대응이
 * 브라우저 기본으로 따라온다 — 직접 만들면 그걸 다시 구현해야 한다. */
function FaqItem({
  q,
  a,
  defaultOpen,
}: {
  q: string;
  a: string;
  defaultOpen: boolean;
}) {
  return (
    <details className="rw-lp-faq__item" open={defaultOpen}>
      <summary>
        <span>{q}</span>
        <span className="rw-lp-faq__mark" aria-hidden="true" />
      </summary>
      <p>{a}</p>
    </details>
  );
}

function LandingHeader() {
  // 스크롤하면 헤더에 경계선을 넣어 본문과 분리한다. 처음엔 히어로와
  // 이어져 보이는 편이 낫다.
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`rw-lp-header${scrolled ? " is-scrolled" : ""}`}>
      <div className="rw-lp-header__inner">
        <Link to="/" className="rw-lp-brand">
          <Logo size={30} />
          <span>자율주행 취약도로 탐지</span>
        </Link>

        <nav className="rw-lp-nav" aria-label="페이지 안내">
          {NAV.map((n) => (
            <a key={n.href} href={n.href}>
              {n.label}
            </a>
          ))}
        </nav>

        <Link to="/dashboard" className="rw-lp-btn rw-lp-btn--sm">
          시작하기
        </Link>
      </div>
    </header>
  );
}

function LandingFooter() {
  return (
    <footer className="rw-lp-footer">
      <div className="rw-lp-footer__inner">
        <p className="rw-lp-footer__brand">자율주행 취약도로 탐지 · RoadWatch</p>
        <p>
          2026 ICT 표준 챌린지 공모전 출품작 · 판교 제로시티 개방데이터 기반
        </p>
        <p className="rw-lp-footer__src">
          데이터 출처 — 국토교통부 공간정보 오픈플랫폼 공간데이터마켓 ·
          ITS 국가교통정보센터 전국표준노드링크
        </p>
      </div>
    </footer>
  );
}
