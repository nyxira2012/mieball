/* 结算窗比分直录交互单一源（真局 EndSettleModal 与教学沙盒 SandboxSettle 同吃）：
   本地态 winA/saText/sbText、胜方联动与点选闸、数字清洗与失焦归一收此一处；
   预填源与写回宿主注入，窗态（Ref）由宿主传——两域 store 各异，组合式不挑。 */
import { computed, ref, watch, type Ref } from "vue";
import { canPickWinner, followWinner } from "@/utils/rotate";

export function useScoreEntry(
  /** 结算窗态（null=关）：变真值即按预填源重置本地态（一次一扇，窗开着不会换片） */
  win: Ref<unknown>,
  /** 开窗预填源：返回比分与胜方预选（改分模式吃最新落账行、上传模式吃本机账） */
  prefill: () => { sa: number; sb: number; winA: boolean | null },
  /** 直录写回宿主（传才写）：upload 模式当场落回本机账——「暂不结算」后
      场卡接着打的就是纠偏后的分；改分模式不传，输入只动本地 */
  writeBack?: (sa: number, sb: number) => void,
) {
  const winA = ref<boolean | null>(null);
  const saText = ref("0");
  const sbText = ref("0");
  /** 空视同 0（数字面派生） */
  const sa = computed(() => Number(saText.value || "0"));
  const sb = computed(() => Number(sbText.value || "0"));

  /** 分低方选不中；平分双方均可点 */
  const canA = computed(() => canPickWinner(sa.value, sb.value, "a"));
  const canB = computed(() => canPickWinner(sa.value, sb.value, "b"));
  /** 确认闸：已点胜方（平分未点禁确认） */
  const canConfirm = computed(() => winA.value !== null);

  watch(
    win,
    (w) => {
      if (!w) return;
      const p = prefill();
      saText.value = String(p.sa);
      sbText.value = String(p.sb);
      winA.value = p.winA;
    },
    { immediate: true },
  );

  /** 点胜方（分低方选不中防误点） */
  function pick(side: "a" | "b"): void {
    if (!canPickWinner(sa.value, sb.value, side)) return;
    winA.value = side === "a";
  }

  /** 比分直录：只收非负整数、至多 3 位（防误触长串，非分制上限——净胜 2 可无限延）；
      胜方自动跟分高方（平分清空，后端仍把关） */
  function onScore(side: "a" | "b", ev: Event): void {
    const raw =
      (ev as { detail?: { value?: string } }).detail?.value ??
      (ev.target as { value?: string } | null)?.value ??
      "";
    const digits = raw.replace(/\D/g, "").slice(0, 3);
    if (side === "a") saText.value = digits;
    else sbText.value = digits;
    winA.value = followWinner(sa.value, sb.value);
    writeBack?.(sa.value, sb.value);
  }

  /** 失焦归一：空与前置零收成规范十进制（""→"0"、"007"→"7"） */
  function onBlurScore(side: "a" | "b"): void {
    if (side === "a") saText.value = String(sa.value);
    else sbText.value = String(sb.value);
  }

  return {
    winA,
    saText,
    sbText,
    sa,
    sb,
    canA,
    canB,
    canConfirm,
    pick,
    onScore,
    onBlurScore,
  };
}
