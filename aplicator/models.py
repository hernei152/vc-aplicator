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
