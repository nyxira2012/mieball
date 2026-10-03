import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

/* P2 单测配置：测试文件放 frontend/tests/（src 之外）——
   避开 uni 编译器对 src 的扫描，tsconfig include 也只盖 src，vue-tsc 不重复检查测试文件；
   vitest 自带 esbuild 直接吃 TS。别名 '@' 与 src 内一致。 */
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
