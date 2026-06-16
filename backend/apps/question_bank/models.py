
from django.db import models
from django.conf import settings


class Technology(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=255, blank=True, help_text="Icon name (lucide icon) or URL")
    color = models.CharField(max_length=20, blank=True, default="cyan", help_text="Theme color key")
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=499, help_text="Price in INR for technology subscription")
    is_active = models.BooleanField(default=True)
    coming_soon = models.BooleanField(
        default=False,
        help_text="Show as coming soon — visible but not openable until disabled",
    )
    learning_path = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered learning path steps: [{title, scenario_slug, description}]",
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "technologies"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Granular tags for scenario filtering (e.g., nginx, dns, bash, docker, systemd)"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Scenario(models.Model):
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    TYPE_CHOICES = [
        ("fix", "Fix"),
        ("do", "Do"),
        ("hack", "Hack"),
    ]

    INFRA_CHOICES = [
        ("docker", "Docker Container"),
        ("aws_ec2", "AWS EC2 Instance"),
        ("digitalocean", "DigitalOcean Droplet"),
    ]

    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name="scenarios")
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, help_text="Short tagline like SadServers city names")
    category = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    scenario_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="fix")
    tags = models.ManyToManyField(Tag, blank=True, related_name="scenarios")
    description = models.TextField()
    objectives = models.JSONField(default=list, blank=True, help_text="List of objectives")
    initial_state = models.TextField(blank=True, help_text="Description of the broken state")
    validation_script = models.TextField(blank=True, help_text="Bash script to validate the fix")
    solution_explanation = models.TextField(blank=True, help_text="Explanation shown after solving")
    docker_image = models.CharField(max_length=255, blank=True, help_text="Custom Docker image override")
    infrastructure_type = models.CharField(
        max_length=20,
        choices=INFRA_CHOICES,
        default="docker",
        help_text="Where to run this scenario: docker (recommended), aws_ec2, or digitalocean",
    )
    docker_privileged = models.BooleanField(
        default=False,
        help_text="Run lab container privileged (required for LVM/device scenarios)",
    )
    cloud_setup_script = models.TextField(
        blank=True,
        help_text="Bash script to set up the broken state on a cloud instance (runs via cloud-init)",
    )
    blocked_commands = models.JSONField(
        default=list, blank=True,
        help_text="List of command patterns blocked in this scenario (e.g. reboot, shutdown, rm -rf /)",
    )
    cloud_ami = models.CharField(
        max_length=100, blank=True,
        help_text="AWS AMI ID for EC2-based scenarios (default: Ubuntu 22.04)",
    )
    cloud_image = models.CharField(
        max_length=100, blank=True,
        help_text="DigitalOcean image slug for droplet-based scenarios (default: ubuntu-22-04-x64)",
    )
    jira_priority = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Jira priority name (e.g. High, Medium, Low)",
    )
    jira_issue_template = models.TextField(
        blank=True,
        help_text="Optional custom Jira ticket body override (plain text)",
    )

    LAB_MODE_CHOICES = [
        ("docker", "Docker Container"),
        ("simulation", "Simulation (no real container)"),
    ]
    SIMULATION_TYPE_CHOICES = [
        ("generic", "Normal Simulation (full RHEL)"),
        ("rhel", "RHEL Linux Simulation"),
        ("kubernetes", "Kubernetes Simulation"),
        ("gpu", "GPU / NVIDIA Simulation"),
        ("baremetal", "Bare Metal / IPMI / VMware"),
        ("database", "Database Simulation"),
        ("ansible", "Ansible Simulation"),
        ("python", "Python Simulation"),
    ]

    requires_companion_hosts = models.BooleanField(
        default=False,
        help_text="Provision dual Docker containers (NFS/SCP/SSH/network scenarios)",
    )
    dual_terminal = models.BooleanField(
        default=False,
        help_text="Show two terminal panels in the lab UI",
    )
    lab_mode = models.CharField(
        max_length=20,
        choices=LAB_MODE_CHOICES,
        default="docker",
        help_text="Docker container or simulated environment",
    )
    simulation_type = models.CharField(
        max_length=20,
        choices=SIMULATION_TYPE_CHOICES,
        default="generic",
        help_text="Technology persona when lab_mode=simulation (one unified engine)",
    )

    time_limit = models.PositiveIntegerField(default=600, help_text="Time limit in seconds (default 10 min)")
    max_score = models.PositiveIntegerField(default=100)
    definition_path = models.CharField(max_length=255, blank=True)
    is_free = models.BooleanField(default=False, help_text="Available without login")
    is_active = models.BooleanField(default=True)
    interview_mode = models.BooleanField(
        default=False,
        help_text="Timed interview-style scenario with stricter hints",
    )
    attempts_count = models.PositiveIntegerField(default=0, help_text="Cached total attempts")
    completions_count = models.PositiveIntegerField(default=0, help_text="Cached total completions")
    avg_completion_time = models.PositiveIntegerField(default=0, help_text="Average solve time in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["technology", "difficulty", "title"]
        indexes = [
            models.Index(fields=["is_active", "technology"]),
            models.Index(fields=["is_active", "difficulty"]),
        ]

    @property
    def completion_rate(self):
        if self.attempts_count == 0:
            return 0
        return round((self.completions_count / self.attempts_count) * 100)

    def __str__(self):
        return self.title


class Bookmark(models.Model):
    """Users can bookmark scenarios for later"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "scenario")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.scenario.slug}"

