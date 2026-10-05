/* 短信 60 秒冷却倒计时（1.1 三个发码界面共用）：login 找回页 / SignupSheet 建号短信态 /
   AccountSheet 注销短信步原各持一份逐字副本，收敛于此。组件卸载自动清计时器。 */
import { onUnmounted, ref } from 'vue';

export function useSmsCountdown() {
  /** 剩余秒数；0 = 可发送 */
  const countdown = ref(0);
  let timer: ReturnType<typeof setInterval> | null = null;

  function start(): void {
    countdown.value = 60;
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
      countdown.value--;
      if (countdown.value <= 0 && timer) {
        clearInterval(timer);
        timer = null;
      }
    }, 1000);
  }
  onUnmounted(() => {
    if (timer) clearInterval(timer);
  });

  return { countdown, start };
}
