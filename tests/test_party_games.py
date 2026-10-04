"""Rule invariants for Party Pack 1 (no presentation claims)."""

from __future__ import annotations

import json

from PlayAtlas.games import (
    BlackjackGame,
    PrizeReelsGame,
    PrizeWheelGame,
    TankBattleGame,
    UnoGame,
    UpgradePokerGame,
)


def test_tank_battle_fixed_tick_hit_and_illegal_input() -> None:
    game = TankBattleGame(players=2, seed=4)
    assert not game.apply_action({"type": "move", "direction": "teleport"}, player_id=0).ok
    game.positions[1] = [2, 1]
    game.directions[0] = "right"
    assert game.apply_action({"type": "fire"}, player_id=0).ok
    assert game.fixed_update().ok
    assert game.scores == [1, 0]
    assert game.positions[1] == list(game.spawns[1])
    restored = TankBattleGame(players=2, seed=4)
    restored.load_state(json.loads(json.dumps(game.save_state())))
    assert restored.save_state() == game.save_state()


def test_uno_standard_deck_conservation_hidden_hands_and_wild_colour() -> None:
    game = UnoGame(players=4, seed=9)
    all_cards = list(game.draw_pile) + list(game.discard)
    for hand in game.hands:
        all_cards.extend(hand)
    assert len(all_cards) == 108
    assert len(game.hands[0]) == 7
    observation = game.get_observation(0)
    assert "hands" not in observation
    assert "hand" in observation and "hand_counts" in observation
    # Force a legal wild to cover the explicit colour-selection rule.
    game.hands[0] = [("wild", "wild")]
    game.current_player = 0
    assert not game.apply_action({"type": "play", "card": ["wild", "wild"]}).ok
    assert game.apply_action({"type": "play", "card": ["wild", "wild"], "color": "blue"}).ok
    assert game.winner == 0


def test_upgrade_follows_lead_and_finishes_with_two_deck_conservation() -> None:
    game = UpgradePokerGame(seed=3)
    cards = [card for hand in game.hands for card in hand] + list(game.kitty)
    assert len(cards) == 108 and len(set(cards)) == 108
    first = game.get_legal_actions(0)[0]
    assert game.apply_action(first, player_id=0).ok
    lead = game.lead_suit
    off_suit = next((card for card in game.hands[1] if game._effective_suit(card) != lead), None)
    followed = next((item for item in game.get_legal_actions(1) if tuple(item["card"]) != off_suit), None)
    if off_suit is not None:
        assert not game.apply_action({"type": "play", "card": list(off_suit)}, player_id=1).ok
    assert followed is not None
    assert game.apply_action(followed, player_id=1).ok
    # A real legal-action loop must consume all 100 hand cards.
    for _ in range(120):
        if game.is_finished():
            break
        action = game.get_legal_actions()[0]
        assert game.apply_action(action).ok
    assert game.status == "finished"
    assert sum(game.scores) >= 0


def test_blackjack_hides_dealer_hole_card_and_resolves_round() -> None:
    game = BlackjackGame(players=3, seed=8)
    observation = game.get_observation(0)
    assert "dealer_hand" not in observation
    assert observation["dealer_card_count"] == 2
    assert len(observation["dealer_visible"]) == 1
    current = game.current_player
    hit = game.apply_action({"type": "hit"}, player_id=current)
    assert hit.ok
    if hit.payload["value"] <= 21:
        assert game.current_player == current
    while not game.is_finished():
        actions = game.get_legal_actions()
        assert actions
        assert game.apply_action({"type": "stand"}, player_id=game.current_player).ok
    assert len(game.get_result()["outcomes"]) == 3


def test_probability_machines_are_score_only_and_seed_deterministic() -> None:
    reels_a, reels_b = PrizeReelsGame(seed=11, max_spins=3), PrizeReelsGame(seed=11, max_spins=3)
    wheel = PrizeWheelGame(seed=12, max_spins=2)
    for _ in range(3):
        reels_a.spin(); reels_b.spin()
    assert reels_a.last_result == reels_b.last_result
    assert reels_a.points >= 0
    wheel.spin(); wheel.spin()
    assert wheel.status == "finished" and wheel.points >= 0
    assert "cash" not in reels_a.get_result()
