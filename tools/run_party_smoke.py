#!/usr/bin/env python3
"""Run deterministic Party Pack rule and localhost protocol smoke checks."""

from __future__ import annotations

import json
import time

from PlayAtlas.games import BlackjackGame, PrizeReelsGame, TankBattleGame, UnoGame, UpgradePokerGame


def rule_smoke() -> dict[str, object]:
    tank = TankBattleGame(players=2, seed=4); tank.positions[1] = [2, 1]; tank.directions[0] = "right"; tank.apply_action({"type": "fire"}, 0); tank.fixed_update()
    uno = UnoGame(players=4, seed=9)
    for _ in range(600):
        if uno.is_finished(): break
        legal = uno.get_legal_actions()
        if not legal: raise AssertionError("UNO has no legal action")
        uno.apply_action(legal[0])
    upgrade = UpgradePokerGame(seed=3)
    for _ in range(120):
        if upgrade.is_finished(): break
        upgrade.apply_action(upgrade.get_legal_actions()[0])
    blackjack = BlackjackGame(players=2, seed=8)
    while not blackjack.is_finished():
        blackjack.apply_action({"type": "stand"}, blackjack.current_player)
    reels = PrizeReelsGame(seed=11, max_spins=3)
    for _ in range(3): reels.spin()
    return {"tank": tank.get_result(), "uno": uno.get_result(), "upgrade": upgrade.get_result(), "blackjack": blackjack.get_result(), "reels": reels.get_result()}


def lan_smoke() -> dict[str, object]:
    # Kept as a separate helper so restricted CI can still run rule smoke.
    from PlayAtlas.network import LanClient, LanHost
    host = LanHost(game=UnoGame(players=2, seed=17), bind_host="127.0.0.1")
    try:
        host.start(); client = LanClient(player_name="smoke")
        try:
            client.connect("127.0.0.1", host.port); client.wait_for("welcome")
            client.send_ready(True)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                message = client.poll(0.1)
                if message and message.get("type") == "lobby" and message.get("players", [{}])[0].get("ready"):
                    break
            host.start_game(); client.wait_for("started"); client.wait_for("snapshot")
            host.submit_local_action(0, host.game.get_legal_actions(0)[0])
            while client.poll(0.01) is not None: pass
            request = client.send_action(host.game.get_legal_actions(1)[0]); result = client.wait_for("action_result")
            return {"request_id": request, "ok": result.get("ok"), "player_id": client.player_id}
        finally:
            client.close()
    finally:
        host.stop()


def main() -> int:
    report = {"rules": rule_smoke()}
    try:
        report["lan"] = lan_smoke()
        report["lan_status"] = "localhost_pass"
    except PermissionError:
        report["lan_status"] = "blocked_tcp_socket_in_sandbox"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
