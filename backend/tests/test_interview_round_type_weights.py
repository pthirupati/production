"""Every real InterviewRound.round_type must have its own eval weights.

Regression guard for the audit finding that INTERVIEW_TYPE_CONFIGS only held the
five "extended" types (behavioral/system_design/live_coding/devops_debug/
sre_oncall) while the database only ever stores technical/manager/hr/deep_dive/
leadership. The two sets did not overlap at all, so get_eval_weights() fell
through to the technical defaults for 100% of real rounds — an HR round was
graded with 35% technical weight.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.interviews.models import InterviewRound
from apps.interviews.services.interview_types import (
    INTERVIEW_TYPE_CONFIGS,
    get_eval_weights,
)

# scoring.aggregate_round_scores only builds a real practical_score for these
# round types; anywhere else it falls back to the raw answer average, so giving
# practical_score weight there would double-count the overall score.
ROUND_TYPES_WITH_PRACTICAL_SIGNAL = {
    "technical",
    "live_coding",
    "devops_debug",
    "sre_oncall",
}

# Dimensions aggregate_round_scores actually emits.
KNOWN_DIMENSIONS = {
    "technical_score",
    "communication_score",
    "problem_solving_score",
    "practical_score",
    "presence_score",
    "resume_alignment_score",
}


class RoundTypeEvalWeightsTest(SimpleTestCase):
    def test_every_db_round_type_has_explicit_config(self):
        for round_type, _label in InterviewRound.ROUND_TYPES:
            self.assertIn(
                round_type,
                INTERVIEW_TYPE_CONFIGS,
                f"{round_type!r} is a real round type but has no eval config, "
                "so it silently inherits the technical defaults.",
            )

    def test_hr_round_is_not_graded_as_a_technical_round(self):
        hr = get_eval_weights("hr")
        technical = get_eval_weights("technical")
        self.assertNotEqual(hr, technical)
        # The concrete bug: 35% technical weight on an HR screen.
        self.assertLess(hr.get("technical_score", 0), 0.20)
        # HR is a communication screen, so communication must dominate.
        self.assertEqual(
            max(hr, key=hr.get),
            "communication_score",
            f"communication should be the heaviest HR dimension, got {hr}",
        )

    def test_manager_and_leadership_are_not_technical_defaults(self):
        technical = get_eval_weights("technical")
        for round_type in ("manager", "leadership"):
            weights = get_eval_weights(round_type)
            self.assertNotEqual(
                weights, technical, f"{round_type} still uses technical defaults"
            )
            self.assertLess(weights.get("technical_score", 0), 0.35)

    def test_deep_dive_still_weights_technical_depth_highest(self):
        weights = get_eval_weights("deep_dive")
        self.assertEqual(max(weights, key=weights.get), "technical_score")

    def test_all_weight_sets_are_normalized_and_use_known_dimensions(self):
        for round_type in INTERVIEW_TYPE_CONFIGS:
            weights = get_eval_weights(round_type)
            self.assertAlmostEqual(
                sum(weights.values()),
                1.0,
                places=6,
                msg=f"{round_type} weights must sum to 1.0, got {weights}",
            )
            unknown = set(weights) - KNOWN_DIMENSIONS
            self.assertFalse(
                unknown,
                f"{round_type} weights reference dimensions scoring never "
                f"emits: {unknown}",
            )

    def test_practical_score_only_weighted_where_it_is_computed(self):
        for round_type in INTERVIEW_TYPE_CONFIGS:
            weights = get_eval_weights(round_type)
            if weights.get("practical_score"):
                self.assertIn(
                    round_type,
                    ROUND_TYPES_WITH_PRACTICAL_SIGNAL,
                    f"{round_type} weights practical_score but "
                    "aggregate_round_scores never computes one for it.",
                )
