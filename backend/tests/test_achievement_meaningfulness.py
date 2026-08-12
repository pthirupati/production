"""Audit Z3-11 — two badges that did not mean what they said.

**Perfect Score.** Awarded on `score >= 100`. `compute_score` returns
`max(10, 100 + time_bonus - hint_penalty)`, so 100 is the *floor* for a clean
solve, not a ceiling — every hint-free completion earned it, and plenty of
hinted ones did too once the time bonus covered the penalty. It also overlapped
exactly with `no_hints`, which already existed. A badge everyone has is not a
badge.

**Streak badges.** `_check_streaks` called `UserAchievement.objects.get_or_create`
directly instead of the local `_award` helper, so streak badges were created but
never appended to `awarded` — they were the only achievements on the platform
that never notified the person who earned them. Silent, and invisible to any test
that only checked the row existed.

The tests below therefore assert on the *notification*, not just the row: the row
was always being written correctly, which is precisely why the bug survived.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.progress.models import UserAchievement, UserScenarioProgress
from apps.progress.services import (
    PERFECT_SCORE_MIN,
    check_achievements,
    compute_current_streak,
)
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="Linux", slug="linux")
        self.scenario = Scenario.objects.create(
            technology=self.tech, title="Disk full", slug="disk-full",
            difficulty="easy",
        )
        self.user = User.objects.create_user(
            username="ach", email="ach@example.com", password="Str0ng-Pass-1"
        )

    def _check(self, score=100, time_seconds=120, hints_used=0):
        return check_achievements(
            self.user, self.scenario, score, time_seconds, hints_used
        )


class PerfectScoreIsEarnableNotAutomaticTests(_Base):
    def test_a_bare_pass_does_not_earn_it(self):
        """100 is what `compute_score` floors a clean solve at, so this was the
        every-completion case."""
        self.assertNotIn("perfect_score", self._check(score=100, hints_used=0))

    def test_a_fast_hint_free_solve_earns_it(self):
        self.assertIn(
            "perfect_score", self._check(score=PERFECT_SCORE_MIN, hints_used=0)
        )

    def test_a_hinted_solve_never_earns_it_however_fast(self):
        """The time bonus could previously outrun the hint penalty and hand the
        badge to someone who used hints."""
        self.assertNotIn("perfect_score", self._check(score=195, hints_used=2))

    def test_it_is_distinct_from_no_hints(self):
        """If the two coincided, one of them is redundant."""
        awarded = self._check(score=100, hints_used=0)
        self.assertIn("no_hints", awarded)
        self.assertNotIn("perfect_score", awarded)

    def test_the_threshold_is_above_the_score_floor(self):
        """Guard the guard: a threshold of ≤100 restores the original bug while
        every other test here keeps passing."""
        self.assertGreater(
            PERFECT_SCORE_MIN, 100,
            "PERFECT_SCORE_MIN is at or below compute_score's floor, so every "
            "clean solve earns 'Perfect Score' again",
        )


class StreakBadgesNotifyTests(_Base):
    """The row was always written; only the notification was missing."""

    def _solve_on_days(self, days_ago_list):
        for d in days_ago_list:
            sc = Scenario.objects.create(
                technology=self.tech, title=f"S{d}", slug=f"s{d}", difficulty="easy",
            )
            p = UserScenarioProgress.objects.create(
                user=self.user, scenario=sc, completed=True
            )
            stamp = timezone.now() - timedelta(days=d)
            UserScenarioProgress.objects.filter(pk=p.pk).update(completed_at=stamp)

    def test_a_three_day_streak_is_detected(self):
        self._solve_on_days([0, 1, 2])
        self.assertGreaterEqual(compute_current_streak(self.user), 3)

    def test_a_streak_badge_is_returned_as_newly_awarded(self):
        self._solve_on_days([0, 1, 2])
        awarded = self._check()
        self.assertIn(
            "streak_3", awarded,
            "streak badges are still bypassing _award, so nothing notifies",
        )

    def test_a_streak_badge_actually_triggers_a_notification(self):
        self._solve_on_days([0, 1, 2])
        with mock.patch(
            "apps.notifications.tasks.notify_achievement_earned.delay"
        ) as notify:
            self._check()
        notified = {call.args[1] for call in notify.call_args_list}
        self.assertIn(
            "streak_3", notified,
            "the streak badge was awarded without telling the user",
        )

    def test_the_row_is_still_written(self):
        self._solve_on_days([0, 1, 2])
        self._check()
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.user, achievement="streak_3"
            ).exists()
        )

    def test_a_streak_badge_is_not_re_awarded(self):
        """Re-notifying on every solve for the rest of the streak would be worse
        than never notifying."""
        self._solve_on_days([0, 1, 2])
        self._check()
        self.assertNotIn("streak_3", self._check())

    def test_no_streak_means_no_streak_badge(self):
        """Guard the guard: awarding unconditionally would pass every test above."""
        self._solve_on_days([0])
        self.assertNotIn("streak_3", self._check())

    def test_a_broken_streak_does_not_award(self):
        """A gap must break it — days 0, 1 and 5 is a 2-day streak, not 3."""
        self._solve_on_days([0, 1, 5])
        self.assertNotIn("streak_3", self._check())

    def test_the_profile_mirror_still_happens(self):
        """`_check_streaks` also syncs the dashboard counters; the refactor to pass
        `award` in must not have dropped that."""
        self._solve_on_days([0, 1, 2])
        self._check()
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.profile.daily_streak, 3)
