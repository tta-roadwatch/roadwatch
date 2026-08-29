/** 서비스 로고.
 *
 * 원본(road.png)은 5768px · 15MB 라 그대로 서빙하면 첫 화면이 그것 하나로
 * 느려진다. 표시 크기의 4배인 256px 로 줄여 public 에 두고 이걸 쓴다.
 * 이미지가 자체 배경(파랑)을 갖고 있어 뒤에 색을 깔지 않는다.
 */
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <img
      className="rw-logo"
      src="/logo.png"
      width={size}
      height={size}
      alt=""
      /* 옆에 서비스명이 글자로 있으므로 로고는 장식이다 —
         alt 를 비워 스크린리더가 같은 말을 두 번 읽지 않게 한다. */
      aria-hidden="true"
    />
  );
}
