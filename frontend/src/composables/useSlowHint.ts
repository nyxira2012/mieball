/* A2 加载慢提示单一源（meet/detail 两页共用）：busy 翻 true 起 2 秒计时，
   翻 false（或组件卸载）即收——复位毛刺（上一轮慢网点亮的 slow 不带进下一轮）由 watch 归一。 */
import { onUnmounted, ref, watch } from "vue";

export function useSlowHint(busy: () => boolean) {
  const slow = ref(false);
  let timer: ReturnType<typeof setTimeout> | null = null;
  watch(busy, (on) => {
    if (timer) clearTimeout(timer);
    if (on) timer = setTimeout(() => (slow.value = true), 2000);
    else slow.value = false;
  });
  onUnmounted(() => {
    if (timer) clearTimeout(timer);
  });
  return { slow };
}
