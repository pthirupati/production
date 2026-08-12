"""Engine layer for the public, free "Playgrounds".

Playgrounds are lightweight, anonymous, *ephemeral* sandboxes that let a visitor
try the platform's existing engines without a lab or subscription. This module
deliberately REUSES the engines that already power authenticated labs rather
than duplicating them:

    * Terminal playgrounds (Linux / Git / Docker / Kubernetes / Ansible /
      Jenkins / Bash) run on ``UnifiedSimulationEngine`` — the same RHEL shell
      simulator the real labs use. Each playground picks a ``simulation_type``
      persona so the relevant command set is front-and-centre.
    * The SQL playground runs on Python's stdlib ``sqlite3`` (no external DB, no
      paid API) in a per-session in-memory database, so a visitor can CREATE /
      INSERT / SELECT against real SQL semantics.
    * Code-runner playgrounds (Python / JavaScript) reuse ``apps.labs`` code
      execution: the locked-down ``sandbox_runner`` container when available,
      falling back to the same in-process restricted subprocess used by CI.

Ephemerality / abuse-resistance:
    * No database rows are written for a playground session — ALL state lives in
      process memory (terminal/SQL) and is evicted after a short idle timeout
      (:data:`IDLE_TTL_SECONDS`). A process restart wipes everything, which is
      exactly the "no persistence" contract.
    * A hard cap on the number of concurrently-tracked sessions
      (:data:`MAX_SESSIONS`) plus per-action input limits bound memory use.
    * The view layer applies a per-IP rate limit on top of this.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

# ── Tunables ─────────────────────────────────────────────────────────────────
IDLE_TTL_SECONDS = 15 * 60          # evict a sandbox after 15 min of inactivity
MAX_SESSIONS = 500                  # hard ceiling on concurrently-tracked sandboxes
MAX_COMMAND_LEN = 4_000             # reject absurdly long command lines
MAX_SQL_LEN = 8_000                 # reject absurdly long SQL
MAX_OUTPUT_CHARS = 40_000           # truncate runaway output
MAX_SQL_ROWS = 500                  # cap rows returned from a SELECT
SQL_BUSY_TIMEOUT_S = 2.0            # sqlite lock wait

# ── Playground catalogue ─────────────────────────────────────────────────────
# slug -> definition. ``kind`` selects the engine; ``sim_type`` is the
# UnifiedSimulationEngine persona for terminal playgrounds.
PLAYGROUNDS: "OrderedDict[str, dict]" = OrderedDict()


def _register(slug: str, **meta) -> None:
    PLAYGROUNDS[slug] = {"slug": slug, **meta}


# Terminal playgrounds — all reuse UnifiedSimulationEngine.
_register(
    "linux", kind="terminal", sim_type="generic",
    name="Online Linux Terminal",
    tagline="A real shell experience — files, processes, permissions, text tools.",
    category="Operating Systems",
    icon="terminal",
    starter=["whoami", "ls -la", "uname -a", "cat /etc/os-release"],
    scenario_slug="",
)
_register(
    "bash", kind="terminal", sim_type="generic",
    name="Bash Scripting Playground",
    tagline="Write and run shell snippets — variables, loops, pipes, conditionals.",
    category="Operating Systems",
    icon="square-terminal",
    starter=["for i in 1 2 3; do echo \"line $i\"; done", "echo $HOME", "ls /etc | head"],
    scenario_slug="",
)
# Git has no standalone command engine in the simulator, so rather than fake it
# we route this card to a real Git/CI lab scenario (per the "link, don't fake"
# rule). The matching tutorial still teaches the full workflow.
_register(
    "git", kind="lab_link",
    name="Git & CI Practice",
    tagline="Practise Git and pipeline troubleshooting in a real, guided lab.",
    category="DevOps",
    icon="git-branch",
    scenario_slug="cicd-pipeline-broken",
)
_register(
    "docker", kind="terminal", sim_type="docker",
    name="Docker Playground",
    tagline="Run docker commands — images, containers, ps, logs, exec.",
    category="Containers",
    icon="container",
    starter=["docker version", "docker ps -a", "docker images"],
    scenario_slug="",
)
_register(
    "kubernetes", kind="terminal", sim_type="kubernetes",
    name="Kubernetes Playground",
    tagline="Explore kubectl against a simulated cluster — pods, deployments, services.",
    category="Containers",
    icon="ship-wheel",
    starter=["kubectl get nodes", "kubectl get pods -A", "kubectl get deployments"],
    scenario_slug="",
)
_register(
    "ansible", kind="terminal", sim_type="ansible",
    name="Ansible Playground",
    tagline="Try ansible / ansible-playbook and inventory commands hands-on.",
    category="DevOps",
    icon="boxes",
    starter=["ansible --version", "ansible localhost -m ping", "ansible-playbook --help"],
    scenario_slug="",
)
# Jenkins/CI is best practised end-to-end in a real lab (the playground shell
# does not simulate a Jenkins controller), so this card links to a CI scenario.
_register(
    "jenkins", kind="lab_link",
    name="Jenkins / CI Practice",
    tagline="Debug a failing CI job in a real, graded troubleshooting lab.",
    category="DevOps",
    icon="hammer",
    scenario_slug="jenkins-job-oom",
)

# SQL playground — reuses stdlib sqlite3 (free, embedded, per-session).
_register(
    "sql", kind="sql",
    name="SQL / PostgreSQL Console",
    tagline="Run real SQL — CREATE, INSERT, SELECT, JOIN — on an in-memory database.",
    category="Databases",
    icon="database",
    starter=[
        "SELECT name, role FROM employees;",
        "SELECT role, count(*) AS n FROM employees GROUP BY role;",
        "INSERT INTO employees (name, role) VALUES ('Dana', 'sre');",
    ],
    scenario_slug="",
)

# Code-runner playgrounds — reuse apps.labs sandboxed execution.
_register(
    "python", kind="code", language="python",
    name="Python Compiler",
    tagline="Write and run Python 3 instantly in a sandboxed interpreter.",
    category="Programming",
    icon="file-code",
    starter_code='print("Hello from FixitLab!")\nfor i in range(3):\n    print("square", i, i * i)\n',
    scenario_slug="",
)
_register(
    "javascript", kind="code", language="javascript",
    name="JavaScript (Node) Runner",
    tagline="Execute JavaScript with Node in an isolated sandbox.",
    category="Programming",
    icon="file-code-2",
    starter_code='console.log("Hello from FixitLab!");\n[1, 2, 3].forEach(n => console.log("cube", n, n ** 3));\n',
    scenario_slug="",
)
# Languages we expose as playground cards but route to a full lab/scenario
# instead of faking an engine (no free in-browser Java/C++ runner here).
_register(
    "java", kind="lab_link", language="java",
    name="Java Practice",
    tagline="Practise Java in a guided, graded coding lab.",
    category="Programming",
    icon="coffee",
    scenario_slug="sim-java-compile-error",
)
_register(
    "cpp", kind="lab_link", language="cpp",
    name="C++ Practice",
    tagline="Fix and build C++ in a guided coding lab.",
    category="Programming",
    icon="binary",
    scenario_slug="",  # no C++ scenario yet — CTA falls back to the catalogue
)


def public_catalogue() -> list[dict]:
    """Catalogue payload for the /playgrounds index (no engine internals)."""
    out = []
    for p in PLAYGROUNDS.values():
        out.append(
            {
                "slug": p["slug"],
                "name": p["name"],
                "tagline": p["tagline"],
                "category": p["category"],
                "icon": p.get("icon", "terminal"),
                "kind": p["kind"],
                "language": p.get("language", ""),
                "scenario_slug": p.get("scenario_slug", ""),
            }
        )
    return out


def get_definition(slug: str) -> dict | None:
    return PLAYGROUNDS.get((slug or "").lower())


# ─────────────────────────────────────────────────────────────────────────────
# Ephemeral session store (process-local). Each entry holds the live engine and
# a last-touched timestamp; idle entries are evicted lazily on access.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _Session:
    slug: str
    kind: str
    engine: Any = None                 # UnifiedSimulationEngine | sqlite3.Connection
    created: float = field(default_factory=time.time)
    touched: float = field(default_factory=time.time)
    commands: int = 0


_LOCK = threading.Lock()
_SESSIONS: "OrderedDict[str, _Session]" = OrderedDict()


def _evict_idle(now: float) -> None:
    """Drop sessions past their idle TTL and enforce the hard ceiling.

    Caller must hold ``_LOCK``.
    """
    dead = [sid for sid, s in _SESSIONS.items() if now - s.touched > IDLE_TTL_SECONDS]
    for sid in dead:
        _close_session(_SESSIONS.pop(sid, None))
    # Enforce the ceiling by evicting the least-recently-touched sessions.
    while len(_SESSIONS) > MAX_SESSIONS:
        _, victim = _SESSIONS.popitem(last=False)
        _close_session(victim)


def _close_session(session: _Session | None) -> None:
    if session is None:
        return
    if session.kind == "sql" and isinstance(session.engine, sqlite3.Connection):
        try:
            session.engine.close()
        except Exception:
            pass


def _seed_sql(conn: sqlite3.Connection) -> None:
    """Seed a friendly demo schema so the SQL console isn't an empty prompt."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            hired TEXT
        );
        INSERT INTO employees (name, role, hired) VALUES
            ('Asha',  'sre',      '2021-03-01'),
            ('Bilal', 'developer','2020-07-15'),
            ('Chen',  'developer','2022-01-10'),
            ('Devi',  'sre',      '2019-11-20'),
            ('Erik',  'manager',  '2018-05-05');

        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            severity INTEGER NOT NULL,
            assignee_id INTEGER,
            resolved INTEGER DEFAULT 0,
            FOREIGN KEY (assignee_id) REFERENCES employees(id)
        );
        INSERT INTO incidents (title, severity, assignee_id, resolved) VALUES
            ('Disk full on web-01',      2, 1, 1),
            ('5xx spike after deploy',   1, 2, 0),
            ('Certificate expiring soon',3, 4, 0),
            ('Slow database queries',    2, 3, 0);

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO products (sku, name, price_cents, stock) VALUES
            ('SKU-NIC-25G', '25GbE NIC', 24900, 12),
            ('SKU-SSD-2T',  '2TB NVMe SSD', 18900, 40),
            ('SKU-PSU-1400','1400W PSU', 32000, 8);

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        INSERT INTO orders (product_id, qty, status) VALUES
            (1, 2, 'pending'),
            (2, 1, 'shipped');
        """
    )
    conn.commit()


def rest_http_api(
    session_id: str,
    method: str,
    path: str,
    body: dict | None = None,
) -> tuple[int, Any]:
    """REST-over-SQL teaching surface on the SQL playground sqlite (audit Y3).

    Routes ``/api/products`` and ``/api/orders`` with real per-session persistence
    in the in-memory sqlite connection. Returns ``(http_status, body)``.
    """
    from urllib.parse import urlparse

    definition = get_definition("sql")
    if not definition:
        return 503, {"error": "SQL playground unavailable"}

    sess = _get_or_create(str(session_id or "rest-anon"), definition)
    conn: sqlite3.Connection = sess.engine
    method = (method or "GET").upper()
    raw = (path or "").strip()
    if "://" in raw:
        raw = urlparse(raw).path or "/"
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    norm = raw.rstrip("/") or "/"
    body = body if isinstance(body, dict) else {}

    def _rows(sql: str, args: tuple = ()) -> list[dict]:
        cur = conn.execute(sql, args)
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # /api/products[/{id}]
    if norm == "/api/products":
        if method == "GET":
            return 200, {"items": _rows("SELECT * FROM products ORDER BY id")}
        if method == "POST":
            sku = str(body.get("sku") or "").strip()
            name = str(body.get("name") or "").strip()
            if not sku or not name:
                return 400, {"error": "sku and name are required"}
            try:
                cur = conn.execute(
                    "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
                    (sku, name, int(body.get("price_cents") or 0), int(body.get("stock") or 0)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return 409, {"error": f"sku {sku!r} already exists"}
            row = _rows("SELECT * FROM products WHERE id = ?", (cur.lastrowid,))[0]
            return 201, row
        return 405, {"error": "method not allowed"}

    m = re.match(r"^/api/products/(\d+)$", norm)
    if m:
        pid = int(m.group(1))
        rows = _rows("SELECT * FROM products WHERE id = ?", (pid,))
        if method == "GET":
            if not rows:
                return 404, {"error": "product not found"}
            return 200, rows[0]
        if method == "PATCH" or method == "PUT":
            if not rows:
                return 404, {"error": "product not found"}
            fields = []
            args: list[Any] = []
            for key in ("sku", "name", "price_cents", "stock"):
                if key in body:
                    fields.append(f"{key} = ?")
                    args.append(body[key])
            if not fields:
                return 400, {"error": "no fields to update"}
            args.append(pid)
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", tuple(args))
            conn.commit()
            return 200, _rows("SELECT * FROM products WHERE id = ?", (pid,))[0]
        if method == "DELETE":
            conn.execute("DELETE FROM products WHERE id = ?", (pid,))
            conn.commit()
            return 204, {}
        return 405, {"error": "method not allowed"}

    if norm == "/api/orders":
        if method == "GET":
            return 200, {"items": _rows(
                "SELECT o.*, p.sku AS product_sku FROM orders o "
                "JOIN products p ON p.id = o.product_id ORDER BY o.id"
            )}
        if method == "POST":
            product_id = int(body.get("product_id") or 0)
            qty = int(body.get("qty") or 1)
            if product_id < 1 or qty < 1:
                return 400, {"error": "product_id and qty are required"}
            prod = _rows("SELECT id, stock FROM products WHERE id = ?", (product_id,))
            if not prod:
                return 404, {"error": "product not found"}
            if prod[0]["stock"] < qty:
                return 409, {"error": "insufficient stock"}
            cur = conn.execute(
                "INSERT INTO orders (product_id, qty, status) VALUES (?, ?, ?)",
                (product_id, qty, str(body.get("status") or "pending")),
            )
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (qty, product_id),
            )
            conn.commit()
            row = _rows("SELECT * FROM orders WHERE id = ?", (cur.lastrowid,))[0]
            return 201, row
        return 405, {"error": "method not allowed"}

    m = re.match(r"^/api/orders/(\d+)$", norm)
    if m:
        oid = int(m.group(1))
        rows = _rows("SELECT * FROM orders WHERE id = ?", (oid,))
        if method == "GET":
            if not rows:
                return 404, {"error": "order not found"}
            return 200, rows[0]
        if method == "PATCH":
            if not rows:
                return 404, {"error": "order not found"}
            status = str(body.get("status") or "").strip()
            if not status:
                return 400, {"error": "status is required"}
            conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
            conn.commit()
            return 200, _rows("SELECT * FROM orders WHERE id = ?", (oid,))[0]
        return 405, {"error": "method not allowed"}

    return 404, {"error": f"REST API: unknown path {path}"}


def _new_engine(definition: dict) -> Any:
    kind = definition["kind"]
    if kind == "terminal":
        # Imported lazily so importing this module never drags in the whole
        # simulation stack (keeps Django startup / migrations light).
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine

        return UnifiedSimulationEngine(
            scenario_slug=definition.get("scenario_slug", "") or "",
            simulation_type=definition.get("sim_type", "generic"),
        )
    if kind == "sql":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute(f"PRAGMA busy_timeout = {int(SQL_BUSY_TIMEOUT_S * 1000)}")
        _seed_sql(conn)
        return conn
    return None


def _get_or_create(session_id: str, definition: dict) -> _Session:
    now = time.time()
    with _LOCK:
        _evict_idle(now)
        sess = _SESSIONS.get(session_id)
        if sess is None or sess.slug != definition["slug"]:
            _close_session(sess)
            sess = _Session(slug=definition["slug"], kind=definition["kind"])
            sess.engine = _new_engine(definition)
            _SESSIONS[session_id] = sess
        else:
            sess.touched = now
            _SESSIONS.move_to_end(session_id)
    return sess


def _truncate(text: str) -> str:
    if text and len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n… [output truncated]"
    return text


# ── Public API used by the views ─────────────────────────────────────────────
def reset(session_id: str) -> None:
    """Drop a session's in-memory state (the "Reset" button)."""
    with _LOCK:
        _close_session(_SESSIONS.pop(session_id, None))


def terminal_banner(definition: dict) -> dict:
    """Initial prompt + welcome line for a fresh terminal playground."""
    sess = _get_or_create(f"banner-probe-{definition['slug']}", definition)
    # The probe session is only used to read the prompt; drop it immediately so
    # it doesn't count against the live-session ceiling.
    reset(f"banner-probe-{definition['slug']}")
    prompt = "$ "
    try:
        prompt = sess.engine.shell.prompt  # type: ignore[union-attr]
    except Exception:
        pass
    return {"prompt": prompt}


def run_terminal(session_id: str, definition: dict, command: str) -> dict:
    """Run a single command line on a terminal playground and return its output."""
    command = (command or "")
    if len(command) > MAX_COMMAND_LEN:
        return {"ok": False, "error": "Command is too long.", "output": "", "prompt": "$ "}
    sess = _get_or_create(session_id, definition)
    engine = sess.engine
    try:
        output = engine._handle_shell(command)  # noqa: SLF001 — documented engine hook
    except Exception:
        # A simulator bug must never 500 the public page.
        return {
            "ok": True,
            "output": "fixitlab: command could not be simulated",
            "prompt": _safe_prompt(engine),
            "commands": sess.commands,
        }
    with _LOCK:
        sess.commands += 1
        sess.touched = time.time()
    return {
        "ok": True,
        "output": _truncate(_normalize(output)),
        "prompt": _safe_prompt(engine),
        "commands": sess.commands,
    }


def _safe_prompt(engine: Any) -> str:
    try:
        return engine.shell.prompt
    except Exception:
        return "$ "


def _normalize(text: str) -> str:
    """Terminal handlers emit CRLF for xterm.js; HTTP clients want plain LF."""
    if not text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "")


def run_sql(session_id: str, definition: dict, sql: str) -> dict:
    """Execute one or more SQL statements against the session's in-memory DB."""
    sql = (sql or "").strip()
    if not sql:
        return {"ok": False, "error": "Enter a SQL statement.", "rows": [], "columns": []}
    if len(sql) > MAX_SQL_LEN:
        return {"ok": False, "error": "SQL is too long.", "rows": [], "columns": []}

    sess = _get_or_create(session_id, definition)
    conn: sqlite3.Connection = sess.engine
    cur = conn.cursor()

    # A visitor may paste several statements at once (e.g. a CREATE plus a few
    # INSERTs, or a couple of SELECTs). ``cursor.execute`` runs ONE statement, so
    # we split on top-level semicolons (respecting string literals / comments)
    # and run them in order. The result we surface is the LAST statement that
    # produced a result set (a trailing SELECT), so "INSERT …; SELECT …;" shows
    # the query output. Everything runs in a single transaction.
    statements = _split_sql(sql)
    if not statements:
        return {"ok": False, "error": "Enter a SQL statement.", "rows": [], "columns": []}

    columns: list[str] = []
    rows: list[list[Any]] = []
    truncated = False
    affected = 0
    try:
        for stmt in statements:
            cur.execute(stmt)
            if cur.description:  # this statement returns rows
                columns = [c[0] for c in cur.description]
                fetched = cur.fetchmany(MAX_SQL_ROWS + 1)
                truncated = len(fetched) > MAX_SQL_ROWS
                rows = [list(r) for r in fetched[:MAX_SQL_ROWS]]
            else:
                columns, rows, truncated = [], [], False
                if cur.rowcount and cur.rowcount > 0:
                    affected = cur.rowcount
        conn.commit()
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "rows": [],
            "columns": [],
        }

    with _LOCK:
        sess.commands += 1
        sess.touched = time.time()

    message = ""
    if not columns:
        message = f"OK — {affected} row(s) affected." if affected else "OK."
    return {
        "ok": True,
        "columns": columns,
        "rows": rows,
        "rowcount": len(rows),
        "truncated": truncated,
        "message": message,
    }


def _split_sql(sql: str) -> list[str]:
    """Split a SQL blob into individual statements on top-level semicolons.

    Respects single/double-quoted string literals and ``--`` line comments so a
    semicolon inside a string or comment does not split a statement. This is a
    pragmatic splitter for an interactive playground, not a full SQL parser.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                # Doubled quote inside a literal is an escaped quote, not a close.
                if i + 1 < n and sql[i + 1] == quote:
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            # Line comment — skip to end of line (keep it in the buffer so the
            # statement text is faithful; sqlite tolerates trailing comments).
            while i < n and sql[i] != "\n":
                buf.append(sql[i])
                i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def run_code(definition: dict, source: str, stdin: str = "") -> dict:
    """Run a code snippet via the reused apps.labs sandbox, returning stdout/stderr.

    Stateless (no session needed): each run is a one-shot sandboxed execution,
    mirroring how the lab grader executes user code — but here we surface raw
    output instead of a pass/fail verdict.
    """
    from apps.labs import code_exec

    language = (definition.get("language") or "").lower()
    source = source or ""
    if len(source) > 50_000:
        return {"ok": False, "error": "Source is too long.", "stdout": "", "stderr": ""}
    if language not in code_exec.SUPPORTED_LANGUAGES:
        return {
            "ok": False,
            "error": f"{language or 'this language'} cannot be run here — open a lab to practise it.",
            "stdout": "",
            "stderr": "",
        }
    if not code_exec.language_runtime_available(language):
        return {
            "ok": False,
            "error": f"The {language} runtime is not available on this server right now.",
            "stdout": "",
            "stderr": "",
        }

    rc, stdout, stderr, timed_out = _execute_snippet(code_exec, language, source)
    if timed_out:
        return {
            "ok": False,
            "error": "Execution timed out.",
            "stdout": _truncate(stdout or ""),
            "stderr": _truncate(stderr or ""),
        }
    return {
        "ok": rc == 0,
        "exit_code": rc,
        "stdout": _truncate(stdout or ""),
        "stderr": _truncate(stderr or ""),
    }


def _execute_snippet(code_exec, language: str, source: str):
    """Run raw user source (not a test harness) via the reused execution backend.

    Reuses ``code_exec._execute`` so the SAME locked-down container (or the
    CI/dev in-process fallback) that grades labs also powers the playground —
    no second sandbox to maintain. Fails closed: if production refuses the
    in-process path and no container is available, the snippet doesn't run.
    """
    import os
    import sys
    import tempfile

    timeout = min(code_exec.DEFAULT_TIMEOUT_SECONDS, 8)
    workdir = tempfile.mkdtemp(prefix="fixitlab_pg_")
    try:
        if language == "python":
            script_name = "main.py"
            argv = [sys.executable, "-I", "-B", os.path.join(workdir, script_name)]
        else:  # javascript
            script_name = "main.js"
            argv = ["node", os.path.join(workdir, script_name)]
        with open(os.path.join(workdir, script_name), "w", encoding="utf-8") as fh:
            fh.write(source)
        try:
            return code_exec._execute(  # noqa: SLF001 — reuse the shared backend
                language,
                source,
                script_name,
                argv,
                workdir,
                timeout,
                limit_address_space=(language != "javascript"),
            )
        except code_exec.InProcessExecutionForbidden:
            return None, "", "Code execution is unavailable in this environment.", False
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)
