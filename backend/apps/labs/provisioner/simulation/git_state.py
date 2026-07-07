"""In-memory git simulation for terminal labs.

Models enough of real git for learn/troubleshoot labs: repositories with
branches, commits, a staging area, remotes, stash, tags, and merge/rebase
flows. Working-tree contents live in the shared VFS (RHELOSState), so `echo,
vi, cat` interoperate with `git add/commit/status/diff` exactly like a real
shell session.
"""

from __future__ import annotations

import hashlib
import time


def _short_hash(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:7]


def _full_hash(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()


class GitRepo:
    """A single repository. Tracked snapshots are {path: content} per commit."""

    def __init__(self, root: str, bare_remote: str = "origin"):
        self.root = root.rstrip("/") or "/"
        self.head = "main"
        self.detached = False
        # branch -> list of commits; each commit is a dict:
        #   {hash, message, author, email, ts, files: {relpath: content}, parents}
        self.branches: dict[str, list[dict]] = {"main": []}
        self.staged: dict[str, str | None] = {}  # relpath -> content (None = deleted)
        self.remotes: dict[str, str] = {}
        self.config: dict[str, str] = {}
        self.stash: list[dict] = []
        self.tags: dict[str, str] = {}  # tag -> commit hash
        # remote-tracking: branch -> number of local commits not pushed
        self.pushed_counts: dict[str, int] = {}
        self.merge_conflict: bool = False
        self.conflict_files: list[str] = []

    # ── serialization ──
    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "head": self.head,
            "detached": self.detached,
            "branches": self.branches,
            "staged": self.staged,
            "remotes": self.remotes,
            "config": self.config,
            "stash": self.stash,
            "tags": self.tags,
            "pushed_counts": self.pushed_counts,
            "merge_conflict": self.merge_conflict,
            "conflict_files": self.conflict_files,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GitRepo":
        repo = cls(d.get("root", "/"))
        repo.head = d.get("head", "main")
        repo.detached = d.get("detached", False)
        repo.branches = d.get("branches", {"main": []})
        repo.staged = d.get("staged", {})
        repo.remotes = d.get("remotes", {})
        repo.config = d.get("config", {})
        repo.stash = d.get("stash", [])
        repo.tags = d.get("tags", {})
        repo.pushed_counts = d.get("pushed_counts", {})
        repo.merge_conflict = d.get("merge_conflict", False)
        repo.conflict_files = d.get("conflict_files", [])
        return repo

    # ── helpers ──
    def commits(self, branch: str | None = None) -> list[dict]:
        return self.branches.get(branch or self.head, [])

    def tracked_files(self, branch: str | None = None) -> dict[str, str]:
        commits = self.commits(branch)
        return dict(commits[-1]["files"]) if commits else {}

    def author(self) -> tuple[str, str]:
        name = self.config.get("user.name", "Lab Engineer")
        email = self.config.get("user.email", "engineer@fixitlab.local")
        return name, email

    def make_commit(self, message: str, files: dict[str, str], author=None) -> dict:
        name, email = author or self.author()
        ts = time.time()
        parents = [self.commits()[-1]["hash"]] if self.commits() else []
        h = _full_hash(f"{message}{ts}{self.head}{len(self.commits())}")
        return {
            "hash": h,
            "message": message,
            "author": name,
            "email": email,
            "ts": ts,
            "files": files,
            "parents": parents,
        }


class GitSimState:
    """All repositories in one simulated machine, keyed by repo root path."""

    def __init__(self):
        self.repos: dict[str, GitRepo] = {}

    def to_dict(self) -> dict:
        return {"repos": {k: r.to_dict() for k, r in self.repos.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "GitSimState":
        g = cls()
        for k, v in (d or {}).get("repos", {}).items():
            g.repos[k] = GitRepo.from_dict(v)
        return g

    def repo_for(self, cwd: str) -> GitRepo | None:
        """Find the repository whose root contains cwd (deepest match wins)."""
        best = None
        for root, repo in self.repos.items():
            if cwd == root or cwd.startswith(root.rstrip("/") + "/"):
                if best is None or len(root) > len(best.root):
                    best = repo
        return best

    def init_repo(self, root: str) -> GitRepo:
        root = root.rstrip("/") or "/"
        if root not in self.repos:
            self.repos[root] = GitRepo(root)
        return self.repos[root]


def seed_repo(
    git: GitSimState,
    state,
    root: str,
    files: dict[str, str],
    history: list[tuple[str, dict[str, str]]] | None = None,
    branch_commits: dict[str, list[tuple[str, dict[str, str]]]] | None = None,
    remote: str = "git@gitlab.fixitlab.local:platform/app.git",
) -> GitRepo:
    """Create a repo at `root`, write files into the VFS, and build history.

    `history` is a list of (message, files_delta) applied in order on main.
    `branch_commits` maps extra branch names to their own (message, delta) list
    branched from main's tip.
    """
    repo = git.init_repo(root)
    repo.remotes["origin"] = remote
    repo.config.setdefault("user.name", "Lab Engineer")
    repo.config.setdefault("user.email", "engineer@fixitlab.local")

    state._mkdir(root)
    snapshot: dict[str, str] = {}
    base_history = history or [("Initial commit", dict(files))]
    ts = time.time() - 86400 * 3
    for i, (msg, delta) in enumerate(base_history):
        snapshot.update(delta)
        commit = repo.make_commit(msg, dict(snapshot))
        commit["ts"] = ts + i * 7200
        commit["parents"] = [repo.branches["main"][-1]["hash"]] if repo.branches["main"] else []
        repo.branches["main"].append(commit)
    repo.pushed_counts["main"] = len(repo.branches["main"])

    for bname, commits in (branch_commits or {}).items():
        repo.branches[bname] = list(repo.branches["main"])
        bsnap = dict(snapshot)
        for j, (msg, delta) in enumerate(commits):
            bsnap.update(delta)
            commit = repo.make_commit(msg, dict(bsnap))
            commit["ts"] = ts + 86400 + j * 3600
            commit["parents"] = [repo.branches[bname][-1]["hash"]]
            repo.branches[bname].append(commit)

    # Working tree mirrors main's tip
    for rel, content in snapshot.items():
        state.write_file(f"{root}/{rel}", content)
    return repo
