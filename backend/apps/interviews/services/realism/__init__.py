"""Interview realism layer — free, deterministic, rule-based (no paid APIs).

P2.R* modules live here. Timing is the first shipped piece: human-like
think-time before interviewer replies so the call never feels synchronous.
"""

from apps.interviews.services.realism.timing import compute_thinking_delay_ms

__all__ = ["compute_thinking_delay_ms"]
