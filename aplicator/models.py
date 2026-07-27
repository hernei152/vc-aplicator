from django.db import models


class TeamMember(models.Model):
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    bio = models.TextField(blank=True, default="")
    track_record = models.TextField(blank=True, default="")
    notable_projects = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name


class CompanyContextBlock(models.Model):
    label = models.CharField(max_length=100)
    text = models.TextField()

    def __str__(self):
        return self.label


class QuestionArchetype(models.TextChoices):
    PROBLEM = "problem", "Problem"
    SOLUTION = "solution", "Solution"
    WHY_NOW = "why_now", "Why now"
    WHY_YOU = "why_you", "Why you"
    TEAM = "team", "Team"
    TRACTION = "traction", "Traction"
    BUSINESS_MODEL = "business_model", "Business model"
    MARKET_SIZE = "market_size", "Market size"
    COMPETITION = "competition", "Competition"
    MOAT = "moat", "Moat"
    GTM = "gtm", "GTM"
    PRODUCT_DEMO = "product_demo", "Product demo"
    TECH = "tech", "Tech"
    MILESTONES = "milestones", "Milestones"
    ASK = "ask", "Ask"
    USE_OF_FUNDS = "use_of_funds", "Use of funds"
    RISKS = "risks", "Risks"
    FAILURE_STORY = "failure_story", "Failure story"
    WHY_THIS_PROGRAM = "why_this_program", "Why this program"
    LEGAL_ADMIN = "legal_admin", "Legal admin"
    OTHER = "other", "Other"


NON_SHAREABLE = frozenset(
    {
        QuestionArchetype.WHY_THIS_PROGRAM,
        QuestionArchetype.LEGAL_ADMIN,
        QuestionArchetype.OTHER,
    }
)


class VideoFocus(models.TextChoices):
    FOUNDER_INTRO = "founder_intro", "Founder intro"
    PITCH = "pitch", "Pitch"
    DEMO = "demo", "Demo"


class Accelerator(models.Model):
    accelerator_name = models.CharField(max_length=200)
    url = models.URLField(blank=True, default="")
    deadline = models.DateField(null=True, blank=True)
    raw_text = models.TextField(blank=True, default="")

    def __str__(self):
        return self.accelerator_name


class Question(models.Model):
    TYPE_CHOICES = [
        ("text", "Text"),
        ("multiple_choice", "Multiple choice"),
        ("video", "Video"),
    ]
    ORIENTATION_CHOICES = [("h", "Horizontal"), ("v", "Vertical"), ("any", "Any")]
    LANGUAGE_CHOICES = [("es", "Spanish"), ("en", "English"), ("any", "Any")]
    WHO_CHOICES = [("solo", "Solo"), ("all_founders", "All founders"), ("any", "Any")]

    accelerator = models.ForeignKey(
        Accelerator, on_delete=models.CASCADE, related_name="questions"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    original_text = models.TextField()
    is_required = models.BooleanField(default=True)

    # text / multiple_choice fields
    category = models.CharField(
        max_length=30, choices=QuestionArchetype.choices, null=True, blank=True
    )
    max_chars = models.IntegerField(null=True, blank=True)
    options = models.JSONField(default=list, blank=True)
    allow_multiple = models.BooleanField(default=False)

    # video fields
    focus = models.CharField(
        max_length=20, choices=VideoFocus.choices, null=True, blank=True
    )
    min_seconds = models.IntegerField(null=True, blank=True)
    max_seconds = models.IntegerField(null=True, blank=True)
    orientation = models.CharField(
        max_length=5, choices=ORIENTATION_CHOICES, default="any"
    )
    language = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default="any"
    )
    who = models.CharField(max_length=15, choices=WHO_CHOICES, default="any")

    def __str__(self):
        return f"[{self.type}] {self.original_text[:50]}"
