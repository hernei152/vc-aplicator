import os
from django.conf import settings
from django.test import TestCase


class PicoCssVendoredTest(TestCase):
    def test_pico_css_file_exists_and_is_nontrivial(self):
        path = os.path.join(settings.BASE_DIR, "aplicator", "static", "aplicator", "pico.min.css")
        self.assertTrue(os.path.exists(path), f"expected {path} to exist")
        self.assertGreater(os.path.getsize(path), 50_000)

    def test_base_template_links_pico_css(self):
        response = self.client.get("/")
        self.assertContains(response, "pico.min.css")
