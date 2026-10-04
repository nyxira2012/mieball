/* session store（1.1 账号域前端深模块）单测：
   - 启动认人：有钥匙换档案 / 钥匙失效静默降级游客
   - D3 过渡接线：真账号视图落到 reactive U.me 的「我」位
   - 退出/注销恢复演示态；建号成功清草稿
   API 层整体 mock（@/api/auth），不触网。 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import * as authApi from '@/api/auth';
import type { AccountView } from '@/api/auth';
import * as http from '@/api/http';
import { U } from '@/api/mock';
import { useSessionStore } from '@/stores/session';
import { useUserStore } from '@/stores/user';

vi.mock('@/api/auth', () => ({
  apiSignup: vi.fn(),
  apiMe: vi.fn(),
  apiUpdateProfile: vi.fn(),
  apiLogout: vi.fn(),
  apiSendCode: vi.fn(),
  apiRedeem: vi.fn(),
  apiDeactivate: vi.fn(),
}));

const view: AccountView = {
  id: 42,
  name: '海淀反手王',
  chibi: { skin: 2, hair: 3, hc: 1, shirt: 4, face: 2, acc: 1 },
  card_bg: 'gold',
  deactivated: false,
  phone: '13800001111',
  phone_tail: '1111',
};

/** 演示态 U.me 快照（恢复断言用） */
const demo = { id: U.me.id, name: U.me.name, chibi: { ...U.me.chibi }, cardBg: U.me.cardBg };

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  vi.spyOn(http, 'getToken').mockReturnValue(null);
  vi.spyOn(http, 'setToken').mockImplementation(() => {});
  vi.spyOn(http, 'clearCardDraft').mockImplementation(() => {});
});

describe('启动认人（4.3）', () => {
  it('本机有钥匙 → 换成后端档案，U.me 过渡位同步换新（D3）', async () => {
    vi.spyOn(http, 'getToken').mockReturnValue('a-token');
    vi.mocked(authApi.apiMe).mockResolvedValue({ account: view });

    const session = useSessionStore();
    await session.init();

    expect(session.status).toBe('ready');
    expect(session.account?.id).toBe(42);
    const me = useUserStore().me;
    expect(me.id).toBe(42);
    expect(me.name).toBe('海淀反手王');
    expect(me.chibi).toEqual(view.chibi);
    expect(me.cardBg).toBe('gold');
  });

  it('钥匙已作废（被接管/注销）→ 静默降级游客，不报错', async () => {
    vi.spyOn(http, 'getToken').mockReturnValue('dead-token');
    vi.mocked(authApi.apiMe).mockResolvedValue({ account: null });

    const session = useSessionStore();
    await session.init();

    expect(session.status).toBe('guest');
    expect(session.account).toBeNull();
  });

  it('没钥匙 → 直接游客', async () => {
    const session = useSessionStore();
    await session.init();
    expect(session.status).toBe('guest');
    expect(authApi.apiMe).not.toHaveBeenCalled();
  });

  it('网络失败 → 按游客进场，不拦启动', async () => {
    vi.spyOn(http, 'getToken').mockReturnValue('t');
    vi.mocked(authApi.apiMe).mockRejectedValue(new Error('net'));
    const session = useSessionStore();
    await session.init();
    expect(session.status).toBe('guest');
  });
});

describe('名片建号与退出（4.2 / A3）', () => {
  it('建号成功：落钥匙、接过渡位、清草稿', async () => {
    vi.mocked(authApi.apiSignup).mockResolvedValue({ token: 't1', account: view });
    const session = useSessionStore();
    await session.signupWithCard({ phone: '13800001111', nickname: '海淀反手王', nickname_set: true });

    expect(http.setToken).toHaveBeenCalledWith('t1');
    expect(session.status).toBe('ready');
    expect(http.clearCardDraft).toHaveBeenCalled();
    expect(useUserStore().me.id).toBe(42);
  });

  it('手机号被占：phone_taken 原样抛给弹层接', async () => {
    vi.mocked(authApi.apiSignup).mockRejectedValue(
      Object.assign(new Error('占用'), { code: 'phone_taken', status: 409 }),
    );
    const session = useSessionStore();
    await expect(session.signupWithCard({ phone: '13800001111' })).rejects.toMatchObject({ code: 'phone_taken' });
    expect(session.status).not.toBe('ready');
  });

  it('退出：服务端作废失败也不拦，本机恢复演示态', async () => {
    vi.mocked(authApi.apiLogout).mockRejectedValue(new Error('net'));
    const session = useSessionStore();
    session.$patch({ status: 'ready', account: view });
    useUserStore().users.me.id = 42;

    await session.logout();

    expect(session.status).toBe('guest');
    expect(session.account).toBeNull();
    expect(http.setToken).toHaveBeenCalledWith(null);
    const me = useUserStore().me;
    expect(me.id).toBe(demo.id);
    expect(me.name).toBe(demo.name);
    expect(me.chibi).toEqual(demo.chibi);
  });
});

describe('注销（4.6）', () => {
  it('验证通过后：清钥匙、恢复演示态', async () => {
    vi.mocked(authApi.apiDeactivate).mockResolvedValue();
    const session = useSessionStore();
    session.$patch({ status: 'ready', account: view });

    await session.deactivateAccount('13800001111', '123456');

    expect(session.status).toBe('guest');
    expect(useUserStore().me.name).toBe(demo.name);
  });

  it('验证码错：错误上抛，不降级身份', async () => {
    vi.mocked(authApi.apiDeactivate).mockRejectedValue(
      Object.assign(new Error('码不对'), { code: 'sms_bad_code', status: 400 }),
    );
    const session = useSessionStore();
    session.$patch({ status: 'ready', account: view });

    await expect(session.deactivateAccount('13800001111', '000000')).rejects.toMatchObject({ code: 'sms_bad_code' });
    expect(session.status).toBe('ready');
  });
});

describe('改名片（A3）', () => {
  it('登录态走云端并回接视图', async () => {
    const updated = { ...view, name: '亮马河快攻' };
    vi.mocked(authApi.apiUpdateProfile).mockResolvedValue({ account: updated });
    const session = useSessionStore();
    session.$patch({ status: 'ready', account: view });

    await session.saveProfile({ nickname: ' 亮马河快攻 ', chibi: view.chibi, card_bg: 'gold' });

    expect(authApi.apiUpdateProfile).toHaveBeenCalledWith(
      expect.objectContaining({ nickname: '亮马河快攻' }), // 去首尾空格
    );
    expect(useUserStore().me.name).toBe('亮马河快攻');
  });

  it('昵称为空：本地拦截，不发请求', async () => {
    const session = useSessionStore();
    session.$patch({ status: 'ready', account: view });
    await session.saveProfile({ nickname: '   ' });
    expect(authApi.apiUpdateProfile).not.toHaveBeenCalled();
  });

  it('游客态：本地演示保存，不触网', async () => {
    const session = useSessionStore();
    await session.saveProfile({ nickname: '路人甲' });
    expect(authApi.apiUpdateProfile).not.toHaveBeenCalled();
    expect(useUserStore().me.name).toBe('路人甲');
    // 还原演示名，避免影响其他用例
    useUserStore().users.me.name = demo.name;
  });
});
