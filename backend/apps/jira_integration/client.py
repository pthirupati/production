"""
Jira Cloud REST API v3 client for FixitLab lab lifecycle sync.
"""

import base64
import logging
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    pass


class JiraClient:
    """Minimal Jira Cloud client for issue create, transition, and comment."""

    def __init__(self):
        self.base_url = (settings.JIRA_BASE_URL or "").rstrip("/")
        self.email = settings.JIRA_EMAIL
        self.api_token = settings.JIRA_API_TOKEN
        self.project_key = settings.JIRA_PROJECT_KEY
        self.issue_type = settings.JIRA_ISSUE_TYPE

    @property
    def enabled(self) -> bool:
        return bool(
            settings.JIRA_ENABLED
            and self.base_url
            and self.email
            and self.api_token
            and self.project_key
        )

    def _headers(self) -> dict:
        creds = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}/rest/api/3{path}"
        try:
            resp = requests.request(
                method, url, headers=self._headers(), timeout=15, **kwargs
            )
        except requests.RequestException as exc:
            raise JiraClientError(str(exc)) from exc

        if resp.status_code >= 400:
            logger.error("Jira API %s %s failed: %s", method, path, resp.text[:500])
            raise JiraClientError(f"Jira API error {resp.status_code}: {resp.text[:200]}")

        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def issue_url(self, issue_key: str) -> str:
        return f"{self.base_url}/browse/{issue_key}"

    def create_issue(
        self,
        summary: str,
        description: str,
        priority: str = "",
        labels: Optional[list] = None,
    ) -> dict:
        fields: dict = {
            "project": {"key": self.project_key},
            "issuetype": {"name": self.issue_type},
            "summary": summary[:255],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description[:32000]}],
                    }
                ],
            },
        }
        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels

        return self._request("POST", "/issue", json={"fields": fields})

    def get_transitions(self, issue_key: str) -> list:
        data = self._request("GET", f"/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    def transition_issue(self, issue_key: str, transition_name: str) -> bool:
        transitions = self.get_transitions(issue_key)
        target = transition_name.strip().lower()
        transition_id = None
        for t in transitions:
            if t.get("name", "").strip().lower() == target:
                transition_id = t["id"]
                break

        if not transition_id:
            logger.warning(
                "Jira transition '%s' not found for %s (available: %s)",
                transition_name,
                issue_key,
                [t.get("name") for t in transitions],
            )
            return False

        self._request(
            "POST",
            f"/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )
        return True

    def add_comment(self, issue_key: str, body: str) -> None:
        self._request(
            "POST",
            f"/issue/{issue_key}/comment",
            json={
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": body[:32000]}],
                        }
                    ],
                }
            },
        )

    def get_issue_status(self, issue_key: str) -> str:
        data = self._request("GET", f"/issue/{issue_key}", params={"fields": "status"})
        return data.get("fields", {}).get("status", {}).get("name", "")
