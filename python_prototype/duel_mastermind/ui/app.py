"""Minimal tkinter UI for sequential Human vs Bot — fast proof only."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

from duel_mastermind import CODE_LENGTH, NUM_COLOURS, GamePhase, SequentialDuelGame

COLOUR_NAMES = [
    "Flame", "Frost", "Storm", "Stone", "Light",
    "Shadow", "Vine", "Metal", "Spirit", "Arcane",
]
COLOUR_SYMBOLS = [
    "Fr", "Fs", "St", "Sn", "Li",
    "Sh", "Vi", "Me", "Sp", "Ar",
]
POINT_NAMES = ["Shield", "Body", "Staff", "Mind"]
COLOUR_HEX = [
    "#e6194b", "#4fc3f7", "#9e9e9e", "#795548", "#fff176",
    "#424242", "#66bb6a", "#b0bec5", "#ce93d8", "#7e57c2",
]


class DuelApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Duel Master Battle (Python prototype)")
        self.geometry("700x500")
        self.game = SequentialDuelGame(bot_seed=42)
        self._selected_slot: Optional[int] = None
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        self.status = ttk.Label(self, text="", font=("", 11))
        self.status.pack(pady=8)

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # Secret setup row
        ttk.Label(frame, text="Your secret code:").grid(row=0, column=0, sticky="w")
        self.secret_btns: List[tk.Button] = []
        for i in range(CODE_LENGTH):
            b = tk.Button(frame, text="?", width=4, command=lambda s=i: self._pick_secret(s))
            b.grid(row=0, column=i + 1, padx=2)
            self.secret_btns.append(b)
        self.lock_btn = ttk.Button(frame, text="Lock code", command=self._lock_secret, state=tk.DISABLED)
        self.lock_btn.grid(row=0, column=6, padx=8)

        # Colour picker
        ttk.Label(frame, text="Colours:").grid(row=1, column=0, sticky="w", pady=8)
        self.colour_frame = ttk.Frame(frame)
        self.colour_frame.grid(row=1, column=1, columnspan=6, sticky="w")
        for c in range(NUM_COLOURS):
            btn = tk.Button(
                self.colour_frame, text=str(c), bg=COLOUR_HEX[c], fg="white" if c == 9 else "black",
                width=3, command=lambda col=c: self._select_colour(col),
            )
            btn.grid(row=c // 5, column=c % 5, padx=2, pady=2)

        # Bot guess board
        ttk.Label(frame, text="Bot guesses:").grid(row=2, column=0, sticky="nw", pady=8)
        self.bot_board = tk.Text(frame, height=14, width=50, state=tk.DISABLED)
        self.bot_board.grid(row=2, column=1, columnspan=6, sticky="w")

        # Human guess row
        ttk.Label(frame, text="Your guess:").grid(row=3, column=0, sticky="w", pady=8)
        self.guess_btns: List[tk.Button] = []
        for i in range(CODE_LENGTH):
            b = tk.Button(frame, text="?", width=4, command=lambda s=i: self._pick_guess(s))
            b.grid(row=3, column=i + 1, padx=2)
            self.guess_btns.append(b)
        self.submit_btn = ttk.Button(frame, text="Submit guess", command=self._submit_guess, state=tk.DISABLED)
        self.submit_btn.grid(row=3, column=6, padx=8)

        self.restart_btn = ttk.Button(self, text="New game", command=self._new_game)
        self.restart_btn.pack(pady=8)

    def _pick_secret(self, slot: int) -> None:
        if self.game.phase != GamePhase.HUMAN_SETUP:
            return
        self._selected_slot = slot
        self._mode = "secret"

    def _pick_guess(self, slot: int) -> None:
        if self.game.phase != GamePhase.HUMAN_TURN:
            return
        self._selected_slot = slot
        self._mode = "guess"

    def _select_colour(self, colour: int) -> None:
        if self._selected_slot is None:
            return
        if getattr(self, "_mode", "") == "secret":
            self.game.set_human_secret_peg(self._selected_slot, colour)
        elif getattr(self, "_mode", "") == "guess":
            self.game.set_human_guess_peg(self._selected_slot, colour)
        self._selected_slot = None
        self._refresh()

    def _lock_secret(self) -> None:
        self.game.lock_human_secret()
        self._refresh()

    def _submit_guess(self) -> None:
        self.game.submit_human_guess()
        if self.game.phase == GamePhase.BOT_TURN:
            self.game.bot_make_guess()
        self._refresh()

    def _new_game(self) -> None:
        self.game.reset()
        self._refresh()

    def _refresh(self) -> None:
        g = self.game
        phase_names = {
            GamePhase.HUMAN_SETUP: "Set your secret code (4 pegs)",
            GamePhase.HUMAN_TURN: f"Your turn ({g.human_guesses_remaining} left)",
            GamePhase.BOT_TURN: "Bot is attacking...",
            GamePhase.FINISHED: "Game over",
        }
        self.status.config(text=phase_names.get(g.phase, ""))

        # Secret pegs
        for i, btn in enumerate(self.secret_btns):
            if g.phase == GamePhase.HUMAN_SETUP:
                c = g.human_setup_pegs[i]
                btn.config(text=str(c) if c is not None else "?", state=tk.NORMAL)
            else:
                btn.config(text="****", state=tk.DISABLED)

        self.lock_btn.config(state=tk.NORMAL if g.can_lock_human_secret() else tk.DISABLED)

        # Bot board
        self.bot_board.config(state=tk.NORMAL)
        self.bot_board.delete("1.0", tk.END)
        for i, rec in enumerate(g.bot_guesses):
            self.bot_board.insert(tk.END, f"{i+1}: {rec.guess}  exact={rec.exact} colour={rec.colour_only}\n")
        if g.phase != GamePhase.HUMAN_SETUP:
            solved = any(r.exact == CODE_LENGTH for r in g.bot_guesses)
            if solved:
                n = len(g.bot_guesses)
                self.bot_board.insert(tk.END, f"\nBot SOLVED in {n} guesses!\n")
        self.bot_board.config(state=tk.DISABLED)

        # Human guess
        guess_active = g.phase == GamePhase.HUMAN_TURN
        for i, btn in enumerate(self.guess_btns):
            c = g.current_human_guess[i] if guess_active else None
            btn.config(text=str(c) if c is not None else "?", state=tk.NORMAL if guess_active else tk.DISABLED)
        self.submit_btn.config(state=tk.NORMAL if g.can_submit_human_guess() else tk.DISABLED)

        # Human guess history in bot board area
        if g.human_guesses:
            self.bot_board.config(state=tk.NORMAL)
            self.bot_board.insert(tk.END, "\nYour guesses:\n")
            for i, rec in enumerate(g.human_guesses):
                self.bot_board.insert(tk.END, f"{i+1}: {rec.guess}  exact={rec.exact} colour={rec.colour_only}\n")
            self.bot_board.config(state=tk.DISABLED)

        if g.phase == GamePhase.FINISHED and g.result:
            messagebox.showinfo("Result", g.result.message)


def main() -> None:
    app = DuelApp()
    app.mainloop()


if __name__ == "__main__":
    main()
