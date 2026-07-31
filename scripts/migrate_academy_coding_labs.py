#!/usr/bin/env python3
"""Convert academy JavaScript/React labs from systemd drills to Coding IDE labs.

Rewrites scenario.yaml (coding_mode + coding_spec), vestigial check.sh, and strips
those slugs from generated academy_service_presets / e2e fix maps.

Usage:
  python3 scripts/migrate_academy_coding_labs.py [--dry-run] [--technology javascript|react]
"""
from __future__ import annotations

import argparse
import re
import stat
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCEN = ROOT / "scenarios"
PRESET_OUT = ROOT / "backend/apps/labs/provisioner/simulation/academy_service_presets.py"
E2E_OUT = ROOT / "backend/apps/labs/provisioner/simulation/academy_service_e2e_fixes.py"

CODING_TECHS = ("javascript", "react")

# Topic → coding_spec builder. `n` is the cycle variant (1..10) for mild uniqueness.
def _js(n: int) -> dict[str, dict]:
    return {
        "arrays": {
            "fn": "arraySum",
            "instructions": (
                f"Implement arraySum(arr) → number. Empty array → 0. "
                f"Variant {n}: ignore non-numbers by coercing with Number()."
            ),
            "stub": "function arraySum(arr) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(arraySum([1,2,3]) === 6, String(arraySum([1,2,3])));"),
                ("single", "assert(arraySum([10]) === 10, String(arraySum([10])));"),
            ],
            "hidden": [
                ("empty", "assert(arraySum([]) === 0);"),
                ("neg", f"assert(arraySum([-1, {n}, 1]) === {n});"),
            ],
        },
        "objects": {
            "fn": "pick",
            "instructions": "Implement pick(obj, keys) → new object with only listed keys. Do not mutate obj.",
            "stub": "function pick(obj, keys) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(JSON.stringify(pick({a:1,b:2,c:3}, ['a','c'])) === JSON.stringify({a:1,c:3}));"),
            ],
            "hidden": [
                ("missing", "assert(JSON.stringify(pick({a:1}, ['a','z'])) === JSON.stringify({a:1}));"),
                ("empty", "assert(JSON.stringify(pick({a:1}, [])) === JSON.stringify({}));"),
                ("no-mutate", "const o={a:1,b:2}; pick(o,['a']); assert(o.b===2);"),
            ],
        },
        "async-await": {
            "fn": "thenMap",
            "instructions": (
                "Implement thenMap(value, fn) → fn(value). "
                "(Sync warm-up for promise pipelines — no timers.)"
            ),
            "stub": "function thenMap(value, fn) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(thenMap(5, x => x * 2) === 10);"),
            ],
            "hidden": [
                ("str", "assert(thenMap('a', x => x + 'b') === 'ab');"),
                ("n", f"assert(thenMap({n}, x => x + 1) === {n + 1});"),
            ],
        },
        "modules": {
            "fn": "compose",
            "instructions": "Implement compose(f, g) so compose(f,g)(x) === f(g(x)).",
            "stub": "function compose(f, g) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "const f=x=>x+1,g=x=>x*2; assert(compose(f,g)(3)===7);"),
            ],
            "hidden": [
                ("id", "const id=x=>x; assert(compose(id,id)(5)===5);"),
                ("order", f"assert(compose(x=>x+{n}, x=>x*2)(2)==={4+n});"),
            ],
        },
        "dom": {
            "fn": "buildButtonLabel",
            "instructions": "Implement buildButtonLabel(count) → `Click (N)` string for a button label (DOM-less).",
            "stub": "function buildButtonLabel(count) {\n  // TODO\n}\n",
            "visible": [
                ("zero", "assert(buildButtonLabel(0) === 'Click (0)');"),
            ],
            "hidden": [
                ("n", f"assert(buildButtonLabel({n}) === 'Click ({n})');"),
                ("ten", "assert(buildButtonLabel(10) === 'Click (10)');"),
            ],
        },
        "fetch": {
            "fn": "parseJsonSafe",
            "instructions": "Implement parseJsonSafe(text) → parsed value or null on invalid JSON.",
            "stub": "function parseJsonSafe(text) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(parseJsonSafe('{\"a\":1}').a === 1);"),
            ],
            "hidden": [
                ("bad", "assert(parseJsonSafe('{') === null);"),
                ("num", f"assert(parseJsonSafe('{n}') === {n});"),
            ],
        },
        "testing": {
            "fn": "assertEqual",
            "instructions": "Implement assertEqual(a, b) that throws Error with message if a !== b, else returns true.",
            "stub": "function assertEqual(a, b) {\n  // TODO\n}\n",
            "visible": [
                ("pass", "assert(assertEqual(1, 1) === true);"),
            ],
            "hidden": [
                ("fail", "let threw=false; try { assertEqual(1, 2); } catch (e) { threw=true; } assert(threw);"),
                ("str", f"assert(assertEqual('v{n}', 'v{n}') === true);"),
            ],
        },
        "bundling": {
            "fn": "entryPath",
            "instructions": "Implement entryPath(dir, file) → join with '/' without double slashes.",
            "stub": "function entryPath(dir, file) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(entryPath('src', 'main.js') === 'src/main.js');"),
            ],
            "hidden": [
                ("slash", "assert(entryPath('src/', 'main.js') === 'src/main.js');"),
                ("root", f"assert(entryPath('', 'a{n}.js') === 'a{n}.js');"),
            ],
        },
        "forms": {
            "fn": "validateEmail",
            "instructions": "Implement validateEmail(s) → true if string contains '@' and a '.' after '@'.",
            "stub": "function validateEmail(s) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(validateEmail('a@b.co') === true);"),
            ],
            "hidden": [
                ("no-at", "assert(validateEmail('ab.co') === false);"),
                ("no-dot", "assert(validateEmail('a@b') === false);"),
                ("ok2", f"assert(validateEmail('u{n}@ex.com') === true);"),
            ],
        },
        "performance": {
            "fn": "unique",
            "instructions": "Implement unique(arr) → new array of first-seen values (stable order).",
            "stub": "function unique(arr) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(JSON.stringify(unique([1,1,2,2,3])) === JSON.stringify([1,2,3]));"),
            ],
            "hidden": [
                ("empty", "assert(JSON.stringify(unique([])) === JSON.stringify([]));"),
                ("str", f"assert(JSON.stringify(unique(['a','a','b{n}'])) === JSON.stringify(['a','b{n}']));"),
            ],
        },
    }


def _react(n: int) -> dict[str, dict]:
    # Graded as pure JS (no React runtime in CodingIDE).
    return {
        "components": {
            "fn": "createGreeting",
            "instructions": "Implement createGreeting(name) → `{ type: 'h1', props: { children: 'Hello, NAME' } }` (pseudo-component).",
            "stub": "function createGreeting(name) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "const n=createGreeting('Ada'); assert(n.type==='h1' && n.props.children==='Hello, Ada');"),
            ],
            "hidden": [
                ("n", f"assert(createGreeting('U{n}').props.children==='Hello, U{n}');"),
            ],
        },
        "state": {
            "fn": "createCounter",
            "instructions": "Implement createCounter(initial) returning { get value(), inc(), dec() }.",
            "stub": "function createCounter(initial = 0) {\n  // TODO\n}\n",
            "visible": [
                ("start", "const c=createCounter(1); assert(c.value===1); c.inc(); assert(c.value===2);"),
            ],
            "hidden": [
                ("dec", "const c=createCounter(0); c.dec(); assert(c.value===-1);"),
                ("n", f"const c=createCounter({n}); c.inc(); assert(c.value==={n+1});"),
            ],
        },
        "effects": {
            "fn": "once",
            "instructions": "Implement once(fn) → wrapper that calls fn only on the first invocation.",
            "stub": "function once(fn) {\n  // TODO\n}\n",
            "visible": [
                ("once", "let n=0; const f=once(()=>{n+=1; return n;}); assert(f()===1); assert(f()===1);"),
            ],
            "hidden": [
                ("args", f"const f=once((x)=>x*{n}); assert(f(2)==={2*n}); assert(f(9)==={2*n});"),
            ],
        },
        "router": {
            "fn": "matchPath",
            "instructions": "Implement matchPath(pattern, path) → true when equal or pattern is '*'.",
            "stub": "function matchPath(pattern, path) {\n  // TODO\n}\n",
            "visible": [
                ("eq", "assert(matchPath('/a', '/a') === true);"),
                ("star", "assert(matchPath('*', '/x') === true);"),
            ],
            "hidden": [
                ("no", "assert(matchPath('/a', '/b') === false);"),
                ("n", f"assert(matchPath('/v{n}', '/v{n}') === true);"),
            ],
        },
        "forms": {
            "fn": "required",
            "instructions": "Implement required(value) → true if string trim length > 0.",
            "stub": "function required(value) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(required('hi') === true);"),
                ("blank", "assert(required('  ') === false);"),
            ],
            "hidden": [
                ("empty", "assert(required('') === false);"),
                ("n", f"assert(required('x{n}') === true);"),
            ],
        },
        "accessibility": {
            "fn": "ariaLabel",
            "instructions": "Implement ariaLabel(action, name) → `action name` (e.g. 'Close dialog').",
            "stub": "function ariaLabel(action, name) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(ariaLabel('Close', 'dialog') === 'Close dialog');"),
            ],
            "hidden": [
                ("n", f"assert(ariaLabel('Open', 'menu{n}') === 'Open menu{n}');"),
            ],
        },
        "performance": {
            "fn": "memoize",
            "instructions": "Implement memoize(fn) caching last single-argument result.",
            "stub": "function memoize(fn) {\n  // TODO\n}\n",
            "visible": [
                ("cache", "let calls=0; const f=memoize(x=>{calls+=1; return x*2;}); assert(f(2)===4); assert(f(2)===4); assert(calls===1);"),
            ],
            "hidden": [
                ("diff", f"const f=memoize(x=>x+{n}); assert(f(1)==={1+n}); assert(f(2)==={2+n});"),
            ],
        },
        "error-boundaries": {
            "fn": "safeRender",
            "instructions": "Implement safeRender(fn) → fn() result, or { error: true, message } if fn throws.",
            "stub": "function safeRender(fn) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(safeRender(() => 1) === 1);"),
            ],
            "hidden": [
                ("err", "const r=safeRender(()=>{throw new Error('boom');}); assert(r.error===true && /boom/.test(r.message));"),
                ("n", f"assert(safeRender(() => {n}) === {n});"),
            ],
        },
        "context": {
            "fn": "createStore",
            "instructions": "Implement createStore(initial) → { getState(), setState(v) }.",
            "stub": "function createStore(initial) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "const s=createStore(0); assert(s.getState()===0); s.setState(2); assert(s.getState()===2);"),
            ],
            "hidden": [
                ("obj", f"const s=createStore({{n:{n}}}); assert(s.getState().n==={n});"),
            ],
        },
        "testing": {
            "fn": "shallowEqual",
            "instructions": "Implement shallowEqual(a, b) for plain objects (same keys + === values).",
            "stub": "function shallowEqual(a, b) {\n  // TODO\n}\n",
            "visible": [
                ("eq", "assert(shallowEqual({a:1}, {a:1}) === true);"),
                ("neq", "assert(shallowEqual({a:1}, {a:2}) === false);"),
            ],
            "hidden": [
                ("keys", "assert(shallowEqual({a:1}, {a:1,b:2}) === false);"),
                ("n", f"assert(shallowEqual({{v:{n}}}, {{v:{n}}}) === true);"),
            ],
        },
    }


def parse_slug(slug: str) -> tuple[str, int, str, str, int] | None:
    """academy-{tech}-{seq:03d}-{kind}-{topic}[-cycle] → tech, seq, kind, topic, cycle."""
    m = re.match(
        r"^academy-(javascript|react)-(\d{3})-(learn|build|operate|troubleshoot|production|"
        r"security|automation|observability|backup|integration)-(.+)$",
        slug,
    )
    if not m:
        return None
    tech, seq_s, kind, rest = m.group(1), m.group(2), m.group(3), m.group(4)
    cycle = 1
    cm = re.match(r"^(.+)-(\d+)$", rest)
    if cm:
        topic, cycle = cm.group(1), int(cm.group(2))
    else:
        topic = rest
    return tech, int(seq_s), kind, topic, cycle


def build_coding_spec(tech: str, topic: str, cycle: int) -> dict | None:
    catalog = _js(cycle) if tech == "javascript" else _react(cycle)
    # normalize topic aliases
    key = topic
    if key not in catalog:
        key = topic.replace("_", "-")
    if key not in catalog:
        return None
    t = catalog[key]
    return {
        "language": "javascript",
        "entrypoint": "solution.js",
        "kind": "impl",
        "instructions": t["instructions"] + "\nClick Run to try it, then Check Solution to grade.\n",
        "files": [
            {"path": "solution.js", "content": t["stub"], "readonly": False},
        ],
        "visible_tests": [{"name": name, "code": code} for name, code in t["visible"]],
        "hidden_tests": [{"name": name, "code": code} for name, code in t["hidden"]],
        "timeout": 8,
    }


def patch_yaml(path: Path, tech: str, topic: str, cycle: int, *, dry_run: bool) -> bool:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    spec = build_coding_spec(tech, topic, cycle)
    if not spec:
        print(f"  SKIP unknown topic {topic} in {path.parent.name}")
        return False
    data["coding_mode"] = True
    data["simulation_type"] = "python"
    data["coding_spec"] = spec
    # Grading is hidden_tests — rewrite task validation language lightly
    fn = spec["files"][0]["path"]
    topic_label = topic.replace("-", " ")
    data["objectives"] = [
        f"Implement the required function in {fn}",
        "Pass visible tests with Run",
        "Pass Check Solution (hidden tests)",
    ]
    data["initial_state"] = (
        f"Coding challenge: {topic_label}. "
        "The stub in solution.js is incomplete so tests fail until you implement it."
    )
    # Rewrite ticket description verify language away from systemd
    desc = str(data.get("description") or "")
    if "systemctl" in desc or "node-app" in desc:
        data["description"] = (
            f"CONTEXT: Complete the {topic_label} coding exercise in the browser IDE.\n\n"
            f"ENVIRONMENT: FixitLab JavaScript/React practice IDE — edit solution.js, "
            f"Run visible tests, then Check Solution.\n\n"
            f"SYMPTOM / STARTING STATE: {data['initial_state']}\n\n"
            f"OBJECTIVE: Implement the required function so all visible and hidden tests pass.\n\n"
            f"VERIFY: Check Solution passes all hidden tests.\n"
        )
    if "tasks" in data and isinstance(data["tasks"], list) and data["tasks"]:
        data["tasks"][0]["validation"] = {
            "type": "script",
            "script": "hidden_tests",
            "error_message": "Hidden tests still failing — keep iterating in the IDE.",
        }
        data["tasks"][0]["description"] = (
            f"Implement the {topic_label} exercise in the browser IDE and pass all tests."
        )
    if "solution" in data and isinstance(data["solution"], dict):
        data["solution"] = {
            "summary": "Implement the function so visible and hidden tests pass in the coding IDE.",
            "files_changed": ["solution.js"],
            "commands_run": [],
            "reference_docs": data.get("linked_tutorial") or tech,
        }
    # Soften systemd hints
    new_hints = []
    for h in data.get("hints") or []:
        if not isinstance(h, dict):
            continue
        content = str(h.get("content") or "")
        if "systemctl" in content or "journalctl" in content:
            order = h.get("order", 3)
            if order <= 2:
                new_hints.append(h)
            elif order == 3:
                new_hints.append({
                    "order": 3,
                    "cost": h.get("cost", 25),
                    "content": (
                        "WHICH TOOL — use the IDE Run button on visible tests first; "
                        "read the failing assertion message carefully."
                    ),
                })
            elif order == 4:
                new_hints.append({
                    "order": 4,
                    "cost": h.get("cost", 40),
                    "content": (
                        "NARROW DOWN — implement the smallest change that satisfies one failing test, "
                        "then re-run."
                    ),
                })
            else:
                new_hints.append({
                    "order": 5,
                    "cost": h.get("cost", 60),
                    "content": (
                        "NEAR-SOLUTION — finish the function so all visible tests pass, then Check Solution."
                    ),
                })
        else:
            new_hints.append(h)
    if new_hints:
        data["hints"] = new_hints
    if dry_run:
        return True
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    check = path.parent / "check.sh"
    check.write_text(
        "#!/usr/bin/env bash\n"
        "# coding_mode lab — graded by hidden_tests via /code-validate/\n"
        "exit 0\n",
        encoding="utf-8",
    )
    check.chmod(check.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def strip_generated_maps(slugs: set[str], *, dry_run: bool) -> None:
    """Remove migrated slugs from generated preset/e2e Python modules."""
    for path in (PRESET_OUT, E2E_OUT):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        removed = 0
        for line in lines:
            if any(f"'{slug}'" in line or f'"{slug}"' in line for slug in slugs):
                # Keep frozenset/dict structural lines; drop entry lines for our slugs
                if line.strip().startswith(("'", '"')) or "academy-javascript-" in line or "academy-react-" in line:
                    if any(s in line for s in slugs):
                        removed += 1
                        continue
            out.append(line)
        print(f"  {path.name}: removed ~{removed} lines")
        if not dry_run:
            path.write_text("".join(out), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--technology", default="", help="javascript or react")
    args = parser.parse_args()
    techs = [args.technology] if args.technology else list(CODING_TECHS)
    migrated: set[str] = set()
    for tech in techs:
        if tech not in CODING_TECHS:
            raise SystemExit(f"unsupported tech {tech}")
        count = 0
        for folder in sorted((SCEN / tech).glob("academy-*")):
            yaml_path = folder / "scenario.yaml"
            if not yaml_path.is_file():
                continue
            parsed = parse_slug(folder.name)
            if not parsed:
                print(f"  SKIP unparsable {folder.name}")
                continue
            t, _seq, _kind, topic, cycle = parsed
            ok = patch_yaml(yaml_path, t, topic, cycle, dry_run=args.dry_run)
            if ok:
                migrated.add(folder.name)
                count += 1
        print(f"{tech}: migrated {count} labs")
    print(f"total migrated: {len(migrated)}")
    strip_generated_maps(migrated, dry_run=args.dry_run)
    print("done" + (" (dry-run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
