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


class TeamMemberEditDeleteViewTest(TestCase):
    def setUp(self):
        self.member = TeamMember.objects.create(name="Ada Lovelace", role="CTO")

    def test_get_renders_edit_form(self):
        response = self.client.get(
            reverse("aplicator:team_member_edit", args=[self.member.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Lovelace")

    def test_post_edits_member(self):
        response = self.client.post(
            reverse("aplicator:team_member_edit", args=[self.member.id]),
            {
                "name": "Ada Lovelace",
                "role": "CEO",
                "bio": "",
                "track_record": "",
                "notable_projects": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "CEO")

    def test_post_deletes_member(self):
        response = self.client.post(
            reverse("aplicator:team_member_delete", args=[self.member.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TeamMember.objects.count(), 0)


class ContextBlockEditDeleteViewTest(TestCase):
    def setUp(self):
        self.block = CompanyContextBlock.objects.create(
            label="traction", text="10 pilots."
        )

    def test_get_renders_edit_form(self):
        response = self.client.get(
            reverse("aplicator:context_block_edit", args=[self.block.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "traction")

    def test_post_edits_block(self):
        response = self.client.post(
            reverse("aplicator:context_block_edit", args=[self.block.id]),
            {"label": "traction", "text": "20 pilots now."},
        )
        self.assertEqual(response.status_code, 302)
        self.block.refresh_from_db()
        self.assertEqual(self.block.text, "20 pilots now.")

    def test_post_deletes_block(self):
        response = self.client.post(
            reverse("aplicator:context_block_delete", args=[self.block.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyContextBlock.objects.count(), 0)
