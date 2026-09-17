"""T022 client clock accounting mirrors."""

from __future__ import annotations

from sim.dmb.time.clock import ClockService


class FakeClockDriver:
    def __init__(self) -> None:
        self.pause_depth = 0
        self.focused = True
        self.accumulator = 0.0
        self.sequence = 0

    def open_pause(self) -> None:
        self.pause_depth += 1

    def close_pause(self) -> None:
        self.pause_depth = max(0, self.pause_depth - 1)

    def notify_focus(self, focused: bool) -> None:
        self.focused = focused
        self.accumulator = 0.0

    def tick(self, delta_ms: float, server: ClockService) -> int:
        if self.pause_depth > 0 or not self.focused:
            return 0
        self.accumulator += delta_ms
        advanced = 0
        while self.accumulator >= 100:
            self.accumulator -= 100
            self.sequence += 1
            advanced += server.request_advance(100, self.sequence)
        return advanced


def test_two_screens_one_close_still_paused() -> None:
    driver = FakeClockDriver()
    server = ClockService({"game_ms": 0, "residual_ms": 0, "pause_tokens": {}, "clock_sequence": 0})
    driver.open_pause()
    driver.open_pause()
    driver.close_pause()
    assert driver.tick(60000, server) == 0
    assert server.clock_view()["game_ms"] == 0


def test_sixty_second_focus_loss_advances_zero() -> None:
    driver = FakeClockDriver()
    server = ClockService({"game_ms": 0, "residual_ms": 0, "pause_tokens": {}, "clock_sequence": 0})
    driver.notify_focus(False)
    assert driver.tick(60000, server) == 0
    driver.notify_focus(True)
    assert driver.tick(60000, server) == 600
    assert server.clock_view()["game_ms"] == 60000


def test_different_frame_patterns_identical_accounting() -> None:
    patterns = [[16, 16, 16, 16, 16, 20], [50, 50], [100], [1] * 100]
    results = []
    for pattern in patterns:
        driver = FakeClockDriver()
        server = ClockService({"game_ms": 0, "residual_ms": 0, "pause_tokens": {}, "clock_sequence": 0})
        for delta in pattern:
            driver.tick(delta, server)
        results.append(server.clock_view()["game_ms"])
    assert len(set(results)) == 1
