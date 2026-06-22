"""Data model for the public Tutorials section.

A Tutorial is a self-contained, SEO-friendly written guide (Linux, Git, Docker,
…). Each Tutorial owns an ordered list of TutorialSection rows (the steps). All
prose is ORIGINAL content authored for FixitLab and seeded via the
``seed_tutorials`` management command — nothing is copied from any third party.

The model intentionally stores content as data (not hard-coded React) so the
catalogue can grow over time without code changes, mirroring how BlogPost and
the question_bank already work.
"""

from django.db import models
from django.utils.text import slugify


class Tutorial(models.Model):
    """A single written tutorial, surfaced at /tutorials/<slug>."""

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    slug = models.SlugField(max_length=255, unique=True, blank=True)
    title = models.CharField(max_length=200)
    # Short one-line tagline shown on cards and as the meta description seed.
    summary = models.CharField(max_length=300, blank=True)
    # Free-text topic label used for grouping/filtering on the index
    # (e.g. "Linux", "Git", "Docker", "Kubernetes", "Python", "Bash",
    # "PostgreSQL", "Ansible"). Kept as a string (not an FK) so a tutorial can
    # exist before any matching Technology row does.
    topic = models.CharField(max_length=60, db_index=True)
    difficulty = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default="beginner"
    )
    estimated_minutes = models.PositiveIntegerField(default=10)

    # ── Call-to-action wiring ────────────────────────────────────────────────
    # Slug of the public playground to deep-link the "Try it" CTA
    # (e.g. "linux", "python", "docker"). Empty = no playground CTA.
    playground_slug = models.CharField(max_length=60, blank=True)
    # Slug of a matching question_bank Scenario to deep-link "Start a lab".
    # Stored as a plain string so the tutorial seeding never depends on a
    # particular scenario existing. Empty = no scenario CTA.
    scenario_slug = models.CharField(max_length=255, blank=True)

    # ── SEO ──────────────────────────────────────────────────────────────────
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    # Comma-separated keywords for the <meta name="keywords"> tag.
    seo_keywords = models.CharField(max_length=320, blank=True)

    is_published = models.BooleanField(default=True)
    # Lower numbers sort first on the index.
    order = models.PositiveIntegerField(default=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "title"]
        indexes = [
            models.Index(fields=["is_published", "order"]),
            models.Index(fields=["topic", "is_published"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:255]
        super().save(*args, **kwargs)

    @property
    def meta_description(self) -> str:
        return self.seo_description or self.summary

    @property
    def meta_title(self) -> str:
        return self.seo_title or self.title


class TutorialSection(models.Model):
    """One ordered step/section within a Tutorial.

    ``body`` is Markdown-ish prose (paragraphs separated by blank lines). The
    optional ``code`` block is rendered verbatim in a syntax-highlighted box
    with ``code_language`` as the hint.
    """

    tutorial = models.ForeignKey(
        Tutorial, related_name="sections", on_delete=models.CASCADE
    )
    order = models.PositiveIntegerField(default=0)
    heading = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    code = models.TextField(blank=True)
    code_language = models.CharField(max_length=30, blank=True, default="bash")
    # Short caption shown beneath the code block (e.g. "Expected output").
    code_caption = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("tutorial", "order")]

    def __str__(self):
        return f"{self.tutorial.slug} · {self.order}. {self.heading}"
