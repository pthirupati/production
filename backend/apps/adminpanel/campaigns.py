"""Campaign helpers: serialization, audience resolution, and social-post generation.

Social posting is intentionally FREE / no-paid-API: we never call LinkedIn,
Twitter/X or Reddit APIs. Instead we generate ready-to-paste post text plus
share-intent URLs so an admin can post manually in one click.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from django.conf import settings


def serialize_campaign(c, *, admin: bool = False) -> dict:
    """Serialize a Campaign. ``admin=True`` includes draft/internal fields."""
    data = {
        "id": str(c.id),
        "kind": c.kind,
        "title": c.title,
        "body": c.body,
        "media_type": c.media_type,
        "media_url": c.media_url,
        "placement": c.placement,
        "bg_color": c.bg_color,
        "text_color": c.text_color,
        "text_style": c.text_style or {},
        "cta_label": c.cta_label,
        "cta_url": c.cta_url,
        "audience": c.audience,
        "dismissible": c.dismissible,
        "starts_at": c.starts_at.isoformat() if c.starts_at else None,
        "ends_at": c.ends_at.isoformat() if c.ends_at else None,
    }
    if admin:
        data.update({
            "status": c.status,
            "is_live": c.is_live(),
            "created_by": getattr(c.created_by, "username", None),
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        })
    return data


def user_is_paid(user) -> bool:
    """Best-effort check whether a user has any paid/complimentary access."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    try:
        from apps.billing.subscription_utils import (
            active_tech_subscriptions_qs,
            user_has_complimentary_access,
        )

        if user_has_complimentary_access(user):
            return True
        return active_tech_subscriptions_qs(user).exists()
    except Exception:
        return False


def audience_matches(campaign_audience: str, user) -> bool:
    """Whether a campaign's audience targets this (possibly anonymous) user."""
    if campaign_audience == "all":
        return True
    paid = user_is_paid(user)
    if campaign_audience == "paid":
        return paid
    if campaign_audience == "free":
        return not paid
    return True


def active_campaigns_for(user, placement: str | None = None) -> list:
    """Return serialized, currently-live campaigns matching the user's audience.

    Safe by contract — callers rely on this never raising.
    """
    from .models import Campaign

    try:
        qs = Campaign.objects.filter(status="enabled")
        if placement:
            qs = qs.filter(placement=placement)
        out = []
        for c in qs.order_by("-created_at"):
            if not c.is_live():
                continue
            if not audience_matches(c.audience, user):
                continue
            out.append(serialize_campaign(c, admin=False))
        return out
    except Exception:
        return []


# ─── Social post generation (free, manual posting) ──────────────────────────

def _frontend_url() -> str:
    url = getattr(settings, "FRONTEND_URL", "") or "https://fixitlab.io"
    return url.rstrip("/")


def build_social_posts(campaign=None, *, current_features=None, upcoming_features=None) -> dict:
    """Generate ready-to-paste posts + share-intent links for LinkedIn/Twitter/Reddit.

    If ``campaign`` is given, its title/body seed the post. Otherwise a generic
    product update post is built from current + upcoming feature lists.
    """
    site = _frontend_url()
    current = current_features or []
    upcoming = upcoming_features or []

    if campaign is not None:
        headline = campaign.title
        intro = campaign.body or "We just shipped something new on FixitLab."
        link = campaign.cta_url or site
        if link and link.startswith("/"):
            link = f"{site}{link}"
    else:
        headline = "What's new on FixitLab"
        intro = "Hands-on labs for real DevOps & SRE troubleshooting — here's the latest."
        link = site

    def _bullets(items, bullet="•"):
        return "\n".join(f"{bullet} {i}" for i in items if i)

    # Twitter/X — short, hashtag-friendly (~280 chars target)
    tw_lines = [f"🚀 {headline}", ""]
    if current:
        tw_lines.append("Now live:")
        tw_lines.append(_bullets(current[:3]))
    if upcoming:
        tw_lines.append("")
        tw_lines.append("Coming soon:")
        tw_lines.append(_bullets(upcoming[:2]))
    tw_lines += ["", f"Try it 👉 {link}", "#DevOps #SRE #Homelab #FixitLab"]
    twitter_text = "\n".join([l for l in tw_lines if l is not None]).strip()

    # LinkedIn — longer, professional
    li_lines = [f"🚀 {headline}", "", intro, ""]
    if current:
        li_lines += ["✅ Available now:", _bullets(current), ""]
    if upcoming:
        li_lines += ["🔭 On the roadmap:", _bullets(upcoming), ""]
    li_lines += [
        "FixitLab gives engineers safe, real-world break/fix labs to practice "
        "troubleshooting Linux, Kubernetes, VMware, cloud and more.",
        "",
        f"👉 {link}",
        "",
        "#DevOps #SRE #Kubernetes #Linux #CloudComputing #CareerGrowth",
    ]
    linkedin_text = "\n".join(li_lines).strip()

    # Reddit — title + self-text body, conversational, low-spam
    reddit_title = f"{headline} — free hands-on DevOps/SRE troubleshooting labs"
    rd_lines = [intro, ""]
    if current:
        rd_lines += ["**What's live now:**", _bullets(current, bullet="-"), ""]
    if upcoming:
        rd_lines += ["**What's coming:**", _bullets(upcoming, bullet="-"), ""]
    rd_lines += [f"Check it out: {link}", "", "Happy to answer questions / take feedback."]
    reddit_text = "\n".join(rd_lines).strip()

    # Share-intent links (no API/auth needed)
    twitter_intent = "https://twitter.com/intent/tweet?" + urlencode({
        "text": twitter_text,
    })
    # LinkedIn's share dialog only accepts a URL (text must be pasted manually).
    linkedin_share = "https://www.linkedin.com/sharing/share-offsite/?" + urlencode({
        "url": link,
    })
    reddit_submit = "https://www.reddit.com/submit?" + urlencode({
        "title": reddit_title,
        "text": reddit_text,
    })

    return {
        "link": link,
        "twitter": {
            "text": twitter_text,
            "share_url": twitter_intent,
            "char_count": len(twitter_text),
        },
        "linkedin": {
            "text": linkedin_text,
            "share_url": linkedin_share,
            "note": "LinkedIn does not allow pre-filling post text — copy the text, then paste it into the share box that opens.",
        },
        "reddit": {
            "title": reddit_title,
            "text": reddit_text,
            "share_url": reddit_submit,
        },
    }
