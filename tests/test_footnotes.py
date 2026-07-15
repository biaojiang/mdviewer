import unittest

from bs4 import BeautifulSoup

from mdviewer.app import md


class FootnoteRenderingTest(unittest.TestCase):
    def test_reference_links_to_definition_and_back(self):
        html = md.render(
            "The mystery becomes clear.[^1]\n\n[^1]: A reference with **Markdown**.\n"
        )
        soup = BeautifulSoup(html, "html.parser")

        reference = soup.select_one("sup.footnote-ref > a")
        self.assertIsNotNone(reference)
        self.assertEqual(reference["id"], "fnref1")
        self.assertEqual(reference["href"], "#fn1")

        definition = soup.select_one("li#fn1")
        self.assertIsNotNone(definition)
        self.assertIsNotNone(definition.select_one("strong"))

        back_reference = definition.select_one("a.footnote-backref")
        self.assertIsNotNone(back_reference)
        self.assertEqual(back_reference["href"], "#fnref1")


if __name__ == "__main__":
    unittest.main()
