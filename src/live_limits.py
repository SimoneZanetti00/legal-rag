"""Limits of the public live demo (python -m src.web_demo --public).

A public page must not let visitors spend the owner's API credit without bound. LiveGate decides,
before each question, whether it may be answered, and counts it if so:

- per visitor: at most `per_visitor_hour` questions in any rolling hour, and `per_visitor_day`
  in a UTC calendar day;
- all visitors together: at most `global_day` questions per UTC day;
- spend: at most `spend_usd_day` US dollars per UTC day, from the token usage the API reports for
  every reply (llm.usage_cost). A question is refused when the spend so far today plus the cost
  of the most expensive question so far today (at least `question_reserve_usd`) could exceed the
  cap, so that one more question cannot carry the day far past it.

A visitor is the keyed hash of a client address that web_demo passes in; no address and no question
is kept. The counters live in memory: a restart of the server resets them. The hard backstop is the
monthly spend limit set in the Anthropic console.
"""

from __future__ import annotations

import datetime
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

HOUR = 3600.0


@dataclass(frozen=True)
class Limits:
    per_visitor_hour: int = 3
    per_visitor_day: int = 10
    global_day: int = 40
    spend_usd_day: float = 1.50
    question_reserve_usd: float = 0.10  # the assumed cost of a question before one is measured
    max_question_chars: int = 300

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LIMITS = Limits()


@dataclass(frozen=True)
class Refusal:
    code: str  # visitor_hourly_limit | visitor_daily_limit | global_daily_limit | daily_spend_cap
    message: str


class LiveGate:
    """The limits above, for one server process. Thread-safe; `clock` returns Unix seconds."""

    def __init__(self, limits: Limits = LIMITS, *, clock: Callable[[], float] = time.time) -> None:
        self.limits = limits
        self._clock = clock
        self._lock = threading.Lock()
        self._day: str | None = None
        self._asked: dict[str, list[float]] = {}  # visitor -> times of today's admitted questions
        self._questions = 0
        self._spent = 0.0
        self._largest = 0.0

    def _today(self) -> str:
        """The current UTC day; a new day starts every counter again."""
        day = datetime.datetime.fromtimestamp(self._clock(), datetime.UTC).date().isoformat()
        if day != self._day:
            self._day, self._asked, self._questions, self._spent, self._largest = (
                day, {}, 0, 0.0, 0.0)
        return day

    def admit(self, visitor: str) -> Refusal | None:
        """A Refusal if a question from `visitor` may not be answered now; otherwise None, and the
        question is counted for the visitor and for the day."""
        with self._lock:
            self._today()
            now, limits = self._clock(), self.limits
            if self._spent + max(self._largest, limits.question_reserve_usd) > limits.spend_usd_day:
                return Refusal("daily_spend_cap",
                               f"The live demo has reached its daily spending limit "
                               f"(${limits.spend_usd_day:.2f}). It starts again tomorrow (UTC).")
            if self._questions >= limits.global_day:
                return Refusal("global_daily_limit",
                               f"The live demo has answered its {limits.global_day} questions for "
                               "today. It starts again tomorrow (UTC).")
            asked = self._asked.setdefault(visitor, [])
            if len(asked) >= limits.per_visitor_day:
                return Refusal("visitor_daily_limit",
                               f"You have asked {limits.per_visitor_day} questions today, the most "
                               "this demo allows each visitor in a day (UTC).")
            if sum(1 for t in asked if now - t < HOUR) >= limits.per_visitor_hour:
                return Refusal("visitor_hourly_limit",
                               f"You have asked {limits.per_visitor_hour} questions in the last "
                               "hour, the most this demo allows each visitor. Please try again "
                               "later.")
            asked.append(now)
            self._questions += 1
            return None

    def spend(self, cost_usd: float) -> None:
        """Count what one question cost (the API's reported usage, priced), even if it failed."""
        with self._lock:
            self._today()
            self._spent += max(cost_usd, 0.0)
            self._largest = max(self._largest, cost_usd)

    def today(self) -> dict[str, Any]:
        """The day's totals, for the server log (no visitor information)."""
        with self._lock:
            return {"day": self._today(), "questions": self._questions,
                    "spent_usd": round(self._spent, 4)}
