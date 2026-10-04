import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [uni()],
  server: {
    // 端口约定：前端 12543 · 后端 16588（见 AGENTS.md）
    port: 12543,
    proxy: {
      // 开发期前端只请求相对路径 /api/...，由这里转发给本地后端
      "/api": {
        target: "http://127.0.0.1:16588",
        changeOrigin: true,
      },
    },
  },
});
