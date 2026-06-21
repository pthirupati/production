
from django.db import models
from django.conf import settings


class Technology(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
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

    # Maintenance mode — per-technology
    maintenance_enabled = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default="")
    maintenance_scheduled_start = models.DateTimeField(null=True, blank=True)
    maintenance_scheduled_end = models.DateTimeField(null=True, blank=True)

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
    slug = models.SlugField(max_length=255, unique=True, blank=True)

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
    slug = models.SlugField(max_length=255, unique=True)
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
        ("java", "Java Development Simulation"),
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

    # ── Browser coding IDE scenarios ──
    # When coding_mode is True, the lab opens a full in-browser IDE (CodeMirror +
    # Pyodide / Web Worker execution) instead of a terminal. coding_spec carries
    # the starter files, visible tests, and HIDDEN tests. Hidden test logic is
    # NEVER sent to the client — it is executed server-side by the
    # /labs/<id>/code-validate/ endpoint. See apps.labs.code_exec.
    coding_mode = models.BooleanField(
        default=False,
        help_text="Open a browser coding IDE (CodeMirror + sandboxed run) instead of a terminal",
    )

    # ── Cross-technology scenarios (VMware ⇄ Linux terminal) ──
    # When cross_technology is True the SAME server exists in both the VMware
    # simulator and the Linux lab terminal for one lab session, and an action in
    # VMware (e.g. Add Hard Disk) reflects in the terminal after a rescan/reboot.
    # vmware_link tells the LabRunner to surface an "Open VMware" affordance so the
    # operator can perform the hypervisor-side step.
    cross_technology = models.BooleanField(
        default=False,
        help_text="Server is shared across the VMware simulator and the Linux terminal in one session",
    )
    vmware_link = models.BooleanField(
        default=False,
        help_text="Surface an 'Open VMware' link in the lab so the user can perform the hypervisor-side action",
    )
    coding_spec = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Coding scenario definition: {language, files:[{path,content,readonly}], "
            "entrypoint, visible_tests:[...], hidden_tests:[...]}. "
            "hidden_tests are stripped from public API responses and only run on the backend."
        ),
    )

    # ── ITSM (ServiceNow-style ticketing) flow ──
    # When itsm_enabled is True the lab opens a ServiceNow-style ticket for the
    # user+scenario (apps.itsm). From that parent ticket the user can raise
    # sub-tickets to other teams (Storage/Network/Backup); a simulated team
    # fulfils them and mutates the lab sim — e.g. the Storage team adds a disk via
    # the vmware_bridge so it appears in the terminal after a rescan. itsm_config
    # tunes the opened ticket and which sub-ticket actions the scenario expects.
    itsm_enabled = models.BooleanField(
        default=False,
        help_text="Open a ServiceNow-style ITSM ticket for this scenario in the lab runner",
    )
    ITSM_TYPE_CHOICES = [
        ("incident", "Incident"),
        ("request", "Service Request"),
        ("change", "Change"),
        ("problem", "Problem"),
    ]
    itsm_ticket_type = models.CharField(
        max_length=20,
        choices=ITSM_TYPE_CHOICES,
        default="incident",
        blank=True,
        help_text="ServiceNow ticket type opened for this scenario",
    )
    itsm_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "ITSM tuning: {ticket_type, short_description, description, priority, "
            "assignment_group, teams:[...], allowed_actions:[add_disk,add_nic,...]}. "
            "Drives the opened ticket and the sub-ticket actions surfaced in the panel."
        ),
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
            models.Index(fields=["is_active", "technology"], name="scenario_active_tech_idx"),
            models.Index(fields=["is_active", "difficulty"], name="scenario_active_diff_idx"),
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


# ─── Projects ────────────────────────────────────────────────────────────────

class Project(models.Model):
    """End-to-end guided project: users implement an architecture by following Jira tickets."""

    ARCHITECTURE_CHOICES = [
        ("2tier", "2-Tier Architecture (Web + DB)"),
        ("3tier", "3-Tier Architecture (LB + App + DB)"),
        ("microservices", "Microservices"),
        ("cicd", "CI/CD Pipeline"),
        ("custom", "Custom"),
    ]
    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    architecture_type = models.CharField(max_length=20, choices=ARCHITECTURE_CHOICES, default="custom")
    description = models.TextField()
    objectives = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="intermediate")
    estimated_hours = models.PositiveIntegerField(default=4)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(f"{self.technology.slug}-{self.title}")
            self.slug = base
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.technology.name} — {self.title}"


class ProjectTask(models.Model):
    """A single Jira-style ticket within a Project."""

    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    jira_key = models.CharField(max_length=20, help_text="e.g. PROJ-1")
    description = models.TextField()
    acceptance_criteria = models.TextField(blank=True)
    hint = models.TextField(blank=True, help_text="Jira bot hint when user asks for help")
    order = models.PositiveIntegerField(default=0)
    depends_on = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="dependents"
    )

    class Meta:
        ordering = ["order"]
        unique_together = ("project", "jira_key")

    def __str__(self):
        return f"{self.jira_key}: {self.title}"


class UserProjectProgress(models.Model):
    """Track a user's progress through a Project."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_progress")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="user_progress")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("in_progress", "In Progress"), ("completed", "Completed")],
        default="in_progress",
    )

    class Meta:
        unique_together = ("user", "project")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} → {self.project}"


class UserTaskProgress(models.Model):
    """Track a user's status on an individual ProjectTask, with optional screenshot."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_progress")
    task = models.ForeignKey(ProjectTask, on_delete=models.CASCADE, related_name="user_progress")
    status = models.CharField(
        max_length=20,
        choices=[("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done")],
        default="todo",
    )
    screenshot = models.ImageField(upload_to="project_screenshots/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "task")
        ordering = ["task__order"]

    def __str__(self):
        return f"{self.user} → {self.task.jira_key} ({self.status})"

