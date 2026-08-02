"""Quick console smoke test for game_logic.py — no pygame, no UI.

Runs a full game with the "human" auto-playing Solo every turn (so the
generator-based loop never blocks on real input) and prints round-by-round
progress plus final standings. Run with: python test_logic.py
"""

from game_logic import GameManager

FRAME_DT = 1 / 60  # simulate a 60fps loop


def main():
    game = GameManager(total_players=16, total_rounds=20, delay_between_rounds=0.05, seed=42)

    game.on_round_started.append(lambda r: print(f"\n--- Round {r} ---"))
    game.on_round_summary.append(
        lambda r, events, standings: print(
            f"Round {r} leader: {standings[0].name} ({standings[0].points} pts)"
        )
    )
    game.on_game_ended.append(lambda standings: print("\nGAME OVER"))

    frames = 0
    max_frames = 200_000  # safety cap so a logic bug can't hang the test forever
    while not game.is_game_over and frames < max_frames:
        if game.awaiting_human:
            game.submit_solo()
        game.update(FRAME_DT)
        frames += 1

    assert game.is_game_over, "game did not finish within the frame cap — check for an infinite yield loop"

    standings = sorted(game.players, key=lambda p: p.points, reverse=True)
    print(f"\nRan {frames} frames across {game.total_rounds} rounds.\n")
    print(f"{'Rank':<5}{'Name':<10}{'Points':<8}{'Conns':<7}{'Zone'}")
    for i, p in enumerate(standings, start=1):
        from game_logic import get_zone_name
        print(f"{i:<5}{p.name:<10}{p.points:<8}{p.connection_count:<7}{get_zone_name(p.connection_count)}")

    human = game.human
    print(f"\nYou ({human.name}): {human.points} pts, {human.connection_count} connections")
    winner = standings[0]
    print(f"Winner: {winner.name} with {winner.points} pts")

    # Basic sanity checks
    assert all(p.points != 0 or p.connection_count == 0 for p in game.players)
    assert len(standings) == 16
    print("\nAll sanity checks passed.")


if __name__ == "__main__":
    main()
