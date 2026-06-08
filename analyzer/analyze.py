#!/usr/bin/env python3
"""
Chess game analyzer: PGN → CSV + JSON using Stockfish.

Usage:
    python analyze.py <pgn_file> [--stockfish-path <path>] [--depth <depth>]
                      [--username <name>] [--output-dir <dir>]
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import chess
import chess.pgn
import chess.engine


USERNAME_DEFAULT = "Stockton350"
DEPTH_DEFAULT = 15
MIN_LEGAL_MOVES = 3  # skip classification in near-forced positions

BLUNDER_THRESHOLD = 100
MISTAKE_THRESHOLD = 50
INACCURACY_THRESHOLD = 20

PHASE_OPENING_END = 10
PHASE_MIDDLEGAME_END = 25


def phase(move_number: int) -> str:
    if move_number <= PHASE_OPENING_END:
        return "opening"
    elif move_number <= PHASE_MIDDLEGAME_END:
        return "middlegame"
    return "endgame"


def cp_score(score: chess.engine.Score, board: chess.Board) -> int | None:
    """Return centipawn score from the perspective of the side to move, clamped."""
    if score.is_mate():
        return 1000 if score.mate() > 0 else -1000
    cp = score.score()
    return max(-1000, min(1000, cp))


def classify(cp_loss: int) -> str:
    if cp_loss >= BLUNDER_THRESHOLD:
        return "blunder"
    elif cp_loss >= MISTAKE_THRESHOLD:
        return "mistake"
    elif cp_loss >= INACCURACY_THRESHOLD:
        return "inaccuracy"
    return "good"


def opening_name(game: chess.pgn.Game) -> str:
    for key in ("Opening", "ECOName", "ECO"):
        val = game.headers.get(key, "")
        if val and val != "?":
            return val
    return "Unknown"


def analyze_game(game: chess.pgn.Game, game_id: int, username: str, engine: chess.engine.SimpleEngine, depth: int) -> list[dict]:
    white = game.headers.get("White", "")
    black = game.headers.get("Black", "")
    date = game.headers.get("Date", "????.??.??").replace("????", "").strip(".")
    result = game.headers.get("Result", "*")

    user_color = None
    if white.lower() == username.lower():
        user_color = "white"
    elif black.lower() == username.lower():
        user_color = "black"

    try:
        opponent_elo = int(game.headers.get("BlackElo" if user_color == "white" else "WhiteElo", 0))
    except ValueError:
        opponent_elo = 0

    rows = []
    board = game.board()
    node = game

    move_number = 0
    prev_score = None

    while node.variations:
        next_node = node.variations[0]
        move = next_node.move

        # fullmove number increments after Black's move; track ply
        is_white_move = board.turn == chess.WHITE
        if is_white_move:
            move_number += 1

        # Only analyze moves by the user's color
        player_color = "white" if is_white_move else "black"
        is_user_move = (player_color == user_color)

        legal_moves = list(board.legal_moves)

        # Score before the move (from perspective of side to move)
        info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
        score_before = info_before["score"].relative

        # Best move according to engine
        best_move_uci = info_before.get("pv", [move])[0]
        best_move_san = board.san(best_move_uci)

        # Apply the move
        board.push(move)

        # Score after (flip perspective to match side that just moved)
        info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
        score_after_relative = info_after["score"].relative
        # score_after from the POV of the player who just moved = negated score of side to move
        score_after_for_mover = chess.engine.PovScore(score_after_relative, board.turn).relative

        cp_before = cp_score(score_before, board)
        # after the move, board.turn flipped; score_after_relative is for NEW side to move
        # convert: cp_loss = cp_before - (−score_after_relative)
        cp_after_for_mover = -cp_score(score_after_relative, board)

        if cp_before is not None and cp_after_for_mover is not None:
            cp_loss = cp_before - cp_after_for_mover
            cp_loss = max(0, cp_loss)  # can't gain from your own move scoring perspective
        else:
            cp_loss = 0

        # Only record moves if we know user's color, and only for user's moves
        if is_user_move and user_color is not None and len(legal_moves) >= MIN_LEGAL_MOVES:
            try:
                board.pop()
                move_san = board.san(move)
                board.push(move)
            except Exception:
                move_san = move.uci()

            rows.append({
                "game_id": game_id,
                "date": date,
                "color": user_color,
                "opponent_elo": opponent_elo,
                "move_number": move_number,
                "phase": phase(move_number),
                "move_played": move_san,
                "best_move": best_move_san,
                "centipawn_loss": cp_loss,
                "classification": classify(cp_loss),
                "opening": opening_name(game),
                "result": result,
            })

        node = next_node

    return rows


def build_summary(all_rows: list[dict], games_meta: list[dict]) -> dict:
    wins = sum(1 for g in games_meta if g["user_result"] == "win")
    losses = sum(1 for g in games_meta if g["user_result"] == "loss")
    draws = sum(1 for g in games_meta if g["user_result"] == "draw")

    phase_cpl = defaultdict(list)
    blunders_by_phase = defaultdict(int)
    blunders_by_color = defaultdict(int)

    for row in all_rows:
        phase_cpl[row["phase"]].append(row["centipawn_loss"])
        if row["classification"] == "blunder":
            blunders_by_phase[row["phase"]] += 1
            blunders_by_color[row["color"]] += 1

    total_games = len(games_meta)

    avg_cpl_by_phase = {
        p: round(sum(v) / len(v), 1) if v else 0
        for p, v in phase_cpl.items()
    }

    blunders_total = sum(blunders_by_phase.values())

    # Opening stats
    opening_data = defaultdict(lambda: {"games": 0, "wins": 0, "total_cpl": 0, "moves": 0})
    for row in all_rows:
        op = row["opening"]
        opening_data[op]["games"] += 1  # counts moves; we normalize below
        opening_data[op]["total_cpl"] += row["centipawn_loss"]
        opening_data[op]["moves"] += 1

    # Per-game opening result — use games_meta
    opening_game = defaultdict(lambda: {"games": 0, "wins": 0})
    for g in games_meta:
        op = g["opening"]
        opening_game[op]["games"] += 1
        if g["user_result"] == "win":
            opening_game[op]["wins"] += 1

    worst_openings = []
    for op, stats in opening_data.items():
        if stats["moves"] == 0:
            continue
        avg_cpl = round(stats["total_cpl"] / stats["moves"], 1)
        og = opening_game.get(op, {"games": 1, "wins": 0})
        win_rate = round(og["wins"] / og["games"] * 100, 1) if og["games"] else 0
        worst_openings.append({
            "name": op,
            "games": og["games"],
            "win_rate": win_rate,
            "avg_cpl": avg_cpl,
        })
    worst_openings.sort(key=lambda x: x["avg_cpl"], reverse=True)

    accuracy_by_game = []
    game_rows = defaultdict(list)
    for row in all_rows:
        game_rows[row["game_id"]].append(row["centipawn_loss"])
    for g in games_meta:
        gid = g["game_id"]
        cpls = game_rows.get(gid, [])
        avg = round(sum(cpls) / len(cpls), 1) if cpls else 0
        # Chess.com-style accuracy approximation
        accuracy = round(max(0, 100 - avg * 0.5), 1)
        accuracy_by_game.append({
            "game_id": gid,
            "date": g["date"],
            "result": g["user_result"],
            "avg_cpl": avg,
            "accuracy": accuracy,
        })

    return {
        "total_games": total_games,
        "record": {"wins": wins, "losses": losses, "draws": draws},
        "avg_centipawn_loss": avg_cpl_by_phase,
        "blunder_frequency": {
            "total": blunders_total,
            "per_game": round(blunders_total / total_games, 2) if total_games else 0,
            "by_phase": dict(blunders_by_phase),
        },
        "blunder_by_color": dict(blunders_by_color),
        "worst_openings": worst_openings[:10],
        "accuracy_by_game": accuracy_by_game,
    }


def game_result_for_user(game: chess.pgn.Game, username: str) -> str:
    white = game.headers.get("White", "")
    black = game.headers.get("Black", "")
    result = game.headers.get("Result", "*")
    if result == "*":
        return "unknown"
    if white.lower() == username.lower():
        if result == "1-0":
            return "win"
        elif result == "0-1":
            return "loss"
        return "draw"
    elif black.lower() == username.lower():
        if result == "0-1":
            return "win"
        elif result == "1-0":
            return "loss"
        return "draw"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Analyze chess PGN with Stockfish")
    parser.add_argument("pgn_file", help="Path to PGN file")
    parser.add_argument("--stockfish-path", default="stockfish", help="Path to Stockfish binary")
    parser.add_argument("--depth", type=int, default=DEPTH_DEFAULT, help="Stockfish analysis depth")
    parser.add_argument("--username", default=USERNAME_DEFAULT, help="Your Chess.com username")
    parser.add_argument("--output-dir", default=".", help="Directory for output files")
    args = parser.parse_args()

    if not os.path.exists(args.pgn_file):
        print(f"Error: PGN file not found: {args.pgn_file}", file=sys.stderr)
        sys.exit(1)

    # Count games first for progress reporting
    games = []
    with open(args.pgn_file, encoding="utf-8", errors="replace") as f:
        while True:
            g = chess.pgn.read_game(f)
            if g is None:
                break
            games.append(g)

    print(f"Loaded {len(games)} games from {args.pgn_file}")
    print(f"Username: {args.username} | Depth: {args.depth}")

    try:
        engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
    except FileNotFoundError:
        print(f"Error: Stockfish not found at '{args.stockfish_path}'.", file=sys.stderr)
        print("Install Stockfish and ensure it's on your PATH, or use --stockfish-path.", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    games_meta = []

    CSV_FIELDS = [
        "game_id", "date", "color", "opponent_elo", "move_number",
        "phase", "move_played", "best_move", "centipawn_loss", "classification",
        "opening", "result",
    ]

    csv_path = os.path.join(args.output_dir, "analysis.csv")
    json_path = os.path.join(args.output_dir, "summary.json")

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
            writer.writeheader()

            for i, game in enumerate(games):
                print(f"  Game {i+1}/{len(games)}: {game.headers.get('White', '?')} vs {game.headers.get('Black', '?')} ({game.headers.get('Date', '?')})")

                try:
                    rows = analyze_game(game, i + 1, args.username, engine, args.depth)
                except Exception as e:
                    print(f"    Warning: skipped game {i+1} due to error: {e}")
                    rows = []

                for row in rows:
                    writer.writerow(row)
                all_rows.extend(rows)

                games_meta.append({
                    "game_id": i + 1,
                    "date": game.headers.get("Date", ""),
                    "opening": opening_name(game),
                    "user_result": game_result_for_user(game, args.username),
                })
    finally:
        engine.quit()

    summary = build_summary(all_rows, games_meta)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nDone.")
    print(f"  CSV:  {csv_path}  ({len(all_rows)} moves analyzed)")
    print(f"  JSON: {json_path}")
    print(f"  Record: {summary['record']['wins']}W / {summary['record']['losses']}L / {summary['record']['draws']}D")


if __name__ == "__main__":
    main()
