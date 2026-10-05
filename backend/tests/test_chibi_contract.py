"""chibi 六部件变体数的前后端契约对拍（唯一一处跨栈字段级数值约定）。

前端真值在 frontend/src/utils/chibi.ts 的 DRESS_RANGES（变体渲染取模用它），
后端真值在 services/accounts.py 的 CHIBI_RANGES（建号/改名片校验用它）。
两边没有共享模块，靠本测试盯住：任何一侧改数字，这里立刻红。
"""

import re
from pathlib import Path

from app.services.accounts import CHIBI_RANGES

TS_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "chibi.ts"


def _parse_ts_ranges() -> dict[str, int]:
    src = TS_PATH.read_text(encoding="utf-8")
    m = re.search(r"DRESS_RANGES[^=]*=\s*\{([^}]*)\}", src)
    assert m, "frontend chibi.ts 里找不到 DRESS_RANGES"
    out: dict[str, int] = {}
    for part in m.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        k, v = part.split(":")
        out[k.strip()] = int(v.strip())
    return out


def test_chibi_ranges_match_frontend():
    assert CHIBI_RANGES == _parse_ts_ranges()
