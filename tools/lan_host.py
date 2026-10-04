#!/usr/bin/env python3
"""Start a small PlayAtlas LAN room for local testing.

This is a development/acceptance helper, not an online service.  It binds a
single local-room host, prints the port to share on the same LAN, and exits on
Ctrl+C.  No account, discovery backend, or remote download is involved.
"""

from __future__ import annotations

import argparse
import time

from PlayAtlas.network import LanHost


def main() -> int:
    parser = argparse.ArgumentParser(description="PlayAtlas offline LAN room host")
    parser.add_argument("--game", default="uno", choices=("gomoku", "reversi", "crazy_eights", "tank_battle", "uno", "upgrade_poker", "blackjack"))
    parser.add_argument("--players", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=27800)
    args = parser.parse_args()
    host = LanHost(game_id=args.game, players=args.players, seed=args.seed, bind_host=args.bind, port=args.port)
    try:
        address = host.start()
        print(f"PlayAtlas LAN room: {address[0]}:{address[1]}  game={args.game}")
        print("等待客户端加入；按 Ctrl+C 结束。房主权威规则引擎运行在本进程。")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在关闭 LAN 房间。")
    finally:
        host.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
