from django import forms

from aplicator.models import TeamMember, CompanyContextBlock


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ["name", "role", "bio", "track_record", "notable_projects"]
        labels = {
            "name": "Nombre",
            "role": "Rol",
            "bio": "Bio",
            "track_record": "Trayectoria",
            "notable_projects": "Proyectos destacados",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3}),
            "track_record": forms.Textarea(attrs={"rows": 3}),
            "notable_projects": forms.Textarea(attrs={"rows": 3}),
        }


class CompanyContextBlockForm(forms.ModelForm):
    class Meta:
        model = CompanyContextBlock
        fields = ["label", "text"]
        labels = {
            "label": "Etiqueta",
            "text": "Texto",
        }
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4}),
        }
