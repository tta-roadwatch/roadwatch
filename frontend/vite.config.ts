import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
