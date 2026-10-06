"""games 路由 —— 局簿的 HTTP 面（读链 + 报名/退局/改局）：纯参数搬运，规则全在 GameBook。

响应约定同 auth：成功体直接是 game_view（或其列表）；失败体 {"error": {code, message}}。
时间进出 ISO 8601 +08:00，换算在服务层（契约§2）。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db.models import Account
from ...services.games import GameBook
from ..deps import current_account, get_game_book, require_account

router = APIRouter(prefix="/games", tags=["games"])


class PublishIn(BaseModel):
    """发局表单（4.1）。deadline 只在这里出现——没有任何修改入口（不变承诺 3）。"""

    name: str | None = None
    start_at: datetime
    end_at: datetime
    deadline_at: datetime
    venue_name: str
    venue_address: str | None = None
    min_players: int
    max_players: int
    visibility: str
    scoring: int
    rotation: str
    score_rule: str


class JoinIn(BaseModel):
    """报名表单（4.3）：带几个人 0-3，缺省 0（自己占 1 坑）。"""

    bring: int = 0


class EditIn(BaseModel):
    """改局表单（4.6）：全 Optional——None 参沿用原值；deadline 不在表上
    （截止发布即定死，不变承诺 3）。"""

    name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    visibility: str | None = None
    scoring: int | None = None
    rotation: str | None = None
    score_rule: str | None = None


@router.post("")
def publish_game(
    body: PublishIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    return book.publish(
        organizer_id=account.id,
        name=body.name,
        start_at=body.start_at,
        end_at=body.end_at,
        deadline_at=body.deadline_at,
        venue_name=body.venue_name,
        venue_address=body.venue_address,
        min_players=body.min_players,
        max_players=body.max_players,
        visibility=body.visibility,
        scoring=body.scoring,
        rotation=body.rotation,
        score_rule=body.score_rule,
    )


@router.get("")
def list_games(
    account: Account | None = Depends(current_account),
    book: GameBook = Depends(get_game_book),
):
    """找局打列表：可匿名（匿名只翻得到 public）；懒判定与三档过滤在 book。"""
    return book.list_for(viewer_id=account.id if account else None)


# /mine 必须先于 /{game_id} 声明：FastAPI 按声明序匹配，否则 "mine" 被当成 id
@router.get("/mine")
def my_games(
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    return book.mine(account_id=account.id)


@router.get("/{game_id}")
def game_detail(
    game_id: int,
    account: Account | None = Depends(current_account),
    book: GameBook = Depends(get_game_book),
):
    """局详情：链接即门票——匿名可看、档位不拦（4.2/4.5）。"""
    return book.detail(game_id=game_id, viewer_id=account.id if account else None)


@router.post("/{game_id}/join")
def join_game(
    game_id: int,
    body: JoinIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """报名（4.3/4.14）：整行进出、满员落候补、截止后照常可加、重复提交幂等。"""
    return book.join(game_id=game_id, account_id=account.id, bring=body.bring)


@router.post("/{game_id}/quit")
def quit_game(
    game_id: int,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """退局（4.4）：截止锁退出、改约解锁窗可退、幂等。"""
    return book.quit(game_id=game_id, account_id=account.id)


@router.post("/{game_id}/edit")
def edit_game(
    game_id: int,
    body: EditIn,
    account: Account = Depends(require_account),
    book: GameBook = Depends(get_game_book),
):
    """改局（4.6）：只有组织者、开打前；上限调整与改约解锁在 book。"""
    return book.edit(game_id=game_id, organizer_id=account.id, **body.model_dump())
