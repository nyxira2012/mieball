/// <reference types="vite/client" />

/** 素材基地址（cardbg ASSET_BASE 吃它）：H5 同域直引不设即为空串；小程序编译期注入线上域名 */
interface ImportMetaEnv {
  readonly VITE_ASSET_BASE?: string
}

declare module '*.vue' {
  import { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/ban-types
  const component: DefineComponent<{}, {}, any>
  export default component
}
