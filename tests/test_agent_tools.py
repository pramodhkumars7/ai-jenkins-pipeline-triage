import json
import unittest
from unittest.mock import patch, MagicMock
import agent_tools


class TestCheckDuplicateIssue(unittest.TestCase):
    @patch("agent_tools._github_api")
    def test_returns_duplicate_when_signature_in_title(self, mock_api):
        mock_api.return_value = [
            {
                "number": 42,
                "title": "[playwright-e2e] TimeoutError - selector mismatch",
                "html_url": "https://github.com/owner/repo/issues/42",
            }
        ]
        result = agent_tools.check_duplicate_issue("[playwright-e2e] TimeoutError", "tok")
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["issue_number"], 42)
        self.assertEqual(result["url"], "https://github.com/owner/repo/issues/42")

    @patch("agent_tools._github_api")
    def test_returns_no_duplicate_when_not_found(self, mock_api):
        mock_api.return_value = []
        result = agent_tools.check_duplicate_issue("[playwright-e2e] TimeoutError", "tok")
        self.assertFalse(result["duplicate"])


class TestCreateGithubIssue(unittest.TestCase):
    @patch("agent_tools._github_api")
    def test_returns_issue_number_and_url(self, mock_api):
        mock_api.return_value = {
            "number": 99,
            "html_url": "https://github.com/owner/repo/issues/99",
        }
        result = agent_tools.create_github_issue("title", "body", ["pipeline-triage"], "tok")
        self.assertEqual(result["issue_number"], 99)
        self.assertEqual(result["url"], "https://github.com/owner/repo/issues/99")


class TestAddIssueComment(unittest.TestCase):
    @patch("agent_tools._github_api")
    def test_calls_api_with_correct_path(self, mock_api):
        mock_api.return_value = {"id": 1}
        agent_tools.add_issue_comment(42, "new failure on run #99", "tok")
        mock_api.assert_called_once_with(
            "POST", "/issues/42/comments", "tok", {"body": "new failure on run #99"}
        )


if __name__ == "__main__":
    unittest.main()
