/* 现场 API（2.3 批4 阶段1）——总账读 + 记分链/2.2 域/散场链写端点，仿 games.ts 范式：
   只做类型化取数与错误透传，snake 线上形状在 types.ts 的 LiveViewApi 族。
   - 写动作成功体直接是最新总账视图（写后回画面，免二次拉读）；
   - 两级号防线退回的 409（live_stale_total/court）在 {"error"} 旁带 "view"——http.ts
     已把它挂到 ApiError.view，拿它对表即可、不用再拉一次读（附录 B1）；
   - base 号是「出发时看到的号」：动全场只带 baseTotalSeq，片级记分写另带 baseCourtSeq。 */
import { request } from "./http";
import type {
  CheckInAction,
  DealCourt,
  EloRowApi,
  LiveRulesInput,
  LiveSide,
  LiveView,
  LiveViewApi,
  SettleConfirmInput,
  TempoAction,
} from "./types";

/* ---- 读与开账 ---- */

/** 总账读（可匿名；散场后同一形状=只读回看；未开账 404 live_not_found） */
export function apiLiveView(gameId: number): Promise<LiveViewApi> {
  return request("GET", `/games/${gameId}/live`);
}

/** 开账（组织者；幂等——已开账直接回视图，散场后再点也只回看不重开） */
export function apiLiveStart(gameId: number): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/start`);
}

/* ---- 记分链 ---- */

/** 排阵上报（发牌算法在前端）：各片 A/B 必须正好是候场队头那拨，总账把关后落片开打 */
export function apiLiveDeal(
  gameId: number,
  courts: DealCourt[],
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/deal`, {
    courts: courts.map((c) => ({ court_no: c.courtNo, a: c.a, b: c.b })),
    base_total_seq: baseTotalSeq,
  });
}

/** 记一分（§4.1）：到分判定后端落账时当即判——够线该片转待确认(origin='auto')，别片照打 */
export function apiLivePoint(
  gameId: number,
  courtNo: number,
  side: LiveSide,
  baseTotalSeq: number,
  baseCourtSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/point`, {
    court_no: courtNo,
    side,
    base_total_seq: baseTotalSeq,
    base_court_seq: baseCourtSeq,
  });
}

/** 撤一分：只撤该片最后得分方那 1 分；auto 窗撤到分线下自动关窗回在打（§4.5） */
export function apiLiveUndo(
  gameId: number,
  courtNo: number,
  baseTotalSeq: number,
  baseCourtSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/undo`, {
    court_no: courtNo,
    base_total_seq: baseTotalSeq,
    base_court_seq: baseCourtSeq,
  });
}

/** 清零重开（全权）：比分归 0:0、pending 作废回在打，人不下场同批重打（§4.2） */
export function apiLiveClear(
  gameId: number,
  courtNo: number,
  baseTotalSeq: number,
  baseCourtSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/clear`, {
    court_no: courtNo,
    base_total_seq: baseTotalSeq,
    base_court_seq: baseCourtSeq,
  });
}

/** 提前结算开窗（全权，§4.4）：不到分线也能收，转 pending(origin='manual')；预选看视图 preselect */
export function apiLiveSettleOpen(
  gameId: number,
  courtNo: number,
  baseTotalSeq: number,
  baseCourtSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/settle-open`, {
    court_no: courtNo,
    base_total_seq: baseTotalSeq,
    base_court_seq: baseCourtSeq,
  });
}

/** 确认结束（全权，§4.6）：一本账原子（战报+积分+回流补位一个事务）；重放幂等回 200 */
export function apiLiveSettleConfirm(
  gameId: number,
  input: SettleConfirmInput,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/settle-confirm`, {
    court_no: input.courtNo,
    winner_side: input.winnerSide,
    score_a: input.scoreA,
    score_b: input.scoreB,
    no_redeal: input.noRedeal ?? false,
    base_total_seq: input.baseTotalSeq,
    base_court_seq: input.baseCourtSeq,
  });
}

/** 取消对局（全权，§4.7）：整场作废不计分，场上的人原样回流队首（取消本就不补位） */
export function apiLiveCancel(
  gameId: number,
  courtNo: number,
  baseTotalSeq: number,
  baseCourtSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/cancel`, {
    court_no: courtNo,
    base_total_seq: baseTotalSeq,
    base_court_seq: baseCourtSeq,
  });
}

/* ---- 2.2 域动作（动全场，只走总号） ---- */

/** 报到四态（自己报自己可、代办他人需全权）：late/join 排队尾、left 清队列位与片位 */
export function apiLiveCheck(
  gameId: number,
  playerId: number,
  check: CheckInAction,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/check`, {
    player_id: playerId,
    check,
    base_total_seq: baseTotalSeq,
  });
}

/** 空降报到（本人；1.3 附录 B1 记账通道）：名册没我建行入册（考勤归一+队尾），
    有行幂等回视图——报过到重复点静默 */
export function apiLiveDropIn(
  gameId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/dropin`, {
    base_total_seq: baseTotalSeq,
  });
}

/** 带访客（全权；1.3 附录 B1 记账通道）：count 位挂担保人名册行名下进总账、
    队尾进候场；命名在后端（空名按担保人、多人具名 name·i）——name 空串传 undefined */
export function apiLiveGuests(
  gameId: number,
  body: { count: number; name?: string; guarantor_id: number },
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/guests`, {
    count: body.count,
    name: body.name,
    guarantor_id: body.guarantor_id,
    base_total_seq: baseTotalSeq,
  });
}

/** 换人（任意到场者，§4.9）：in 原位顶坑、out 回队尾；pending 片冻结拒收（court_frozen） */
export function apiLiveSwap(
  gameId: number,
  outId: number,
  inId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/swap`, {
    out_id: outId,
    in_id: inId,
    base_total_seq: baseTotalSeq,
  });
}

/** 歇连（给自己随时、给他人需全权）：skip 叠加 / fire 连战排队首 / unskip 清零 */
export function apiLiveTempo(
  gameId: number,
  playerId: number,
  action: TempoAction,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/tempo`, {
    player_id: playerId,
    action,
    base_total_seq: baseTotalSeq,
  });
}

/** 规则四件套+片数+分制（全权，§4.7 收权）：只动显式给的字段——undefined 键不进 JSON 体 */
export function apiLiveRules(
  gameId: number,
  input: LiveRulesInput,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/rules`, {
    doubles: input.doubles,
    down: input.down,
    pairing: input.pairing,
    streak_max: input.streakMax,
    courts_count: input.courtsCount,
    scoring: input.scoring,
    base_total_seq: baseTotalSeq,
  });
}

/** 封管理员（组织者独占；靶行须正式球友，访客当不了） */
export function apiLiveSetAdmin(
  gameId: number,
  playerId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/set-admin`, {
    player_id: playerId,
    base_total_seq: baseTotalSeq,
  });
}

/** 撤管理员（组织者独占，幂等） */
export function apiLiveUnsetAdmin(
  gameId: number,
  playerId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/unset-admin`, {
    player_id: playerId,
    base_total_seq: baseTotalSeq,
  });
}

/* ---- 散场链 ---- */

/** 未完对局全部取消（全权，§4.9 一键）：逐片 cancel 语义一个事务；无残局幂等 no-op */
export function apiLiveSweepCancelAll(
  gameId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/sweep-cancel-all`, {
    base_total_seq: baseTotalSeq,
  });
}

/** 散场收工（组织者；早退时管理员代收）：残局不清完不放行（409 live_residue） */
export function apiLiveEnd(
  gameId: number,
  baseTotalSeq: number,
): Promise<LiveViewApi> {
  return request("POST", `/games/${gameId}/live/end`, {
    base_total_seq: baseTotalSeq,
  });
}

/* ---- 映射 ---- */

/** 结算行（snake→camel）：战报 elo_rows 与待确认片 elo_preview 双分支共用 */
const eloRow = (r: EloRowApi) => ({
  accountId: r.account_id,
  name: r.name,
  guest: r.guest,
  ratingBefore: r.rating_before,
  ratingAfter: r.rating_after,
  delta: r.delta,
});

/** LiveViewApi（线上 snake）→ LiveView（camel）唯一映射点（沿 stores/game.ts toGame 先例）。
    身份块（两旗+组织者账号）视图直读——2026-10-08 修订前由本层按 viewer 上下文
    拼装（批4a 裁定），深链冷启动的「组织者按不了按钮」补丁族由此而生，已退役 */
export function toLiveView(v: LiveViewApi): LiveView {
  return {
    gameId: v.game_id,
    startedAt: v.started_at,
    ended: v.ended,
    endedAt: v.ended_at,
    fee: v.fee
      ? { total: v.fee.total, heads: v.fee.heads, perHead: v.fee.per_head }
      : null,
    totalSeq: v.total_seq,
    round: v.round,
    admins: [...v.admins],
    feed: [...v.feed],
    courtsCount: v.courts_count,
    rules: {
      scoring: v.rules.scoring,
      doubles: v.rules.doubles,
      down: v.rules.down,
      pairing: v.rules.pairing,
      streakMax: v.rules.streak_max,
    },
    players: v.players.map((p) => ({
      id: p.id,
      accountId: p.account_id,
      name: p.name,
      guest: p.guest,
      dupr: p.dupr, // DUPR 配平代位分（1.4 §6 修订：访客/无派分行统一 2.5、有派分行吃派生分）
      guarantorAccountId: p.guarantor_account_id,
      dropin: p.dropin,
      check: p.check,
      arriveAt: p.arrive_at,
      leftAt: p.left_at,
      courtNo: p.court_no,
      courtSide: p.court_side,
      skip: p.skip,
      fire: p.fire,
      queuePos: p.queue_pos,
    })),
    queue: [...v.queue],
    courts: v.courts.map((c) => ({
      courtNo: c.court_no,
      status: c.status,
      seq: c.seq,
      scoreA: c.score_a,
      scoreB: c.score_b,
      lastWinnerSide: c.last_winner_side,
      courtSeq: c.court_seq,
      pendingOrigin: c.pending_origin,
      preselect: c.preselect,
      scoring: c.scoring,
      eloPreview: c.elo_preview
        ? { a: c.elo_preview.a.map(eloRow), b: c.elo_preview.b.map(eloRow) }
        : null,
    })),
    courtSeqs: Object.fromEntries(
      v.courts.map((c) => [c.court_no, c.court_seq]),
    ),
    matches: v.matches.map((m) => ({
      courtNo: m.court_no,
      seq: m.seq,
      winners: m.winners.map((w) => ({ ...w })),
      losers: m.losers.map((w) => ({ ...w })),
      sa: m.score_a,
      sb: m.score_b,
      winA: m.winner_side === "a",
      endedAt: m.ended_at,
      eloRows: m.elo_rows.map(eloRow),
    })),
    isOrganizer: v.is_organizer,
    isFullPower: v.is_full_power,
    organizerAccountId: v.organizer_account_id,
  };
}
