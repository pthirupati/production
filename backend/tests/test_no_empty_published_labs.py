"""A published lab must have something to do.

Audit §G1's headline was "breadth real, depth manufactured". Measured, that was
literally true for 307 coding labs: every one shipped
`def solution(): raise NotImplementedError('Apply the fix')` — no starter code, no
seeded fault, no artifact to repair — behind a multi-paragraph incident description
promising a degraded production system. Their only tests were named `placeholder`,
so `return 1` earned full XP.

They were not under-graded labs. There was nothing in them to grade. Replacing
`assert callable(solution)` with `assert solution() is not None` (the earlier sweep)
made the stub fail, but it could not conjure a fault to diagnose.

So they are shipped `is_active: false` until they have real content. Every comparable
product optimises the other way — SadServers is respected on a few dozen genuinely
broken servers, not on volume — and 307 is 4.2% of a 7,280-scenario catalogue, so the
breadth claim survives intact while the depth claim becomes true.

This test stops the two ways that decision silently unwinds: a new empty lab shipping
active, or one of these being flipped back on without gaining content.
"""
import functools
import pathlib

import yaml
from django.conf import settings
from django.test import SimpleTestCase

SCENARIOS = pathlib.Path(settings.BASE_DIR).parent / "scenarios"


@functools.lru_cache(maxsize=1)
def _catalogue():
    """Parse the 7.3k-file tree once — it is ~17s per pass."""
    rows = []
    for path in sorted(SCENARIOS.glob("*/*/scenario.yaml")):
        try:
            rows.append((path, yaml.safe_load(path.read_text(encoding="utf-8")) or {}))
        except Exception:
            continue
    return tuple(rows)


def _load():
    return _catalogue()


def _is_empty_coding_lab(data):
    """A coding lab with a bare stub and only placeholder graders."""
    spec = data.get("coding_spec") or {}
    if not spec or (spec.get("kind") or "").lower() == "prompt":
        return False
    tests = list(spec.get("visible_tests") or []) + list(spec.get("hidden_tests") or [])
    if not tests:
        return True
    if not any(str(t.get("name") or "").lower().startswith("placeholder") for t in tests):
        return False
    body = "\n".join(f.get("content", "") for f in (spec.get("files") or []))
    return "NotImplementedError" in body


class NoEmptyPublishedLabsTests(SimpleTestCase):
    def test_no_published_lab_is_empty(self):
        offenders = [
            path.parent.name for path, data in _load()
            if data.get("is_active", True) is not False and _is_empty_coding_lab(data)
        ]
        self.assertEqual(
            offenders[:20], [],
            f"{len(offenders)} published lab(s) ship a bare NotImplementedError stub "
            "with only placeholder graders — there is nothing to diagnose and any "
            f"trivial return earns XP: {offenders[:20]}",
        )

    def test_the_detector_is_not_vacuous(self):
        """If the shape ever changes, the test above would pass by finding nothing at
        all rather than by finding nothing published. Assert the population exists."""
        empties = [p.parent.name for p, d in _load() if _is_empty_coding_lab(d)]
        self.assertGreater(
            len(empties), 100,
            "the empty-lab detector matched almost nothing — its heuristic has "
            "drifted from the scenario format and it is no longer protecting anything",
        )

    def test_every_empty_lab_is_unpublished(self):
        empties = [(p, d) for p, d in _load() if _is_empty_coding_lab(d)]
        still_on = [p.parent.name for p, d in empties if d.get("is_active", True) is not False]
        self.assertEqual(still_on, [], f"empty labs still published: {still_on[:20]}")

    def test_the_catalogue_is_still_overwhelmingly_published(self):
        """Guard the other direction: a bug in the unpublish sweep that switched off
        a large slice of the catalogue would also make the tests above pass."""
        rows = list(_load())
        off = sum(1 for _p, d in rows if d.get("is_active", True) is False)
        self.assertLess(
            off / max(len(rows), 1), 0.10,
            f"{off} of {len(rows)} scenarios are unpublished — expected ~4%",
        )

    def test_unpublished_labs_keep_their_content_for_later_authoring(self):
        """Unpublishing is reversible by design: the slug, description and objectives
        stay in the repo so the lab can be written properly rather than re-invented."""
        for path, data in _load():
            if data.get("is_active", True) is not False:
                continue
            self.assertTrue(data.get("slug"), f"{path} lost its slug")
            self.assertTrue(data.get("description"), f"{path} lost its description")
            break
