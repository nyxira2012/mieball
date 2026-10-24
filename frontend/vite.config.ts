import { defineConfig, type Plugin } from "vite";
import uni from "@dcloudio/vite-plugin-uni";

import fs from "node:fs";
import path from "node:path";

// https://vitejs.dev/config/

// uni-h5 开发服务器会把 vite 自带的 public 中间件整个替换成「只服务 src/static」
// 的版本（见 @dcloudio/uni-h5-vite configureServer/static.js），其余路径一律回退
// index.html——而 /cosmetics/{编号}.png|.webp 这套根路径资产约定（前后端同口径，
// 后端 asset_url 直拼同款路径）在开发期因此全部落空、圆章只出素底。这里把
// public/ 的直出补回来：只挂 dev 服务器，build 期 vite 原生拷贝 publicDir 不经此路。
const DEV_MIME: Record<string, string> = {
  ".png": "image/png",
  ".webp": "image/webp",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".json": "application/json",
};

function servePublicInDev(): Plugin {
  const root = path.resolve(__dirname, "public");
  return {
    name: "mieball:serve-public-in-dev",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = decodeURIComponent((req.url ?? "").split("?")[0]);
        const type = DEV_MIME[path.extname(url)];
        if (!type) return next();
        const file = path.join(root, url);
        // startsWith 兜路径穿越（url 带 ../ 时 join 会跳出 root）
        if (!file.startsWith(root + path.sep)) return next();
        if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return next();
        res.setHeader("Content-Type", type);
        res.setHeader("Cache-Control", "no-cache");
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

// 小程序包剔重：字体在小程序端由 uni 编译自动内嵌 base64 进 wxss，
// src/static/fonts 的目录拷贝件在小程序全包零引用（H5 端仍靠它渲染，源目录不动），
// 剔掉只为压主包体积（微信主包上限 2MB）。
function pruneMpDupFonts(): Plugin {
  return {
    name: "mieball:prune-mp-dup-fonts",
    apply: "build",
    closeBundle() {
      if (process.env.UNI_PLATFORM !== "mp-weixin") return;
      for (const mode of ["build", "dev"]) {
        const dir = path.resolve(__dirname, `dist/${mode}/mp-weixin/static/fonts`);
        if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true });
      }
    },
  };
}

export default defineConfig({
  publicDir: path.resolve(__dirname, "public"),
  plugins: [uni(), servePublicInDev(), pruneMpDupFonts()],
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
