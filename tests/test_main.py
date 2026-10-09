import unittest

from ayudas.__main__ import github_pages_url


class PagesAddress(unittest.TestCase):
    def test_user_or_organisation_site_lives_at_the_root(self):
        self.assertEqual(github_pages_url("ajud-es/ajud-es.github.io"), "https://ajud-es.github.io/")

    def test_project_site_lives_under_the_repository_name(self):
        self.assertEqual(github_pages_url("Ajud-es/web"), "https://ajud-es.github.io/web/")

    def test_outside_github_there_is_no_address(self):
        self.assertEqual(github_pages_url(""), "")


if __name__ == "__main__":
    unittest.main()
