<template>
  <!-- 订场登记 / 锁定必打（3.2 订场改版 · 4.7）：三态锁共用的面板——
       没锁 →「锁定必打（不订场）」上手动空锁，二段确认（人数不够也照开、不可解锁）后才落；
       填了场地号+总价 → 保存即订场锁（必开 + 费用落定 + 场地号告诉大家），不用再点一次锁定；
       已订场 → 面板随时可重开改登记（退一片删一个号、总价改成退完后实际花的钱）或清空；
       截止后名单已锁面板仍可改——临到场场馆换号很常见，锁名单只锁人。
       组装全用公共件（AppField/AppInput/AppButton）；动作走 game store（bookCourt/clearBooking/lockGame，toast 在 store 内）。
       人均口径：输入中的 ¥ 预览是现场换算（Math.round=后端 half-up 同口径），保存后以回填 game.perHead 定值为准（A4）。 -->
  <view v-if="feeOnly || g" class="bks">
    <!-- 补填形态（1.3 §4.5）：散场后从未填过价的局只留「填总价」这一个口子——
         先填数，再吃 fee-preview 后端定值给确认步「将按人均 X 元向 N 人出账」，点定出账 -->
    <template v-if="feeOnly">
      <view class="sheet-t">补填费用 · 只填总价</view>
      <view class="sheet-hint"
        >散场后只有这一次补价机会：按小票填总价（真免费填
        0），点定出账，账单日期记散场那天</view
      >

      <AppField label="总价 · 免费场填 0">
        <AppInput v-model="feeText" type="number" placeholder="如：700" />
        <view class="sub fh">{{ feeHint }}</view>
      </AppField>

      <!-- 确认步：定值来自后端 preview（A4：界面不自算） -->
      <view v-if="preview" class="sub sure-warn">
        {{
          isZeroFee
            ? "免费场 · 费用定为 ¥0，不出账，提醒消失"
            : `将按人均 ¥${preview.per_head} 元向 ${preview.heads} 人出账`
        }}
      </view>

      <view class="btns">
        <AppButton
          v-if="preview"
          variant="ghost"
          class="flex1"
          :disabled="busy"
          @click="preview = null"
          >再改改</AppButton
        >
        <AppButton
          v-else
          variant="ghost"
          class="flex1"
          :disabled="busy"
          @click="ui.closeSheet()"
          >取消</AppButton
        >
        <AppButton
          variant="pri"
          class="flex1"
          :disabled="busy"
          @click="onFeeNext"
        >
          {{
            preview
              ? isZeroFee
                ? "确认定为 ¥0"
                : "确认出账"
              : "下一步 · 看摊账"
          }}
        </AppButton>
      </view>
    </template>

    <!-- 订场登记形态（3.2/4.7 原面板） -->
    <template v-else-if="g">
      <view class="sheet-t">锁定必打 · 订场登记</view>
      <view class="sheet-hint"
        >订了场这局就必开 ·
        场地号和总价随时可改，退一片就删一个号、照小票改总价</view
      >

      <!-- 现状行：订几片、花多少的参考（截止后本面板仍可改——临到场场馆换号很常见，名单锁定只锁人） -->
      <view class="sub stat">
        已报 {{ g.heads }} 人（含带的人）· 最少 {{ g.minPlayers }} · 上限
        {{ g.maxPlayers }}{{ forced ? " · 已锁定必打" : "" }}
      </view>

      <AppField label="场地号 · 几片填几个号（顿号/逗号/空格隔开）">
        <AppInput v-model="courtsText" placeholder="如：3号、5号" />
        <view class="sub fh">{{ parseHint }}</view>
      </AppField>

      <AppField label="总价 · 免费场填 0（按订场小票，人均按当前人数摊）">
        <AppInput v-model="feeText" type="number" placeholder="如：480" />
        <view class="sub fh">{{ feeHint }}</view>
      </AppField>

      <!-- 空锁二段确认的第一段提示（4.7 原话：一锁不撤、不可解锁，只能撤局） -->
      <view v-if="sureArmed && !courts.length" class="sub sure-warn">
        锁上后人数不够也照开，且不能解锁（只能撤局）
      </view>

      <view class="btns">
        <!-- 有登记才有清空（全退光：局回未订场原样，手动锁不跟着松） -->
        <AppButton
          v-if="hasBooking"
          variant="ghost"
          class="flex1 clear-btn"
          @click="onClear"
          >清空登记</AppButton
        >
        <AppButton
          v-if="courts.length"
          variant="pri"
          class="flex1"
          :disabled="busy"
          @click="onSave"
          >保存 · 已订场必开</AppButton
        >
        <!-- 空锁：已手动锁定则不再出现；点第一下只出确认，再点才落锁。
             窗口=开打前的工具箱三态（后端 lock 口径 TOOLBOX_STATUSES，pending 锁必打是
             待处置出口）——开打后空锁 422，钮不露出、live 只能订场登记（book 窗到散场前） -->
        <template v-else-if="canLock && !g.manualLock">
          <AppButton
            v-if="sureArmed"
            variant="ghost"
            class="flex1"
            :disabled="busy"
            @click="sureArmed = false"
            >再想想</AppButton
          >
          <AppButton
            variant="pri"
            class="flex1"
            :disabled="busy"
            @click="onSureTap"
            >{{ busy ? "锁定中…" : "确认锁定必打" }}</AppButton
          >
        </template>
      </view>
      <view v-if="!courts.length && g.manualLock" class="sub sure-note"
        >已手动锁定必打 · 填场地号和总价可升级为「已订场」</view
      >
    </template>
  </view>
</template>

<script setup lang="ts">
/* 订场登记 BookingSheet（3.2 订场改版 · 1.2 调用点适配：async + lockGame 改名 + 空锁二段确认）。
   场地号解析：顿号/逗号/空格/斜杠分隔，去空格去重保序——片数不单独填，就是识别出的个数。
   每次打开按当前登记带出原值（SheetHost 按 type 分发，关闭即卸载重挂）。 */
import { computed, ref, watch } from "vue";
import AppButton from "@/components/ui/AppButton.vue";
import AppField from "@/components/ui/AppField.vue";
import AppInput from "@/components/ui/AppInput.vue";
import { useGameStore } from "@/stores/game";
import { useUiStore } from "@/stores/ui";
import { errText } from "@/api/http";
import type { FeePreviewApi } from "@/api/games";

const props = defineProps({
  gameId: { type: Number, required: true },
  feeOnly: { type: Boolean, default: false }, // 补填形态（1.3 §4.5）：只填总价 + 确认步
});

const game = useGameStore();
const ui = useUiStore();
const busy = ref(false);

/** 局被撤下等场景的兜底（v-if 不渲染）；链接直达的局走 store.current */
const g = computed(() => game.findGame(props.gameId));
const forced = computed(() => !!g.value?.forced);
const hasBooking = computed(() => !!g.value?.courts?.length);
/** 空锁窗口（对齐后端 TOOLBOX_STATUSES）：开打后 lock 端点 game_not_open 422 */
const canLock = computed(
  () =>
    g.value != null &&
    (g.value.status === "open" ||
      g.value.status === "locked" ||
      g.value.status === "pending"),
);

/** 场地号解析（公共口径）：分隔符切 → 去空 → 去重保序 */
const courts = computed<string[]>(() => {
  const seen = new Set<string>();
  return courtsText.value
    .split(/[\s,，、/]+/)
    .map((s) => s.trim())
    .filter((s) => {
      if (!s || seen.has(s)) return false;
      seen.add(s);
      return true;
    });
});

const courtsText = ref(g.value?.courts?.join("、") ?? "");
const feeText = ref(g.value?.feeTotal != null ? String(g.value.feeTotal) : "");

const parseHint = computed(() =>
  courts.value.length
    ? `识别到 ${courts.value.length} 片：${courts.value.join("、")}`
    : canLock.value
      ? "不填场地号 = 只锁定必打，不登记订场"
      : "开打后不办空锁 · 填好场地号和总价即可订场",
);

const feeHint = computed(() => {
  if (props.feeOnly) return "按订场小票的总价填 · 点「下一步」先看摊账再点定";
  if (!courts.value.length) return "先填场地号，总价才有落点";
  const n = Number(feeText.value);
  if (feeText.value === "")
    return "按订场小票的总价填（片数 × 时段价，晚场贵白天便宜）";
  if (!Number.isFinite(n) || n < 0) return "总价得是非负数字";
  const hs = g.value?.heads ?? 1;
  return n === 0
    ? "免费场 · 人均 ¥0"
    : `按现在 ${hs} 人 · 人均 ¥${Math.round(n / Math.max(1, hs))}（人多会更低）`;
});

/* ---- 补填形态（1.3 §4.5）：填数 → fee-preview 定值确认步 → 点定出账 ---- */
const preview = ref<FeePreviewApi | null>(null);
const isZeroFee = computed(() => Number(feeText.value) === 0);

/* 防呆（§4.5「这最后一眼能拦住」）：总价一改，旧定值即作废、确认步弹回填数步——
   否则看过「人均 ¥58」后再改总价，确认行还亮旧数、点定出的却是新价的账 */
watch(feeText, () => (preview.value = null));

/** 两段式：没 preview 先取定值（后端现算）；有 preview 点定 → setFee 出账（store 内 toast） */
async function onFeeNext(): Promise<void> {
  const n = Number(feeText.value);
  if (feeText.value === "" || !Number.isFinite(n) || n < 0) {
    ui.toast("填一下总价 · 免费场填 0");
    return;
  }
  if (busy.value) return;
  busy.value = true;
  try {
    if (!preview.value) {
      preview.value = await game.feePreview(props.gameId, n);
    } else {
      await game.setFee(props.gameId, n);
      ui.closeSheet();
    }
  } catch (e) {
    preview.value = null; // 回到填数态（人数变了定值就变了，不让旧数挂着）
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

/** 保存订场：场地号 ≥1 且总价合法才落（toast 在 store 内） */
async function onSave(): Promise<void> {
  if (!g.value || !courts.value.length || busy.value) return;
  const n = Number(feeText.value);
  if (feeText.value === "" || !Number.isFinite(n) || n < 0) {
    ui.toast("填一下总价 · 免费场填 0");
    return;
  }
  busy.value = true;
  try {
    await game.bookCourt(g.value.id, courts.value, n);
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

/** 空锁二段确认（4.7：点空锁先确认一句，直落太重——锁上一锁不撤）：第一下只点亮确认态 */
const sureArmed = ref(false);

/** 空锁第二段才真落锁（store.lockGame，对齐后端 /lock） */
async function onSureTap(): Promise<void> {
  if (!g.value || busy.value) return;
  if (!sureArmed.value) {
    sureArmed.value = true;
    return;
  }
  busy.value = true;
  try {
    await game.lockGame(g.value.id);
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}

/** 清空登记（场地全退光）：局回未订场原样，手动锁保留（store 内判） */
async function onClear(): Promise<void> {
  if (!g.value || busy.value) return;
  busy.value = true;
  try {
    await game.clearBooking(g.value.id);
    ui.closeSheet();
  } catch (e) {
    ui.toast(errText(e));
  } finally {
    busy.value = false;
  }
}
</script>

<style lang="scss" scoped>
/* 壳层标题/hint 走全局 .sheet-t/.sheet-hint（base.scss 收源） */
/* 现状行（11px dim，同 LaunchSheet ppl-hint 家族） */
.stat {
  color: var(--dim);
  font-size: 11px;
  margin-bottom: 14px;
}
/* 字段下方实时提示 */
.fh {
  color: var(--dim);
  font-size: 11px;
  margin-top: 6px;
}
.btns {
  display: flex;
  gap: 10px;
}
.flex1 {
  flex: 1;
}
.clear-btn {
  color: var(--coral);
  border-color: rgba(255, 90, 54, 0.4);
}
.sure-note {
  color: var(--ice);
  font-size: 11px;
  margin-top: 10px;
}
/* 空锁二段确认的警示行（4.7 原话；coral 小字同 ConfirmSheet warnline 家族） */
.sure-warn {
  color: var(--coral);
  font-size: 12px;
  margin-bottom: 10px;
}
</style>
