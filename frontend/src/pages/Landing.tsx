import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Logo } from "../components/Logo";
import { Reveal } from "../components/Reveal";
import { RoadIllustration } from "../components/RoadIllustration";
import { num } from "../lib/format";
import { useCountUp, useInView } from "../lib/reveal";

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

/** Hero 배경 사진. public/hero.jpg 를 두면 자동으로 적용되고, 없으면
 * 그라데이션 배경이 그대로 쓰인다 — 사진이 준비되지 않아도 화면은 완성이다.
 *
 * 사진 위 글자 대비는 CSS 오버레이가 고정하므로, 사진의 밝기와 무관하게
 * WCAG 기준을 지킨다. 다만 초점이 가운데 몰린 사진은 글자와 겹치므로
 * 여백이 있는 구도를 쓰는 편이 낫다. */
const HERO_PHOTO = "/hero.jpg";

const NAV = [
  { href: "#problem", label: "왜 필요한가" },
  { href: "#how", label: "어떻게 찾는가" },
  { href: "#standards", label: "표준 적용" },
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

/** 랜딩에 세우는 표준 목록.
 *
 * 백엔드 /api/standards 와 같은 내용이되 여기서는 정적으로 둔다. 랜딩은 API 가
 * 죽어도 떠야 하고, 이 목록은 자주 바뀌지 않는다. 바뀌면 양쪽을 함께 고친다.
 *
 * 구현·부분 구현·설계 참조를 구분하는 것이 핵심이다. 다섯 건을 모두 «적용»
 * 이라 적으면 코드를 열어본 심사자에게 곧바로 들통난다. 어디까지 했는지
 * 밝히는 편이 신뢰를 얻는다.
 */
const STANDARDS = [
  {
    id: "TTAK.KO-10.1331-Part4/R1",
    name: "스마트시티 데이터허브 — 데이터 모델",
    role: "분석 결과를 NGSI-LD 정규 표현법과 TrafficEvent 모델로 제공합니다.",
    status: "구현",
    tone: "done" as const,
  },
  {
    id: "TTAK.KO-10.1331-Part3",
    name: "인터페이스 및 프로토콜",
    role: "조회 API를 6장 인터페이스 명세와 5장 응답 코드 체계에 맞췄습니다.",
    status: "구현",
    tone: "done" as const,
  },
  {
    id: "TTAK.KO-10.1398",
    name: "스마트시티 데이터세트 메타데이터",
    role: "주행 세션 8건을 DCAT 기반 데이터세트로 등록하고 품질 문제까지 드러냅니다.",
    status: "구현",
    tone: "done" as const,
  },
  {
    id: "TTAK.KO-06.0580",
    name: "이동통신망 기반 V2N 정보 연계",
    role: "BSM 원본 필드를 실제로 파싱해 적재합니다. 메시지 규격 자체의 인코더는 구현하지 않았습니다.",
    status: "부분 구현",
    tone: "partial" as const,
  },
  {
    id: "TTAK.KO-10.1331-Part2",
    name: "참조구조",
    role: "수집–정규화–저장–제공 계층 분리의 설계 근거로 삼았습니다.",
    status: "설계 참조",
    tone: "ref" as const,
  },
];

/** 랜딩에 싣는 실제 응답. GET /ngsi-ld/v1/entities/... 를 그대로 가져왔다. */
const NGSI_SAMPLE = `{
  "id": "urn:ngsi-ld:TrafficEvent:roadwatch:21:4",
  "type": "TrafficEvent",
  "name":     { "type": "Property", "value": "대왕판교로" },
  "location": { "type": "GeoProperty",
                "value": { "type": "Point",
                           "coordinates": [127.1047865, 37.4035015] } },
  "category": { "type": "Property", "value": "roadCondition" },
  "sessionCount": { "type": "Property", "value": 6 },
  "@context": [ "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld" ]
}`;

const FAQ = [
  {
    q: "자율주행 데이터로 도로 문제를 찾는다는 게 무슨 뜻인가요?",
    a: "자율주행차는 주행 중 위치·속도·상태를 초 단위로 기록합니다. 차선이 지워졌거나 시야가 가린 구간에서는 차가 속도를 줄이거나 이상 신호를 남깁니다. 서로 다른 날 주행한 차량들이 같은 자리에서 똑같이 걸린다면, 그건 그날의 사정이 아니라 도로 쪽 문제일 가능성이 큽니다. 그 지점을 찾아 현장점검을 권고합니다.",
  },
  {
    q: "사고가 난 곳을 표시하는 사고지도와 무엇이 다른가요?",
    a: "사고지도는 이미 사고가 난 뒤에 그려집니다. RoadWatch는 사고가 나기 전, 자율주행차가 «어려움을 겪은» 기록에서 출발합니다. 사고 통계에 잡히지 않는 구간도 반복성이 확인되면 후보가 됩니다.",
  },
  {
    q: "AI가 도로에 문제가 있다고 판단하는 건가요?",
    a: "아닙니다. 원인을 단정하지 않는 것이 RoadWatch의 설계 원칙입니다. 시스템이 제공하는 것은 «서로 다른 주행에서 반복 검출되었다»는 관측 사실과 점검 우선순위 제안까지입니다. 확정은 도로관리자의 현장점검이 합니다. 점검 결과 도로 문제가 아니라고 판단되면 사람이 후보에서 내릴 수 있습니다.",
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
  const heroPhoto = useOptionalImage(HERO_PHOTO);

  return (
    <div className="rw-lp">
      <LandingHeader />

      {/* ── Hero ── */}
      <section
        className={`rw-lp-hero${heroPhoto ? " rw-lp-hero--photo" : ""}`}
        style={
          heroPhoto
            ? ({ "--rw-lp-hero-photo": `url("${HERO_PHOTO}")` } as React.CSSProperties)
            : undefined
        }
      >
        <div className="rw-lp-hero__inner rw-lp-hero__inner--enter">
          <p className="rw-lp-eyebrow">TTA 표준 기반 자율주행 도로환경 분석</p>
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

      </section>

      {/* 통계는 Hero 밖 흰 영역에 둔다. 배경 사진 경계에 걸쳐 있으면
          사진도 카드도 어중간해 보이고, Hero 안에 다 넣으면 한 화면에
          여섯 덩어리가 쌓여 답답하다. */}
      <section className="rw-lp-statband">
        <StatBar
          records={s.records}
          sessions={s.sessions}
          candidates={s.candidates}
        />
      </section>

      {/* ── 문제 제기 ── */}
      <section id="problem" className="rw-lp-section">
        <Reveal className="rw-lp-section__head">
          <h2>지워진 차선은 사고가 나야 발견됩니다</h2>
          <p>그런데 자율주행차는 매일 그 길을 지나며 기록을 남기고 있습니다.</p>
        </Reveal>

        <Reveal className="rw-lp-problem" delay={80}>
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
            <p className="rw-lp-label">RoadWatch</p>
            <ul>
              <li>이미 공개된 주행 데이터에서 이상 구간을 찾습니다</li>
              <li>여러 주행에서 반복된 곳만 후보로 올립니다</li>
              <li>어디부터 나가볼지 순서를 제안합니다</li>
            </ul>
          </div>
        </Reveal>

        {/* 앞 문단이 말한 «매일 그 길을 지나며 기록을 남긴다»를 그림으로
            잇는다. Hero 에 두면 배경 사진의 도로와 겹쳐 충돌했다. */}
        <Reveal as="figure" className="rw-lp-shot rw-lp-shot--illust" delay={120}>
          <RoadIllustration />
          <figcaption>
            서로 다른 날의 세 주행에서 같은 위치가 반복 검출되면, 도로환경
            요인을 점검할 후보가 됩니다.
          </figcaption>
        </Reveal>
      </section>

      {/* ── 작동 방식 ── */}
      <section id="how" className="rw-lp-section rw-lp-section--sunken">
        <Reveal className="rw-lp-section__head">
          <h2>네 단계로 찾아냅니다</h2>
          <p>복잡한 자율주행 AI가 아니라, 표준과 반복성으로 판단합니다.</p>
        </Reveal>

        <div className="rw-lp-features">
          {FEATURES.map((f, i) => (
            <Reveal
              as="article"
              key={f.step}
              className="rw-lp-feature"
              delay={(i % 2) * 80}
            >
              <p className="rw-lp-feature__step">{f.step}</p>
              <h3>{f.title}</h3>
              <p className="rw-lp-feature__body">{f.body}</p>
              <p className="rw-lp-feature__tag">{f.tag}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── 정규화 전·후 ── */}
      <section className="rw-lp-section">
        <Reveal className="rw-lp-section__head">
          <h2>표준을 지키지 않으면 이렇게 됩니다</h2>
          <p>
            같은 데이터, 같은 지도입니다. 코드 체계를 맞췄는지 아닌지의 차이입니다.
          </p>
        </Reveal>

        <div className="rw-lp-compare">
          <Reveal as="figure">
            <img
              src="/shots/norm-before.jpg"
              alt="정규화 전 지도. 주행 경로 전 구간이 비상정지 표시로 굵게 칠해져 있다."
              width={1680}
              height={570}
              loading="lazy"
            />
            <figcaption>
              <span className="rw-lp-compare__tag rw-lp-compare__tag--wrong">
                정규화 없음
              </span>
              주행 전 구간이 «비상정지»로 판정됩니다. 차가 멈춘 적이 없는데도
              15,588건이 이상으로 잡힙니다.
            </figcaption>
          </Reveal>

          <Reveal as="figure" delay={120}>
            <img
              src="/shots/norm-after.jpg"
              alt="정규화 후 지도. 표시가 세 개만 남아 있다."
              width={1680}
              height={570}
              loading="lazy"
            />
            <figcaption>
              <span className="rw-lp-compare__tag">표준 정규화 적용</span>
              세션별 코드북을 적용하면 실제 센서 이상 3건만 남습니다.
              오판 15,585건이 사라집니다.
            </figcaption>
          </Reveal>
        </div>
      </section>

      {/* ── 표준 적용 ──
          앞 섹션이 «표준을 안 지키면 이렇게 된다»를 보였으니, 여기서
          «그래서 어떤 표준을 어떻게 썼는가»로 잇는다. 2026 ICT 표준
          챌린지 출품작이라 이 부분이 랜딩에서 읽히지 않으면 안 된다. */}
      <section id="standards" className="rw-lp-section rw-lp-section--sunken">
        <Reveal className="rw-lp-section__head">
          <h2>TTA 표준을 이렇게 적용했습니다</h2>
          <p>
            어디까지 구현했고 어디부터가 설계 참조인지 구분해 적었습니다.
          </p>
        </Reveal>

        <div className="rw-lp-std">
          <Reveal as="ul" className="rw-lp-std__list">
            {STANDARDS.map((st) => (
              <li key={st.id}>
                <div className="rw-lp-std__head">
                  <code>{st.id}</code>
                  <span className={`rw-lp-std__tag rw-lp-std__tag--${st.tone}`}>
                    {st.status}
                  </span>
                </div>
                <p className="rw-lp-std__name">{st.name}</p>
                <p className="rw-lp-std__role">{st.role}</p>
              </li>
            ))}
          </Reveal>

          <Reveal className="rw-lp-std__sample" delay={120}>
            <p className="rw-lp-label">실제 응답</p>
            <p className="rw-lp-std__path">
              <code>GET /ngsi-ld/v1/entities/…</code>
            </p>
            <pre>
              <code>{NGSI_SAMPLE}</code>
            </pre>
            <p className="rw-lp-std__note">
              속성마다 종류(<code>Property</code> · <code>GeoProperty</code>)를
              밝히는 NGSI-LD 정규 표현법입니다. 조회 API는 로그인 없이 열려
              있어 표준 준수를 직접 확인하실 수 있습니다.
            </p>
          </Reveal>
        </div>

        <Reveal className="rw-lp-std__foot" delay={200}>
          <p>
            공간 연계는 지정 134선에 대응 표준이 없어 ITS 국가교통정보센터의
            전국표준노드링크로 구현했습니다. TTA 표준이 아니므로 위 목록에
            넣지 않았습니다.
          </p>
        </Reveal>
      </section>

      {/* ── 실증 ── */}
      <section id="evidence" className="rw-lp-section">
        <Reveal className="rw-lp-section__head">
          <h2>실제 데이터로 확인했습니다</h2>
          <p>가정이 아니라 공개된 주행 기록을 분석한 결과입니다.</p>
        </Reveal>

        <div className="rw-lp-evidence">
          <Reveal className="rw-lp-evidence__main">
            <p className="rw-lp-label">대왕판교로 · 3차로 · 제한속도 60km/h</p>

            {/* 두 값을 가로로 붙여두면 어느 날짜의 수치인지 읽히지 않는다.
                세로로 세우고 막대를 붙여 «비슷하다»가 눈에 보이게 한다 —
                이 섹션이 말하려는 것이 재현성이기 때문이다. */}
            <div className="rw-lp-evidence__rates">
              <RateDial date="2022-05-16" value={81.3} counts="52 / 64초" />
              <RateDial date="2022-08-05" value={87.2} counts="116 / 133초" />
            </div>

            <p className="rw-lp-evidence__note">
              약 3개월 간격의 서로 다른 두 주행에서 같은 격자가 비슷한 비율로
              걸렸습니다. 우연으로 보기 어려운 재현성입니다.
            </p>
          </Reveal>

          <Reveal as="ul" className="rw-lp-evidence__list" delay={120}>
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
          </Reveal>
        </div>
      </section>

      {/* ── CTA ── */}
      <Reveal as="section" className="rw-lp-cta">
        <h2>오늘 점검할 구간이 {s.candidates}곳 있습니다</h2>
        <p>
          로그인 없이 분석 결과를 둘러볼 수 있습니다. 현장점검 등록만 로그인이
          필요합니다.
        </p>
        <Link to="/dashboard" className="rw-lp-btn rw-lp-btn--onfill">
          점검할 구간 보기 <span aria-hidden="true">→</span>
        </Link>
      </Reveal>

      {/* ── FAQ ── */}
      <section id="faq" className="rw-lp-section">
        <Reveal className="rw-lp-section__head">
          <h2>자주 묻는 질문</h2>
          <p>서비스에 대해 궁금하신 점을 확인해 보세요.</p>
        </Reveal>
        <Reveal className="rw-lp-faq">
          {FAQ.map((item, i) => (
            <FaqItem key={item.q} {...item} defaultOpen={i === 0} />
          ))}
        </Reveal>
      </section>

      <LandingFooter />
    </div>
  );
}

/** 지표 4개. 시야에 들어오면 숫자가 올라간다.
 *
 * 카운트업은 이 묶음이 보일 때 한 번만 돈다 — 카드마다 따로 관찰하면
 * 숫자들이 제각각 시작해 산만하다. */
function StatBar({
  records,
  sessions,
  candidates,
}: {
  records: number;
  sessions: number;
  candidates: number;
}) {
  const { ref, inView } = useInView<HTMLDListElement>("-40px");
  const r = useCountUp(records, inView);
  const se = useCountUp(sessions, inView, 700);
  const c = useCountUp(candidates, inView, 900);

  return (
    <dl ref={ref} className={`rw-lp-stats rw-reveal${inView ? " is-in" : ""}`}>
      <Stat value={num(r)} label="분석한 주행 기록" />
      <Stat value={`${se}회`} label="서로 다른 주행 세션" />
      <Stat value={`${c}곳`} label="현장점검 권고 구간" highlight />
      <Stat value="98.8%" label="좌표 유효율" />
    </dl>
  );
}

/** 한 주행의 이벤트율. 원이 시야에 들어올 때 채워진다.
 *
 * 원형은 각도 비교라 막대보다 정밀도가 떨어진다 — 81.3% 와 87.2% 의 차이는
 * 21도에 불과하다. 다만 이 카드가 말하려는 건 «둘 다 비슷하게 높다»는
 * 인상이고, 나란히 놓인 두 원이 비슷하게 차 있는 모습이 그걸 전한다.
 * 정확한 값은 원 안에 글자로 둔다.
 */
function RateDial({
  date,
  value,
  counts,
}: {
  date: string;
  value: number;
  counts: string;
}) {
  const { ref, inView } = useInView<HTMLDivElement>("-40px");
  const R = 52;
  const C = 2 * Math.PI * R;

  return (
    <div className="rw-lp-dial" ref={ref}>
      <svg viewBox="0 0 120 120" className="rw-lp-dial__svg" aria-hidden="true">
        <circle
          cx="60"
          cy="60"
          r={R}
          fill="none"
          stroke="var(--rw-surface-sunken)"
          strokeWidth="13"
        />
        <circle
          cx="60"
          cy="60"
          r={R}
          fill="none"
          /* 채움은 밝은 주황(warning-30). 글자용 warning-50 은 갈색에 가까워
             큰 면적에 쓰면 칙칙하다. 원 안 숫자는 대비를 위해 그대로 둔다. */
          stroke="var(--rw-intermittent)"
          strokeWidth="13"
          strokeLinecap="round"
          strokeDasharray={C}
          /* 12시 방향에서 시작하도록 90도 돌린다 */
          transform="rotate(-90 60 60)"
          style={{ strokeDashoffset: inView ? C * (1 - value / 100) : C }}
        />
      </svg>

      <div className="rw-lp-dial__center">
        <span className="rw-lp-dial__value">{value}%</span>
      </div>

      <p className="rw-lp-dial__date">{date}</p>
      <p className="rw-lp-dial__counts">{counts}</p>
    </div>
  );
}

/** 이미지가 실제로 있는지 확인한다.
 *
 * 파일이 없을 때 깨진 이미지나 빈 영역이 남으면 안 되므로, 로드에 성공한
 * 뒤에야 배경으로 쓴다. 사진을 아직 준비하지 않았어도 화면은 완성된 상태로
 * 보인다. */
function useOptionalImage(src: string): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    let alive = true;
    const img = new Image();
    img.onload = () => alive && setOk(true);
    img.onerror = () => alive && setOk(false);
    img.src = src;
    return () => {
      alive = false;
    };
  }, [src]);
  return ok;
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
      {/* 숫자가 바뀌는 동안 스크린리더가 매 프레임 읽지 않도록 막는다 */}
      <dd className="rw-lp-stat__value" aria-live="off">
        {value}
      </dd>
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
          <span>RoadWatch</span>
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
        <p className="rw-lp-footer__brand">RoadWatch · 자율주행 취약도로 탐지</p>
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
