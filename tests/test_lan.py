"""Localhost protocol checks.  Real Wi-Fi/multi-device QA remains separate."""

from __future__ import annotations

import time

import pytest

from PlayAtlas.games import UnoGame
from PlayAtlas.network import LanClient, LanHost


def _ready_client(client: LanClient, timeout: float = 2.0) -> None:
    client.wait_for("welcome", timeout)
    client.send_ready(True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = client.poll(0.1)
        if message and message.get("type") == "lobby" and message.get("players", [{}])[0].get("ready"):
            return
    raise AssertionError("client did not receive ready lobby")


def test_lan_host_authority_hidden_observation_and_idempotent_retry() -> None:
    host = LanHost(game=UnoGame(players=2, seed=17), bind_host="127.0.0.1")
    try:
        try:
            host.start()
        except PermissionError:
            pytest.skip("sandbox disallows TCP sockets; run LAN smoke outside restricted mode")
        client = LanClient(player_name="测试玩家")
        try:
            client.connect("127.0.0.1", host.port)
            _ready_client(client)
            assert host.can_start()
            host.start_game()
            client.wait_for("started")
            snapshot = client.wait_for("snapshot")
            assert "observation" in snapshot
            assert "hands" not in snapshot["observation"]
            assert "hand" in snapshot["observation"]

            # Host advances player 0; the client is player 1 and can now act.
            assert host.submit_local_action(0, host.game.get_legal_actions(0)[0])["ok"]
            while client.poll(0.02) is not None:
                pass
            action = host.game.get_legal_actions(client.player_id)[0]
            request_id = client.send_action(action)
            result = client.wait_for("action_result")
            assert result["ok"] is True
            # A retry with a new transport sequence but the same request id is
            # replayed, not applied twice.
            client._send({"type": "action", "client_seq": 99, "request_id": request_id, "action": action})
            replay = client.wait_for("action_result")
            assert replay["request_id"] == request_id
            original_client_id, original_player_id = client.client_id, client.player_id
            client.close()
            # Reusing the stable identity restores the same seat instead of
            # creating a second player slot.
            reconnected = LanClient(client_id=original_client_id, player_name="重连玩家")
            try:
                reconnected.connect("127.0.0.1", host.port)
                welcome = reconnected.wait_for("welcome")
                assert welcome["player_id"] == original_player_id
            finally:
                reconnected.close()
        finally:
            client.close()
    finally:
        host.stop()
