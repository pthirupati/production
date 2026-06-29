"""
Jira Cloud REST API v3 client for FixitLab lab lifecycle sync.
"""

import base64
import logging
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _inline_nodes(text: str) -> list:
    """Split a line into ADF inline nodes, honoring **bold** and `code`."""
    import re

    nodes: list = []
    for part in re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            nodes.append(
                {"type": "text", "text": part[1:-1], "marks": [{"type": "code"}]}
            )
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            nodes.append(
                {"type": "text", "text": part[2:-2], "marks": [{"type": "strong"}]}
            )
        else:
            nodes.append({"type": "text", "text": part})
    return nodes or [{"type": "text", "text": text}]


def _markdown_to_adf(text: str) -> dict:
    """Convert the lightweight Markdown used in ticket bodies to Jira ADF.

    Supports: '## '/'### ' headings, '- '/'* ' bullet lists, ``` code fences,
    blank-line paragraph breaks, and inline **bold** / `code`. Anything else is
    a plain paragraph. This keeps real-Jira tickets readable instead of dumping
    raw Markdown (with literal #, **, -) into a single paragraph.
    """
    content: list = []
    lines = (text or "").split("\n")
    i = 0
    bullets: list = []

    def flush_bullets():
        nonlocal bullets
        if bullets:
            content.append(
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {"type": "paragraph", "content": _inline_nodes(b)}
                            ],
                        }
                        for b in bullets
                    ],
                }
            )
            bullets = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_bullets()
            lang = stripped[3:].strip()
            code_lines: list = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            block = {
                "type": "codeBlock",
                "content": [{"type": "text", "text": "\n".join(code_lines)}],
            }
            if lang:
                block["attrs"] = {"language": lang}
            content.append(block)
            i += 1
            continue
        if stripped.startswith("### "):
            flush_bullets()
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": _inline_nodes(stripped[4:]),
                }
            )
        elif stripped.startswith("## "):
            flush_bullets()
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": _inline_nodes(stripped[3:]),
                }
            )
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullets.append(stripped[2:])
        elif not stripped:
            flush_bullets()
        else:
            flush_bullets()
            content.append({"type": "paragraph", "content": _inline_nodes(stripped)})
        i += 1
    flush_bullets()

    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]
    return {"type": "doc", "version": 1, "content": content}


def _adf_inline_to_markdown(nodes: list) -> str:
    out = ""
    for node in nodes or []:
        if node.get("type") != "text":
            continue
        txt = node.get("text", "")
        marks = {m.get("type") for m in node.get("marks", [])}
        if "code" in marks:
            txt = f"`{txt}`"
        if "strong" in marks:
            txt = f"**{txt}**"
        out += txt
    return out


def _adf_to_markdown(doc: dict) -> str:
    """Reconstruct lightweight Markdown from an ADF doc so JiraRichText renders
    headings/bullets/code instead of one run-together paragraph."""
    out: list = []
    for block in doc.get("content", []):
        btype = block.get("type")
        if btype == "heading":
            level = block.get("attrs", {}).get("level", 2)
            out.append(("#" * max(2, level)) + " " + _adf_inline_to_markdown(block.get("content", [])))
        elif btype == "bulletList":
            for item in block.get("content", []):
                for para in item.get("content", []):
                    out.append("- " + _adf_inline_to_markdown(para.get("content", [])))
        elif btype == "codeBlock":
            lang = block.get("attrs", {}).get("language", "")
            code = "".join(n.get("text", "") for n in block.get("content", []))
            out.append(f"```{lang}\n{code}\n```")
        elif btype == "paragraph":
            out.append(_adf_inline_to_markdown(block.get("content", [])))
        out.append("")
    return "\n".join(out).strip()


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
        from .simulated import use_simulated_jira

        if use_simulated_jira():
            return False
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
            "description": _markdown_to_adf(description[:32000]),
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
            json={"body": _markdown_to_adf(body[:32000])},
        )

    def get_issue_status(self, issue_key: str) -> str:
        data = self._request("GET", f"/issue/{issue_key}", params={"fields": "status"})
        return data.get("fields", {}).get("status", {}).get("name", "")

    def get_issue_details(self, issue_key: str) -> dict:
        """Fetch summary + description for in-app display (no user Jira login needed)."""
        data = self._request(
            "GET",
            f"/issue/{issue_key}",
            params={"fields": "summary,description,status,comment"},
        )
        fields = data.get("fields", {})
        desc_doc = fields.get("description")
        if isinstance(desc_doc, dict):
            description = _adf_to_markdown(desc_doc)
        elif isinstance(desc_doc, str):
            description = desc_doc
        else:
            description = ""
        return {
            "summary": fields.get("summary", ""),
            "description": description[:8000],
            "status": fields.get("status", {}).get("name", ""),
        }
