import { createSSRApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { initBlackbox } from "@/utils/blackbox";

export function createApp() {
  const app = createSSRApp(App);
  app.use(createPinia());
  // 黑匣子先于一切页面装配（6.1 §4.6）：挂路由拦截器 + 记 launch
  initBlackbox();
  return {
    app,
  };
}
