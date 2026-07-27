from django.test import TestCase
from django.urls import reverse
from aplicator.models import TeamMember, CompanyContextBlock


class ContextViewTest(TestCase):
    def test_get_renders_page(self):
        response = self.client.get(reverse("aplicator:context"))
        self.assertEqual(response.status_code, 200)

    def test_post_adds_team_member(self):
        response = self.client.post(
            reverse("aplicator:context"),
            {
                "add_member": "1",
                "name": "Ada Lovelace",
                "role": "CTO",
                "bio": "",
                "track_record": "",
                "notable_projects": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TeamMember.objects.count(), 1)

    def test_post_adds_context_block(self):
        response = self.client.post(
            reverse("aplicator:context"),
            {"add_block": "1", "label": "traction", "text": "10 pilots."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyContextBlock.objects.count(), 1)
