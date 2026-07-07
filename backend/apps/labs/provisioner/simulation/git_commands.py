"""`git` command implementation for the RHEL terminal simulation.

Backed by GitSimState (git_state.py); working-tree contents live in the shared
VFS so file edits made with echo/vi/sed are what git sees.
"""

from __future__ import annotations

import time

from .git_state import GitRepo, GitSimState, _short_hash

IGNORED_DIRS = (".git/",)


def _worktree(state, root: str) -> dict[str, str]:
    """All files under repo root in the VFS, as {relpath: content}."""
    prefix = root.rstrip("/") + "/"
    out: dict[str, str] = {}
    for path, node in state.vfs.items():
        if not path.startswith(prefix):
            continue
        if not isinstance(node, dict) or node.get("type") != "file":
            continue
        rel = path[len(prefix):]
        if any(rel.startswith(d) for d in IGNORED_DIRS):
            continue
        out[rel] = node.get("content", "")
    return out


def _changes(repo: GitRepo, tree: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(modified, untracked, deleted) relative to HEAD commit + staging."""
    tracked = repo.tracked_files()
    modified, untracked, deleted = [], [], []
    for rel, content in tree.items():
        if rel in repo.staged:
            continue
        if rel not in tracked:
            untracked.append(rel)
        elif tracked[rel] != content:
            modified.append(rel)
    for rel in tracked:
        if rel not in tree and rel not in repo.staged:
            deleted.append(rel)
    return sorted(modified), sorted(untracked), sorted(deleted)


def _fmt_date(ts: float) -> str:
    return time.strftime("%a %b %-d %H:%M:%S %Y +0000", time.gmtime(ts))


def run_git(state, parts: list[str], line: str) -> str:
    if not hasattr(state, "git") or state.git is None:
        state.git = GitSimState()
    git: GitSimState = state.git
    state.last_exit_code = 0
    args = parts[1:]
    if not args or args[0] in ("--help", "help"):
        return _help()

    sub = args[0]
    rest = args[1:]

    if sub == "--version":
        return "git version 2.43.5"
    if sub == "init":
        return _git_init(git, state, rest)
    if sub == "clone":
        return _git_clone(git, state, rest)
    if sub == "config":
        return _git_config(git, state, rest)

    repo = git.repo_for(state.cwd)
    if repo is None:
        state.last_exit_code = 128
        return "fatal: not a git repository (or any of the parent directories): .git"

    dispatch = {
        "status": _git_status,
        "add": _git_add,
        "commit": _git_commit,
        "log": _git_log,
        "branch": _git_branch,
        "checkout": _git_checkout,
        "switch": _git_switch,
        "merge": _git_merge,
        "diff": _git_diff,
        "remote": _git_remote,
        "push": _git_push,
        "pull": _git_pull,
        "fetch": _git_fetch,
        "stash": _git_stash,
        "reset": _git_reset,
        "revert": _git_revert,
        "tag": _git_tag,
        "rebase": _git_rebase,
        "cherry-pick": _git_cherry_pick,
        "show": _git_show,
        "rm": _git_rm,
        "mv": _git_mv,
        "restore": _git_restore,
    }
    fn = dispatch.get(sub)
    if fn is None:
        state.last_exit_code = 1
        return f"git: '{sub}' is not a git command. See 'git --help'."
    return fn(repo, state, rest)


def _help() -> str:
    return (
        "usage: git <command> [<args>]\n\n"
        "Common commands:\n"
        "   clone      Clone a repository into a new directory\n"
        "   init       Create an empty Git repository\n"
        "   add        Add file contents to the index\n"
        "   status     Show the working tree status\n"
        "   commit     Record changes to the repository\n"
        "   log        Show commit logs\n"
        "   branch     List, create, or delete branches\n"
        "   checkout   Switch branches or restore files\n"
        "   merge      Join two or more development histories\n"
        "   diff       Show changes between commits and working tree\n"
        "   push       Update remote refs\n"
        "   pull       Fetch and integrate with another repository\n"
        "   stash      Stash changes in a dirty working directory\n"
        "   reset      Reset current HEAD to the specified state\n"
        "   tag        Create, list, delete tag objects"
    )


def _git_init(git: GitSimState, state, rest: list[str]) -> str:
    target = next((a for a in rest if not a.startswith("-")), "")
    root = state.resolve_path(target) if target else state.cwd
    state._mkdir(root)
    git.init_repo(root)
    return f"Initialized empty Git repository in {root}/.git/"


def _git_clone(git: GitSimState, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 129
        return "fatal: You must specify a repository to clone."
    url = pos[0]
    name = pos[1] if len(pos) > 1 else url.rstrip("/").split("/")[-1].removesuffix(".git")
    root = state.resolve_path(name)
    if _worktree(state, root):
        state.last_exit_code = 128
        return f"fatal: destination path '{name}' already exists and is not an empty directory."
    repo = git.init_repo(root)
    repo.remotes["origin"] = url
    readme = f"# {name}\n\nCloned from {url} in the FixitLab simulation.\n"
    files = {"README.md": readme, ".gitlab-ci.yml": "stages:\n  - build\n  - test\n  - deploy\n"}
    commit = repo.make_commit("Initial commit", files, author=("FixitLab Bot", "bot@fixitlab.local"))
    commit["ts"] = time.time() - 86400
    repo.branches["main"] = [commit]
    repo.pushed_counts["main"] = 1
    state._mkdir(root)
    for rel, content in files.items():
        state.write_file(f"{root}/{rel}", content)
    return (
        f"Cloning into '{name}'...\n"
        "remote: Enumerating objects: 12, done.\n"
        "remote: Total 12 (delta 2), reused 12 (delta 2)\n"
        "Receiving objects: 100% (12/12), done.\n"
        "Resolving deltas: 100% (2/2), done."
    )


def _git_config(git: GitSimState, state, rest: list[str]) -> str:
    flags = [a for a in rest if a.startswith("-")]
    pos = [a for a in rest if not a.startswith("-")]
    repo = git.repo_for(state.cwd)
    store = repo.config if repo else git.init_repo("/root").config
    if "--list" in flags or "-l" in flags:
        return "\n".join(f"{k}={v}" for k, v in sorted(store.items())) or ""
    if len(pos) >= 2:
        store[pos[0]] = " ".join(pos[1:]).strip('"')
        return ""
    if len(pos) == 1:
        val = store.get(pos[0])
        if val is None:
            state.last_exit_code = 1
            return ""
        return val
    return ""


def _git_status(repo: GitRepo, state, rest: list[str]) -> str:
    tree = _worktree(state, repo.root)
    modified, untracked, deleted = _changes(repo, tree)
    short = "-s" in rest or "--short" in rest

    if short:
        lines = []
        for rel in sorted(repo.staged):
            lines.append(f"A  {rel}" if rel not in repo.tracked_files() else f"M  {rel}")
        lines += [f" M {r}" for r in modified]
        lines += [f" D {r}" for r in deleted]
        lines += [f"?? {r}" for r in untracked]
        return "\n".join(lines)

    out = [f"On branch {repo.head}"]
    unpushed = len(repo.commits()) - repo.pushed_counts.get(repo.head, 0)
    if "origin" in repo.remotes:
        if unpushed > 0:
            out.append(f"Your branch is ahead of 'origin/{repo.head}' by {unpushed} commit{'s' if unpushed != 1 else ''}.")
            out.append('  (use "git push" to publish your local commits)')
        else:
            out.append(f"Your branch is up to date with 'origin/{repo.head}'.")
    out.append("")
    if repo.merge_conflict:
        out.append("You have unmerged paths.")
        out.append('  (fix conflicts and run "git commit")')
        out.append("")
        out.append("Unmerged paths:")
        for f in repo.conflict_files:
            out.append(f"\tboth modified:   {f}")
        out.append("")
    if repo.staged:
        out.append("Changes to be committed:")
        out.append('  (use "git restore --staged <file>..." to unstage)')
        tracked = repo.tracked_files()
        for rel in sorted(repo.staged):
            if repo.staged[rel] is None:
                out.append(f"\tdeleted:    {rel}")
            elif rel in tracked:
                out.append(f"\tmodified:   {rel}")
            else:
                out.append(f"\tnew file:   {rel}")
        out.append("")
    if modified or deleted:
        out.append("Changes not staged for commit:")
        out.append('  (use "git add <file>..." to update what will be committed)')
        for rel in modified:
            out.append(f"\tmodified:   {rel}")
        for rel in deleted:
            out.append(f"\tdeleted:    {rel}")
        out.append("")
    if untracked:
        out.append("Untracked files:")
        out.append('  (use "git add <file>..." to include in what will be committed)')
        for rel in untracked:
            out.append(f"\t{rel}")
        out.append("")
    if not repo.staged and not modified and not untracked and not deleted and not repo.merge_conflict:
        out.append("nothing to commit, working tree clean")
    return "\n".join(out).rstrip()


def _rel_to_root(state, repo: GitRepo, path: str) -> str:
    ap = state.resolve_path(path)
    prefix = repo.root.rstrip("/") + "/"
    return ap[len(prefix):] if ap.startswith(prefix) else ap.lstrip("/")


def _git_add(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    all_flag = "-A" in rest or "--all" in rest or "." in pos or not pos
    tree = _worktree(state, repo.root)
    modified, untracked, deleted = _changes(repo, tree)
    if all_flag:
        for rel in modified + untracked:
            repo.staged[rel] = tree[rel]
        for rel in deleted:
            repo.staged[rel] = None
        if repo.merge_conflict:
            repo.merge_conflict = False
            repo.conflict_files = []
        return ""
    missing = []
    for p in pos:
        rel = _rel_to_root(state, repo, p)
        if rel in tree:
            repo.staged[rel] = tree[rel]
            if rel in repo.conflict_files:
                repo.conflict_files.remove(rel)
                if not repo.conflict_files:
                    repo.merge_conflict = False
        elif rel in repo.tracked_files():
            repo.staged[rel] = None  # deleted
        else:
            missing.append(p)
    if missing:
        state.last_exit_code = 128
        return f"fatal: pathspec '{missing[0]}' did not match any files"
    return ""


def _git_commit(repo: GitRepo, state, rest: list[str]) -> str:
    msg = ""
    for i, a in enumerate(rest):
        if a in ("-m", "--message") and i + 1 < len(rest):
            msg = rest[i + 1].strip('"').strip("'")
        elif a.startswith("-m"):
            msg = a[2:].strip('"').strip("'")
    if "-am" in rest or "-a" in rest or "--all" in rest:
        tree = _worktree(state, repo.root)
        modified, _, deleted = _changes(repo, tree)
        for rel in modified:
            repo.staged[rel] = tree[rel]
        for rel in deleted:
            repo.staged[rel] = None
    if not msg:
        state.last_exit_code = 1
        return "Aborting commit due to empty commit message."
    if not repo.staged and not repo.merge_conflict:
        state.last_exit_code = 1
        return 'nothing to commit, working tree clean\n(use "git add" to stage changes first)'
    files = repo.tracked_files()
    added = sum(1 for rel, c in repo.staged.items() if rel not in files and c is not None)
    changed = len(repo.staged)
    for rel, content in repo.staged.items():
        if content is None:
            files.pop(rel, None)
        else:
            files[rel] = content
    commit = repo.make_commit(msg, files)
    repo.branches.setdefault(repo.head, []).append(commit)
    repo.staged = {}
    repo.merge_conflict = False
    repo.conflict_files = []
    add_note = f", {added} insertion{'s' if added != 1 else ''}(+)" if added else ""
    return (
        f"[{repo.head} {commit['hash'][:7]}] {msg}\n"
        f" {changed} file{'s' if changed != 1 else ''} changed{add_note}"
    )


def _git_log(repo: GitRepo, state, rest: list[str]) -> str:
    commits = list(reversed(repo.commits()))
    if not commits:
        state.last_exit_code = 128
        return f"fatal: your current branch '{repo.head}' does not have any commits yet"
    limit = None
    for i, a in enumerate(rest):
        if a in ("-n", "--max-count") and i + 1 < len(rest) and rest[i + 1].isdigit():
            limit = int(rest[i + 1])
        elif a.startswith("-") and a[1:].isdigit():
            limit = int(a[1:])
    if limit:
        commits = commits[:limit]
    oneline = "--oneline" in rest
    graph = "--graph" in rest
    if oneline:
        rows = [f"{c['hash'][:7]} {c['message']}" for c in commits]
        if graph:
            rows = [f"* {r}" for r in rows]
        return "\n".join(rows)
    out = []
    for c in commits:
        prefix = "* " if graph else ""
        out.append(f"{prefix}commit {c['hash']}")
        out.append(f"Author: {c['author']} <{c['email']}>")
        out.append(f"Date:   {_fmt_date(c['ts'])}")
        out.append("")
        out.append(f"    {c['message']}")
        out.append("")
    return "\n".join(out).rstrip()


def _git_branch(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if "-d" in rest or "-D" in rest:
        if not pos:
            state.last_exit_code = 1
            return "fatal: branch name required"
        name = pos[0]
        if name == repo.head:
            state.last_exit_code = 1
            return f"error: Cannot delete branch '{name}' checked out at '{repo.root}'"
        if name not in repo.branches:
            state.last_exit_code = 1
            return f"error: branch '{name}' not found."
        tip = repo.branches.pop(name)
        h = tip[-1]["hash"][:7] if tip else "0000000"
        return f"Deleted branch {name} (was {h})."
    if pos:
        name = pos[0]
        if name in repo.branches:
            state.last_exit_code = 128
            return f"fatal: a branch named '{name}' already exists"
        repo.branches[name] = list(repo.commits())
        return ""
    rows = []
    for b in sorted(repo.branches):
        rows.append(f"* {b}" if b == repo.head else f"  {b}")
    if "-a" in rest and "origin" in repo.remotes:
        for b in sorted(repo.pushed_counts):
            rows.append(f"  remotes/origin/{b}")
    return "\n".join(rows)


def _checkout_branch(repo: GitRepo, state, name: str, create: bool) -> str:
    if create:
        if name in repo.branches:
            state.last_exit_code = 128
            return f"fatal: a branch named '{name}' already exists"
        repo.branches[name] = list(repo.commits())
        repo.head = name
        return f"Switched to a new branch '{name}'"
    if name not in repo.branches:
        state.last_exit_code = 1
        return f"error: pathspec '{name}' did not match any file(s) known to git"
    repo.head = name
    # Sync working tree to the branch tip
    prefix = repo.root.rstrip("/") + "/"
    tracked = repo.tracked_files(name)
    current = _worktree(state, repo.root)
    for rel in current:
        if rel not in tracked and rel in repo.tracked_files():
            state.vfs.pop(prefix + rel, None)
    for rel, content in tracked.items():
        state.write_file(prefix + rel, content)
    return f"Switched to branch '{name}'"


def _git_checkout(repo: GitRepo, state, rest: list[str]) -> str:
    create = "-b" in rest or "-B" in rest
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 1
        return "fatal: branch name required"
    name = pos[0]
    if not create and name not in repo.branches:
        # `git checkout -- <file>` / checkout a path: restore from HEAD
        rel = _rel_to_root(state, repo, name)
        tracked = repo.tracked_files()
        if rel in tracked:
            state.write_file(repo.root.rstrip("/") + "/" + rel, tracked[rel])
            return ""
    return _checkout_branch(repo, state, name, create)


def _git_switch(repo: GitRepo, state, rest: list[str]) -> str:
    create = "-c" in rest or "-C" in rest
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 1
        return "fatal: missing branch or commit argument"
    return _checkout_branch(repo, state, pos[0], create)


def _git_merge(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if "--abort" in rest:
        repo.merge_conflict = False
        repo.conflict_files = []
        return ""
    if not pos:
        state.last_exit_code = 1
        return "fatal: No commit specified and merge.defaultToUpstream not set."
    other = pos[0]
    if other not in repo.branches:
        state.last_exit_code = 1
        return f"merge: {other} - not something we can merge"
    ours = repo.commits()
    theirs = repo.branches[other]
    ours_hashes = {c["hash"] for c in ours}
    new_commits = [c for c in theirs if c["hash"] not in ours_hashes]
    if not new_commits:
        return "Already up to date."
    # Fast-forward when current branch is a strict prefix of the other
    theirs_hashes = {c["hash"] for c in theirs}
    prefix = repo.root.rstrip("/") + "/"
    if all(c["hash"] in theirs_hashes for c in ours):
        repo.branches[repo.head] = list(theirs)
        for rel, content in repo.tracked_files().items():
            state.write_file(prefix + rel, content)
        tip = theirs[-1]["hash"][:7]
        return (
            f"Updating {ours[-1]['hash'][:7] if ours else '0000000'}..{tip}\n"
            "Fast-forward\n"
            f" {len(new_commits)} commit{'s' if len(new_commits) != 1 else ''} applied"
        )
    # True merge: overlay their files, create a merge commit
    files = repo.tracked_files()
    files.update(repo.tracked_files(other))
    commit = repo.make_commit(f"Merge branch '{other}' into {repo.head}", files)
    commit["parents"] = [ours[-1]["hash"], theirs[-1]["hash"]]
    repo.branches[repo.head].append(commit)
    for rel, content in files.items():
        state.write_file(prefix + rel, content)
    return (
        f"Merge made by the 'ort' strategy.\n"
        f" {len(new_commits)} commit{'s' if len(new_commits) != 1 else ''} merged from {other}"
    )


def _git_diff(repo: GitRepo, state, rest: list[str]) -> str:
    tree = _worktree(state, repo.root)
    tracked = repo.tracked_files()
    staged_mode = "--staged" in rest or "--cached" in rest
    out = []
    items = repo.staged.items() if staged_mode else [
        (rel, tree.get(rel)) for rel in sorted(set(tree) | set(tracked))
        if tree.get(rel) != tracked.get(rel) and rel not in repo.staged
    ]
    for rel, new in items:
        old = tracked.get(rel, "")
        if new == old:
            continue
        out.append(f"diff --git a/{rel} b/{rel}")
        out.append(f"--- a/{rel}" if old else "--- /dev/null")
        out.append(f"+++ b/{rel}" if new is not None else "+++ /dev/null")
        for ln in (old or "").splitlines():
            if ln not in (new or "").splitlines():
                out.append(f"-{ln}")
        for ln in (new or "").splitlines():
            if ln not in (old or "").splitlines():
                out.append(f"+{ln}")
    return "\n".join(out)


def _git_remote(repo: GitRepo, state, rest: list[str]) -> str:
    if rest and rest[0] == "add" and len(rest) >= 3:
        repo.remotes[rest[1]] = rest[2]
        return ""
    if rest and rest[0] == "remove" and len(rest) >= 2:
        repo.remotes.pop(rest[1], None)
        return ""
    if "-v" in rest:
        rows = []
        for name, url in sorted(repo.remotes.items()):
            rows.append(f"{name}\t{url} (fetch)")
            rows.append(f"{name}\t{url} (push)")
        return "\n".join(rows)
    return "\n".join(sorted(repo.remotes))


def _git_push(repo: GitRepo, state, rest: list[str]) -> str:
    if "origin" not in repo.remotes:
        state.last_exit_code = 128
        return "fatal: No configured push destination."
    pos = [a for a in rest if not a.startswith("-")]
    branch = pos[1] if len(pos) > 1 else repo.head
    if branch not in repo.branches:
        state.last_exit_code = 1
        return f"error: src refspec {branch} does not match any"
    total = len(repo.branches[branch])
    pushed = repo.pushed_counts.get(branch, 0)
    new = total - pushed
    repo.pushed_counts[branch] = total
    url = repo.remotes["origin"]
    if new <= 0:
        return "Everything up-to-date"
    tip = repo.branches[branch][-1]["hash"][:7]
    upstream = f"\nbranch '{branch}' set up to track 'origin/{branch}'." if "-u" in rest or "--set-upstream" in rest else ""
    return (
        f"Enumerating objects: {new * 3}, done.\n"
        f"Counting objects: 100% ({new * 3}/{new * 3}), done.\n"
        f"Writing objects: 100% ({new * 3}/{new * 3}), 1.{new}2 KiB | 1.2 MiB/s, done.\n"
        f"To {url}\n"
        f"   {_short_hash(branch)}..{tip}  {branch} -> {branch}{upstream}"
    )


def _git_pull(repo: GitRepo, state, rest: list[str]) -> str:
    if "origin" not in repo.remotes:
        state.last_exit_code = 1
        return "fatal: no remote repository specified."
    return "Already up to date."


def _git_fetch(repo: GitRepo, state, rest: list[str]) -> str:
    return ""


def _git_stash(repo: GitRepo, state, rest: list[str]) -> str:
    tree = _worktree(state, repo.root)
    modified, untracked, deleted = _changes(repo, tree)
    sub = rest[0] if rest else "push"
    if sub == "list":
        return "\n".join(
            f"stash@{{{i}}}: WIP on {s['branch']}: {s['message']}"
            for i, s in enumerate(reversed(repo.stash))
        )
    if sub == "pop" or sub == "apply":
        if not repo.stash:
            state.last_exit_code = 1
            return "No stash entries found."
        entry = repo.stash[-1] if sub == "apply" else repo.stash.pop()
        prefix = repo.root.rstrip("/") + "/"
        for rel, content in entry["files"].items():
            state.write_file(prefix + rel, content)
        return f"On branch {repo.head}\nChanges restored from stash."
    # push / default
    if not modified and not deleted:
        return "No local changes to save"
    files = {rel: tree[rel] for rel in modified}
    repo.stash.append({"branch": repo.head, "message": "local changes", "files": files})
    tracked = repo.tracked_files()
    prefix = repo.root.rstrip("/") + "/"
    for rel in modified:
        state.write_file(prefix + rel, tracked.get(rel, ""))
    return f"Saved working directory and index state WIP on {repo.head}"


def _git_reset(repo: GitRepo, state, rest: list[str]) -> str:
    hard = "--hard" in rest
    pos = [a for a in rest if not a.startswith("-")]
    target = pos[0] if pos else ""
    if target.startswith("HEAD~"):
        n = int(target[5:] or 1)
        commits = repo.commits()
        if len(commits) <= n:
            state.last_exit_code = 128
            return f"fatal: ambiguous argument '{target}': unknown revision"
        repo.branches[repo.head] = commits[:-n]
        repo.pushed_counts[repo.head] = min(repo.pushed_counts.get(repo.head, 0), len(commits) - n)
        if hard:
            prefix = repo.root.rstrip("/") + "/"
            for rel, content in repo.tracked_files().items():
                state.write_file(prefix + rel, content)
            repo.staged = {}
        tip = repo.commits()[-1]
        return f"HEAD is now at {tip['hash'][:7]} {tip['message']}"
    if target and target != "HEAD":
        # unstage single file
        rel = _rel_to_root(state, repo, target)
        repo.staged.pop(rel, None)
        return f"Unstaged changes after reset:\nM\t{rel}"
    repo.staged = {}
    if hard:
        prefix = repo.root.rstrip("/") + "/"
        for rel, content in repo.tracked_files().items():
            state.write_file(prefix + rel, content)
        tip = repo.commits()[-1] if repo.commits() else None
        if tip:
            return f"HEAD is now at {tip['hash'][:7]} {tip['message']}"
    return ""


def _git_revert(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 129
        return "usage: git revert <commit>"
    ref = pos[0]
    commits = repo.commits()
    target = None
    if ref == "HEAD" and commits:
        target = commits[-1]
    else:
        target = next((c for c in commits if c["hash"].startswith(ref)), None)
    if target is None:
        state.last_exit_code = 128
        return f"fatal: bad revision '{ref}'"
    idx = commits.index(target)
    files = dict(commits[idx - 1]["files"]) if idx > 0 else {}
    # keep files added after the reverted commit
    current = repo.tracked_files()
    for rel in current:
        if rel not in target["files"]:
            files[rel] = current[rel]
    commit = repo.make_commit(f'Revert "{target["message"]}"', files)
    repo.branches[repo.head].append(commit)
    prefix = repo.root.rstrip("/") + "/"
    for rel, content in files.items():
        state.write_file(prefix + rel, content)
    return f"[{repo.head} {commit['hash'][:7]}] Revert \"{target['message']}\""


def _git_tag(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if "-d" in rest and pos:
        if pos[0] in repo.tags:
            h = repo.tags.pop(pos[0])
            return f"Deleted tag '{pos[0]}' (was {h[:7]})"
        state.last_exit_code = 1
        return f"error: tag '{pos[0]}' not found."
    if pos:
        tip = repo.commits()[-1] if repo.commits() else None
        if tip is None:
            state.last_exit_code = 128
            return "fatal: Failed to resolve 'HEAD' as a valid ref."
        repo.tags[pos[0]] = tip["hash"]
        return ""
    return "\n".join(sorted(repo.tags))


def _git_rebase(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if "--abort" in rest or "--continue" in rest:
        return ""
    if not pos:
        state.last_exit_code = 1
        return "fatal: invalid upstream"
    other = pos[0]
    if other not in repo.branches:
        state.last_exit_code = 128
        return f"fatal: invalid upstream '{other}'"
    base = repo.branches[other]
    base_hashes = {c["hash"] for c in base}
    own = [c for c in repo.commits() if c["hash"] not in base_hashes]
    repo.branches[repo.head] = list(base) + own
    prefix = repo.root.rstrip("/") + "/"
    for rel, content in repo.tracked_files().items():
        state.write_file(prefix + rel, content)
    return f"Successfully rebased and updated refs/heads/{repo.head}."


def _git_cherry_pick(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 129
        return "usage: git cherry-pick <commit>"
    ref = pos[0]
    source = None
    for commits in repo.branches.values():
        source = next((c for c in commits if c["hash"].startswith(ref)), None)
        if source:
            break
    if source is None:
        state.last_exit_code = 128
        return f"fatal: bad revision '{ref}'"
    files = repo.tracked_files()
    files.update(source["files"])
    commit = repo.make_commit(source["message"], files)
    repo.branches[repo.head].append(commit)
    prefix = repo.root.rstrip("/") + "/"
    for rel, content in files.items():
        state.write_file(prefix + rel, content)
    return f"[{repo.head} {commit['hash'][:7]}] {source['message']}"


def _git_show(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    commits = repo.commits()
    if not commits:
        state.last_exit_code = 128
        return "fatal: your current branch does not have any commits yet"
    target = commits[-1]
    if pos and pos[0] != "HEAD":
        target = next((c for c in commits if c["hash"].startswith(pos[0])), None)
        if target is None:
            state.last_exit_code = 128
            return f"fatal: bad revision '{pos[0]}'"
    return (
        f"commit {target['hash']}\n"
        f"Author: {target['author']} <{target['email']}>\n"
        f"Date:   {_fmt_date(target['ts'])}\n\n"
        f"    {target['message']}\n\n"
        + "\n".join(f" {rel} | changed" for rel in sorted(target["files"]))
    )


def _git_rm(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 129
        return "usage: git rm <file>"
    out = []
    for p in pos:
        rel = _rel_to_root(state, repo, p)
        if rel not in repo.tracked_files():
            state.last_exit_code = 128
            return f"fatal: pathspec '{p}' did not match any files"
        repo.staged[rel] = None
        state.vfs.pop(repo.root.rstrip("/") + "/" + rel, None)
        out.append(f"rm '{rel}'")
    return "\n".join(out)


def _git_mv(repo: GitRepo, state, rest: list[str]) -> str:
    pos = [a for a in rest if not a.startswith("-")]
    if len(pos) < 2:
        state.last_exit_code = 129
        return "usage: git mv <source> <destination>"
    src_rel = _rel_to_root(state, repo, pos[0])
    dst_rel = _rel_to_root(state, repo, pos[1])
    prefix = repo.root.rstrip("/") + "/"
    content = state.read_file(prefix + src_rel)
    if content is None:
        state.last_exit_code = 128
        return f"fatal: bad source, source={pos[0]}"
    state.write_file(prefix + dst_rel, content)
    state.vfs.pop(prefix + src_rel, None)
    repo.staged[dst_rel] = content
    repo.staged[src_rel] = None
    return ""


def _git_restore(repo: GitRepo, state, rest: list[str]) -> str:
    staged_mode = "--staged" in rest
    pos = [a for a in rest if not a.startswith("-")]
    if not pos:
        state.last_exit_code = 129
        return "fatal: you must specify path(s) to restore"
    for p in pos:
        rel = _rel_to_root(state, repo, p) if p != "." else "."
        if staged_mode:
            if rel == ".":
                repo.staged = {}
            else:
                repo.staged.pop(rel, None)
        else:
            tracked = repo.tracked_files()
            prefix = repo.root.rstrip("/") + "/"
            if rel == ".":
                for r, content in tracked.items():
                    state.write_file(prefix + r, content)
            elif rel in tracked:
                state.write_file(prefix + rel, tracked[rel])
    return ""
