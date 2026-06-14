from django.db import migrations
from django.utils import timezone


POSTS = [
    {
        "slug": "teams-coupons-and-security",
        "title": "Teams, Coupons, and Platform Security — What's New",
        "excerpt": "Enterprise seat licensing, checkout coupon codes, admin security dashboards, and community threads with screenshot attachments.",
        "content": "Enterprise teams can now purchase seat licenses, apply coupon codes at checkout, and use the expanded admin security dashboard. Community threads support screenshot attachments for faster troubleshooting.",
        "author_name": "Platform Team",
        "category": "Product",
        "read_minutes": 4,
    },
    {
        "slug": "why-hands-on-learning-works",
        "title": "Why Hands-On Learning Works Better Than Reading Docs",
        "excerpt": "Studies show engineers retain 75% of what they practice compared to 10% of what they read.",
        "content": "Hands-on practice dramatically improves retention. FixitLab drops you into real broken environments so you investigate, hypothesize, fix, and validate — the same loop used in production incident response.",
        "author_name": "Thirupathi P.",
        "category": "Education",
        "read_minutes": 5,
    },
    {
        "slug": "debugging-nginx-like-a-pro",
        "title": "Debugging Nginx Like a Pro: A Step-by-Step Guide",
        "excerpt": "Learn the systematic approach SREs use to diagnose Nginx configuration issues.",
        "content": "Start with error logs, validate config syntax, trace upstream connectivity, and verify listeners. FixitLab Nginx scenarios walk through each step in a live environment.",
        "author_name": "Platform Team",
        "category": "Linux",
        "read_minutes": 8,
    },
]


def seed_posts(apps, schema_editor):
    BlogPost = apps.get_model("adminpanel", "BlogPost")
    now = timezone.now()
    for i, post in enumerate(POSTS):
        BlogPost.objects.update_or_create(
            slug=post["slug"],
            defaults={
                **post,
                "is_published": True,
                "published_at": now - timezone.timedelta(days=len(POSTS) - i),
            },
        )


def unseed(apps, schema_editor):
    BlogPost = apps.get_model("adminpanel", "BlogPost")
    BlogPost.objects.filter(slug__in=[p["slug"] for p in POSTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("adminpanel", "0005_blogpost"),
    ]

    operations = [
        migrations.RunPython(seed_posts, unseed),
    ]
