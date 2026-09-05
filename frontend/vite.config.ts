import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // maplibre-gl 은 워커를 별도 파일로 싣는데, vite 의 의존성 사전번들이
  // 그 워커를 함께 옮기지 못해 개발 서버에서 404 가 난다. 사전번들에서
  // 빼면 소스 그대로 불러 워커도 따라온다. (프로덕션 빌드는 영향 없음)
  optimizeDeps: { exclude: ["maplibre-gl"] },
  server: {
    // 컨테이너 밖(호스트 브라우저)에서 접근해야 하므로 0.0.0.0 에 바인딩한다.
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // compose 가 ./frontend 를 바인드 마운트한다. macOS 바인드 마운트에서는
    // inotify 가 전달되지 않아 폴링하지 않으면 HMR 이 죽는다.
    watch: { usePolling: true, interval: 300 },
  },
});
