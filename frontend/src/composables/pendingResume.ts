/* 挂起动作续办单一源（1.6 末批自 SignupSheet.followUp 提升）：
   名片建号/接管成功路与「点登录→登录页登回来」两路共用——登录往返中弹层已被
   PageShell.onHide 关闭、SignupSheet 已卸载，续办只能由登录页凭 ui.pendingAfterLogin
   快照代跑。失败 toast 人话（动作入口仍在对应页面可重试），不阻断调用方收尾。 */
import { errText } from "@/api/http";
import { useGameStore } from "@/stores/game";
import { useLiveStore } from "@/stores/live";
import { useUiStore } from "@/stores/ui";
import type { SignupPending } from "@/stores/ui";
import { goMeet } from "@/utils/nav";

export async function runPendingResume(pending: SignupPending): Promise<void> {
  const game = useGameStore();
  const liveStore = useLiveStore();
  const ui = useUiStore();
  try {
    if (pending.pendingJoin) {
      await game.joinGame(
        pending.pendingJoin.gameId,
        pending.pendingJoin.bring,
      );
    } else if (pending.pendingLaunch) {
      await game.publishGame(pending.pendingLaunch);
      goMeet(); // 建局成功回约球页（与 LaunchSheet.publish 同径）
    } else if (pending.pendingCheckin) {
      await liveStore.arriveMe(pending.pendingCheckin.gameId); // 2.1 选项A：建号即球友，自动「我到了」
    } else if (pending.pendingIntent) {
      const { slots, frequency, note } = pending.pendingIntent;
      await game.saveIntent(slots, frequency, note); // 文案由 store 发（单一源）
    }
  } catch (e) {
    ui.toast(errText(e));
  }
}
