<template>
  <PageShell>
    <!-- 装扮页（重造）：顶部大试穿框 + 选头像/选卡背两栏 + 昵称/手机号行 + 一颗保存钮。
         点任一件（含带锁荣誉款）即时试穿；保存把关在按钮——含未解锁件则钮灰、
         文字报差什么（真值在服务端，灰钮只是前置提示）。 -->
    <!-- 点空白收键盘：原生监听直挂包裹层元素（uni 内建 view 的 @click 在 slot 根节点位
         不落地——login 页同款问题先行实证，见 login.vue 注释） -->
    <view ref="tapRoot" class="tap-blur">
      <BackRow />

      <view class="stag">
        <view class="kicker">Dress Up</view>
        <view class="brand">装<text class="bem">扮</text></view>
      </view>

      <!-- 三态：加载占位不白屏 / 目录拉不到提示重试可退回（返回行常驻）/ 整页 -->
      <EmptyBox v-if="loadErr" class="state">
        装扮册子没拉到，稍后再试
        <view class="retry">
          <AppButton
            variant="ghost"
            size="sm"
            :disabled="busyLoad"
            @click="load"
            >{{ busyLoad ? "拉取中…" : "重试" }}</AppButton
          >
        </view>
      </EmptyBox>
      <EmptyBox v-else-if="!page" class="state">装扮加载中…</EmptyBox>

      <template v-else>
        <!-- 大试穿框：全站最大形象展示位（卡背 'd' 档试穿取景 + 140 圆章 +
             名片数据沿用——名字/战绩行与我的页同源 me） -->
        <view class="tryon cbd-host">
          <CardBackdrop
            :cid="sel.back"
            mode="d"
            :fx="itemOf(sel.back)?.fx"
            :fy="itemOf(sel.back)?.fy"
          />
          <view class="tryon-row">
            <AvatarBadge :url="tryAvatarUrl" :size="140" />
            <view class="tryon-info">
              <view class="tname">{{ meName }}</view>
              <view class="trecord">{{ record }}</view>
            </view>
          </view>
        </view>

        <!-- 两栏（选头像/选卡背）：同构一套模板按 kind 驱动，微信头像选项只挂在
             头像栏公共款节尾（头像被记下的老球友才见，4.8） -->
        <template v-for="col in COLUMNS" :key="col.kind">
          <SectionTitle :title="col.title" />
          <view v-for="sec in sections[col.kind]" :key="sec.key" class="sec">
            <view class="sec-h">{{ sec.title }}</view>
            <view class="tiles">
              <view
                v-for="it in sec.rows"
                :key="it.cid"
                class="tile"
                :class="{ on: sel[col.kind] === it.cid }"
                @click="pick(col.kind, it.cid)"
              >
                <view class="thumb">
                  <AvatarBadge
                    v-if="col.kind === 'avatar'"
                    :url="it.asset"
                    :size="44"
                  />
                  <view
                    v-else
                    class="th-back"
                    :style="{ backgroundImage: `url('${it.asset}')` }"
                  />
                  <view v-if="lockedOf(it)" class="tag">锁</view>
                  <view v-else-if="newOf(it)" class="tag isNew">新</view>
                </view>
                <view class="tile-name">{{ it.name }}</view>
                <!-- 带锁款：册子条件原文照显 + 可派生时再给一行「还差 X」（锁标行守卫同源） -->
                <template v-if="lockedOf(it)">
                  <view class="tile-cond">{{ it.lock_text }}</view>
                  <view v-if="gapOf(it)" class="tile-cond gap">{{
                    gapOf(it)
                  }}</view>
                </template>
              </view>

              <!-- 微信头像（4.8）：选项只在后端记下头像时渲染，挂在头像栏公共款节尾；
                   预览图由装扮页自带（wechat_avatar_url）——有选项必有真图，
                   记录缺失的异常场合占位圆+字样兜底 -->
              <view
                v-if="
                  col.kind === 'avatar' &&
                  sec.key === 'common' &&
                  page.wechat_avatar_available
                "
                class="tile"
                :class="{ on: sel.avatar === 'wechat' }"
                @click="sel.avatar = 'wechat'"
              >
                <view class="thumb">
                  <AvatarBadge v-if="wechatUrl" :url="wechatUrl" :size="44" />
                  <view v-else class="wx-slot">微信头像</view>
                </view>
                <view class="tile-name">微信头像</view>
              </view>
            </view>
          </view>
        </template>

        <!-- 昵称：初值取当前名，本地草稿不即时写 store，保存才落（toast 在 store） -->
        <AppField label="昵称">
          <AppInput v-model="nameDraft" placeholder="怎么称呼你" />
        </AppField>
        <!-- 手机号（1.1 A1 档案页）：完整号只有本人可见 + 「账号的根」换号提示；
             手机号不可自行换（人工） -->
        <AppField v-if="session.account?.phone" label="手机号">
          <view class="phonerow">
            <text class="phone">{{ session.account.phone }}</text>
            <text class="phint">手机号是你账号的根 · 换号先联系群主</text>
          </view>
        </AppField>

        <!-- 页底留白：给 fixed 保存条让位（字段自带 margin 不够垫） -->
        <view class="tail-gap" />
      </template>

      <!-- 保存条：页底常驻（拇指一次点完闭环）；含未解锁款则灰钮+文字报差什么。
           键盘弹起骑到键盘上沿 -->
      <view
        class="savebar"
        :style="kbH ? { transform: `translateY(-${kbH}px)` } : undefined"
      >
        <AppButton
          variant="pri"
          block
          :disabled="saveDisabled"
          @click="onSave"
          >{{ saveText }}</AppButton
        >
      </view>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/* 装扮页：本地试穿态（sel 头像/卡背各一件，初始=当前穿戴）+ 保存时变化才发请求
   （穿戴走 POST /cosmetics/dress、昵称走改名片旧口）；「新」标与解锁状态全由
   GET /api/cosmetics 打开即核算给定，界面只显示不算。保存成功 navigateBack
   返回我的页（toast 在 mine 页 ToastHost 常驻亮）。 */
import { computed, ref, onMounted, onUnmounted } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import PageShell from "@/components/biz/PageShell.vue";
import BackRow from "@/components/biz/BackRow.vue";
import SectionTitle from "@/components/ui/SectionTitle.vue";
import AvatarBadge from "@/components/ui/AvatarBadge.vue";
import CardBackdrop from "@/components/ui/CardBackdrop.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import AppButton from "@/components/ui/AppButton.vue";
import EmptyBox from "@/components/ui/EmptyBox.vue";
import { useUserStore } from "@/stores/user";
import { useSessionStore } from "@/stores/session";
import { useUiStore } from "@/stores/ui";
import { bindBlurOnBlank, unbindBlurOnBlank } from "@/composables/blurOnBlank";
import { errText } from "@/api/http";
import {
  apiCosmeticsPage,
  apiCosmeticsDress,
  type CosmeticsPageApi,
  type CosmeticItemApi,
} from "@/api/cosmetics";
import { dressBlock, honorGap, isUnlocked } from "@/utils/dress";
import { displayMeName, meRecordText } from "@/utils/format";

const user = useUserStore();
const session = useSessionStore();
const ui = useUiStore();
/** 我 = store 同一份可变引用（试穿框名字/战绩、保存后本地镜像换新） */
const me = computed(() => user.me);

/* ---- 整页数据：进页拉一次（后端顺手核算三类进度），失败可重试可退回 ---- */
const page = ref<CosmeticsPageApi | null>(null);
const loadErr = ref(false);
const busyLoad = ref(false);

/* ---- 试穿态：sel 是本地草稿（拉到整页后初始=当前穿戴），保存成功才落云；
      点任一件即时试穿（含带锁款——试穿放开、保存把关，4.4）。
      初始空串占位：整页模板闸在 page 之后，onLoad 拉到整页即覆写为本人当前
      穿戴，占位值不上屏（穿戴真值不另设常量镜像，全由 GET wearing 直出） ---- */
const sel = ref({ avatar: "", back: "" });
function pick(kind: "avatar" | "back", cid: string): void {
  sel.value[kind] = cid;
}

async function load(): Promise<void> {
  busyLoad.value = true;
  loadErr.value = false;
  try {
    const data = await apiCosmeticsPage();
    page.value = data;
    sel.value.avatar = data.wearing.avatar;
    sel.value.back = data.wearing.back;
  } catch {
    loadErr.value = true;
  } finally {
    busyLoad.value = false;
  }
}
onLoad(() => void load());

/** 两栏一张模板：kind 驱动选中态与缩略形态（头像圆章 / 卡背横幅缩略） */
const COLUMNS = [
  { kind: "avatar", title: "选头像" },
  { kind: "back", title: "选卡背" },
] as const;

/* 两栏分节（页数据加载后恒定，computed 缓存——点选试穿触发重渲染不再全册重筛；
    定制款条目层裁剪在后端：未授予者的 items 里本来就没有，节自然不渲染（4.7）） */
const sections = computed(() => {
  const of = (kind: "avatar" | "back") => {
    const rows = (page.value?.items ?? []).filter((i) => i.kind === kind);
    return [
      {
        key: "common",
        title: "公共款",
        rows: rows.filter((i) => i.tier === "common"),
      },
      {
        key: "honor",
        title: "荣誉款",
        rows: rows.filter((i) => i.tier === "honor"),
      },
      {
        key: "custom",
        title: "专属定制",
        rows: rows.filter((i) => i.tier === "custom"),
      },
    ].filter((s) => s.rows.length > 0);
  };
  return { avatar: of("avatar"), back: of("back") };
});

/* 册子 cid → 条目对表（渲染期恒定，Map 一次建好；itemOf 背后的 .find 逐次线性扫） */
const itemMap = computed(
  () => new Map(page.value?.items.map((i) => [i.cid, i] as const)),
);
function itemOf(cid: string): CosmeticItemApi | undefined {
  return itemMap.value.get(cid);
}
function lockedOf(it: CosmeticItemApi): boolean {
  return !isUnlocked(it.cid, page.value?.unlocks ?? {});
}
function newOf(it: CosmeticItemApi): boolean {
  return page.value?.unlocks[it.cid]?.is_new ?? false;
}
function gapOf(it: CosmeticItemApi): string | null {
  return honorGap(it, page.value!.progress);
}

/** 微信头像预览图：装扮页全视图自带本人微信头像原图（有记录直出、没记录
    null）——有选项（available）必有真图，试穿不再吃 me.avatarUrl（那只在
    正穿着时才是微信图）；空走占位圆兜底 */
const wechatUrl = computed(() => page.value?.wechat_avatar_url);

/** 试穿框头像：册子编号直取 asset；'wechat' 有预览图用图、没有回落默认公共款 */
const tryAvatarUrl = computed(() => {
  if (sel.value.avatar === "wechat") return wechatUrl.value;
  return itemOf(sel.value.avatar)?.asset;
});

/** 试穿框名片数据：与我的页同源 me（显示名/战绩行单一源在 utils/format） */
const meName = computed(() => displayMeName(me.value.name, session.isGuest));
const record = computed(() => meRecordText(me.value.play, me.value.win));

/* ---- 保存把关（4.4）：含未解锁件 → 钮灰 + 文字报差什么；全可保存 → 正常钮 ---- */
const blockText = computed(() =>
  page.value ? dressBlock(page.value, sel.value) : null,
);

const saveBusy = ref(false);
const saveDisabled = computed(
  () => !page.value || !!blockText.value || saveBusy.value,
);
const saveText = computed(() => {
  if (saveBusy.value) return "保存中…";
  if (blockText.value) return blockText.value;
  return "保存";
});

/** 保存：穿戴变化才发 dress、昵称变化才发改名片（穿戴永远「最后保存的赢」）；
    空名前置拦截没存成不退场；失败 toast 可重试、穿戴保持原样（越权/断网由
    后端与网络层把关）。成功 navigateBack 返回我的页（现状去向） */
async function onSave(): Promise<void> {
  if (saveBusy.value || !page.value) return;
  const n = nameDraft.value.trim();
  if (!n) {
    ui.toast("昵称不能为空");
    return;
  }
  saveBusy.value = true;
  try {
    const p = page.value;
    const body: { avatar?: string; back?: string } = {};
    if (sel.value.avatar !== p.wearing.avatar) body.avatar = sel.value.avatar;
    if (sel.value.back !== p.wearing.back) body.back = sel.value.back;
    const dressChanged = body.avatar !== undefined || body.back !== undefined;
    const nameChanged = n !== me.value.name;
    // 穿戴与昵称两口互不依赖，并行同发省一趟往返；失败留页可重试（成功的半边
    // 本地已镜像，重试只补发另一边，仍是「最后保存的赢」）
    const [d] = await Promise.all([
      dressChanged ? apiCosmeticsDress(body) : null,
      nameChanged ? session.saveProfile({ nickname: n }) : null, // toast 在 store
    ]);
    if (d) {
      // 本地镜像先行换新（store 单点换装，返回我的页名片即点即新）；wearing 对表
      // 同步，避免重试把同一份穿戴再发一遍
      user.applyDress(d);
      p.wearing = { avatar: d.avatar, back: d.back };
      if (!nameChanged) ui.toast("已保存 · 全局同步换新");
    }
    uni.navigateBack();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    saveBusy.value = false;
  }
}

/* 键盘让位：软键盘弹起把保存条顶到键盘上沿（uni H5 3.5+/App 支持；不支持的端
   不触发，保存条留在页底——点空白收键盘后自然可见，是同一件事的兜底）。
   on/off 配对（onKeyboardHeightChange 是全局监听，只挂不摘会随进出页面叠回调） */
const kbH = ref(0);
function onKbHeight(res?: { height?: number }): void {
  kbH.value = res?.height ?? 0;
}
onMounted(() => {
  uni.onKeyboardHeightChange?.(onKbHeight);
});
onUnmounted(() => {
  uni.offKeyboardHeightChange?.(onKbHeight);
});

/* 点空白收键盘（login 页同款，机制见 blurOnBlank.ts 头注） */
const tapRoot = ref<unknown>(null);
onMounted(() => bindBlurOnBlank(tapRoot.value));
onUnmounted(() => unbindBlurOnBlank(tapRoot.value));

/** 昵称草稿 */
const nameDraft = ref(me.value.name);
</script>

<style lang="scss" scoped>
/* ---------- 头部 brand：版式走全局 .brand 类，只补 700 加粗（bills 同款） ---------- */
.brand {
  font-weight: 700;
}

/* ---------- 加载/出错占位（A2：先出结构后出图，版面不跳） ---------- */
.state {
  margin-top: 14px;
}
.retry {
  margin-top: 10px;
}

/* ---------- 大试穿框：卡背 'd' 档取景（宿主契约三件套挂全局 .cbd-host，负 z-index
   取景层垫在卡底之上、文字之下）；素卡渐变兜底（没铺出图的空档） ---------- */
.tryon {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  background: linear-gradient(150deg, var(--ink3), var(--ink2));
  padding: 22px 18px;
}
.tryon-row {
  display: flex;
  align-items: center;
  gap: 18px;
}
.tryon-info {
  flex: 1;
  min-width: 0;
}
.tryon-info .tname {
  font-size: 20px;
  font-weight: 800;
}
.tryon-info .trecord {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
  margin-top: 5px;
}

/* ---------- 两栏的节与件格：横向换行铺开（头像 44 圆章 / 卡背横幅缩略） ---------- */
.sec {
  margin: 10px 0 4px;
}
.sec-h {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--dim);
  margin: 8px 0 8px 2px;
}
.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.tile {
  width: 76px;
  flex: none;
  cursor: pointer;
}
.tile .thumb {
  position: relative;
  width: 60px;
  height: 60px;
  margin: 0 auto;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--ink3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.tile.on .thumb {
  border-color: var(--lemon);
  box-shadow: 0 0 0 1px var(--lemon);
}
/* 卡背缩略：横幅 12:5 取中一块（background-image 直吃 asset） */
.th-back {
  width: 52px;
  height: 30px;
  border-radius: 5px;
  background-size: cover;
  background-position: center;
  background-color: var(--ink2);
}
.tile-name {
  font-size: 11px;
  text-align: center;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile-cond {
  font-size: 9px;
  line-height: 1.4;
  color: var(--dim);
  text-align: center;
  margin-top: 2px;
}
.tile-cond.gap {
  color: var(--lemon);
}
/* 件角标：锁（带锁荣誉款）/ 新（本次核算新解锁，看过即摘）。占位顺序锁优先 */
.tag {
  position: absolute;
  top: -5px;
  right: -5px;
  font-family: var(--mono);
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 8px;
  background: rgba(14, 14, 18, 0.9);
  border: 1px solid var(--line);
  color: var(--dim);
}
.tag.isNew {
  color: var(--lemon);
  border-color: rgba(255, 212, 0, 0.5);
}
/* 微信头像无预览图的占位圆（头像还没被记下不会到这——正穿着但 me 未带图的兜底） */
.wx-slot {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px dashed var(--line);
  display: grid;
  place-items: center;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}

/* 手机号行（1.1 档案页：本人可见完整号 + 唯一钥匙提示） */
.phonerow {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}
.phone {
  font-family: var(--mono);
  font-size: 14px;
  letter-spacing: 1px;
}
.phint {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}

/* 页底留白给 fixed 保存条让位（字段自带 margin 不够垫一截） */
.tail-gap {
  height: 56px;
}

/* ---------- 保存条：页底常驻，半透明底+发丝线（与吸附返回行同族材质） ---------- */
.savebar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 80;
  padding: 10px 18px calc(14px + env(safe-area-inset-bottom, 0px));
  background: rgba(14, 14, 18, 0.92);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--line);
  transition: transform 0.2s ease-out;
}
/* 宽屏画布：与 PageShell 的 480px 居中画布同宽（fixed 元素用左右归零+max-width 居中） */
@media (min-width: 561px) {
  .savebar {
    max-width: 480px;
    margin: 0 auto;
  }
}
</style>
