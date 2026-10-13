import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";
import path from "node:path";

// 微信登录走查专用临时配置（用完即删）：端口 12549 · /api 代理到假通道测试后端 16589
export default defineConfig({
  publicDir: path.resolve(__dirname, "public"),
  plugins: [uni()],
  server: {
    port: 12549,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:16589",
        changeOrigin: true,
      },
    },
  },
});
