from django.test import TestCase
from aplicator.models import TeamMember, CompanyContextBlock


class TeamMemberModelTest(TestCase):
    def test_create_team_member(self):
        member = TeamMember.objects.create(
            name="Ada Lovelace",
            role="CTO",
            bio="Built the first algorithm.",
            track_record="Shipped the Analytical Engine software.",
            notable_projects="Notes on the Analytical Engine.",
        )
        self.assertEqual(TeamMember.objects.count(), 1)
        self.assertEqual(member.name, "Ada Lovelace")

    def test_track_record_and_projects_optional(self):
        member = TeamMember.objects.create(name="Grace Hopper", role="CEO")
        self.assertEqual(member.track_record, "")
        self.assertEqual(member.notable_projects, "")


class CompanyContextBlockModelTest(TestCase):
    def test_create_block(self):
        block = CompanyContextBlock.objects.create(
            label="traction", text="10 pilot customers, $5k MRR."
        )
        self.assertEqual(str(block), "traction")
        self.assertEqual(CompanyContextBlock.objects.count(), 1)
