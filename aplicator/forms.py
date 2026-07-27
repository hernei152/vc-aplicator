from django import forms

from aplicator.models import TeamMember, CompanyContextBlock


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ["name", "role", "bio", "track_record", "notable_projects"]


class CompanyContextBlockForm(forms.ModelForm):
    class Meta:
        model = CompanyContextBlock
        fields = ["label", "text"]
