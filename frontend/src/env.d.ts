/// <reference types="vite/client" />

/** 素材基地址（cardbg ASSET_BASE 的 H5 分支吃它）：H5 同域直引不设即为空串 */
interface ImportMetaEnv {
  readonly VITE_ASSET_BASE?: string;
  /** MP 专属镜像键（接口/素材基地址）：只被 #ifdef MP-WEIXIN 分支读取，.env 建档不改 H5 读法 */
  readonly VITE_MP_API_BASE?: string;
  readonly VITE_MP_ASSET_BASE?: string;
}

declare module "*.vue" {
  import { DefineComponent } from "vue";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/ban-types
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
