from django.test import SimpleTestCase
from aplicator.templatetags.aplicator_extras import category_label, focus_label


class LabelFiltersTest(SimpleTestCase):
    def test_category_label_maps_known_value(self):
        self.assertEqual(category_label("why_now"), "Why now")

    def test_category_label_falls_back_to_raw_value(self):
        self.assertEqual(category_label("not_a_real_category"), "not_a_real_category")

    def test_focus_label_maps_known_value(self):
        self.assertEqual(focus_label("founder_intro"), "Founder intro")

    def test_focus_label_falls_back_to_raw_value(self):
        self.assertEqual(focus_label("not_a_real_focus"), "not_a_real_focus")
