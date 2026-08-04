"""Extra academy coding catalogs: java, shell-script, nodejs, python.

Java/shell/nodejs are JS-graded themed exercises (same pattern as React academy).
Python academy uses the real Python code_exec runtime (solution.py + assert tests).
"""
from __future__ import annotations


def python_catalog(n: int) -> dict[str, dict]:
    """Python-language academy topics matching generate_complete_technology_scenarios."""
    return {
        "venv": {
            "fn": "venv_python_bin",
            "instructions": (
                f"Implement venv_python_bin(root) → path to the venv interpreter "
                f"(root/bin/python). Variant {n}."
            ),
            "stub": "def venv_python_bin(root):\n    # TODO\n    pass\n",
            "visible": [
                ("basic", "assert venv_python_bin('/opt/app/.venv') == '/opt/app/.venv/bin/python'"),
            ],
            "hidden": [
                ("trail", "assert venv_python_bin('/x/') == '/x/bin/python'"),
                ("n", f"assert venv_python_bin('/v{n}') == '/v{n}/bin/python'"),
            ],
            "reference": (
                "def venv_python_bin(root):\n"
                "    r = str(root).rstrip('/')\n"
                "    return r + '/bin/python'\n"
            ),
        },
        "files": {
            "fn": "join_path",
            "instructions": "Implement join_path(base, name) → base/name with exactly one slash between.",
            "stub": "def join_path(base, name):\n    # TODO\n    pass\n",
            "visible": [
                ("basic", "assert join_path('/data', 'a.txt') == '/data/a.txt'"),
            ],
            "hidden": [
                ("slash", "assert join_path('/data/', '/a.txt') == '/data/a.txt'"),
                ("n", f"assert join_path('/p{n}', 'f') == '/p{n}/f'"),
            ],
            "reference": (
                "def join_path(base, name):\n"
                "    return str(base).rstrip('/') + '/' + str(name).lstrip('/')\n"
            ),
        },
        "http-api": {
            "fn": "json_status",
            "instructions": "Implement json_status(code) → dict {'status': code, 'ok': True if 200<=code<300 else False}.",
            "stub": "def json_status(code):\n    # TODO\n    pass\n",
            "visible": [
                ("ok", "assert json_status(200) == {'status': 200, 'ok': True}"),
            ],
            "hidden": [
                ("nf", "assert json_status(404) == {'status': 404, 'ok': False}"),
                ("n", f"assert json_status({200 + (n % 10)})['ok'] is True"),
            ],
            "reference": (
                "def json_status(code):\n"
                "    c = int(code)\n"
                "    return {'status': c, 'ok': 200 <= c < 300}\n"
            ),
        },
        "testing": {
            "fn": "assert_equal",
            "instructions": "Implement assert_equal(a, b) → True if a==b else raise AssertionError.",
            "stub": "def assert_equal(a, b):\n    # TODO\n    pass\n",
            "visible": [
                ("ok", "assert assert_equal(1, 1) is True"),
            ],
            "hidden": [
                ("fail", "raised=False\ntry:\n assert_equal(1, 2)\nexcept AssertionError:\n raised=True\nassert raised"),
                ("n", f"assert assert_equal('v{n}', 'v{n}') is True"),
            ],
            "reference": (
                "def assert_equal(a, b):\n"
                "    if a != b:\n"
                "        raise AssertionError(f'{a!r} != {b!r}')\n"
                "    return True\n"
            ),
        },
        "logging": {
            "fn": "format_log",
            "instructions": "Implement format_log(level, msg) → '[LEVEL] msg' with level uppercased.",
            "stub": "def format_log(level, msg):\n    # TODO\n    pass\n",
            "visible": [
                ("info", "assert format_log('info', 'hi') == '[INFO] hi'"),
            ],
            "hidden": [
                ("err", "assert format_log('error', 'x') == '[ERROR] x'"),
                ("n", f"assert format_log('debug', 'n{n}') == '[DEBUG] n{n}'"),
            ],
            "reference": (
                "def format_log(level, msg):\n"
                "    return f'[{str(level).upper()}] {msg}'\n"
            ),
        },
        "exceptions": {
            "fn": "safe_int",
            "instructions": "Implement safe_int(s, default=0) → int(s) or default on ValueError/TypeError.",
            "stub": "def safe_int(s, default=0):\n    # TODO\n    pass\n",
            "visible": [
                ("ok", "assert safe_int('42') == 42"),
            ],
            "hidden": [
                ("bad", "assert safe_int('x', -1) == -1"),
                ("n", f"assert safe_int('{n}') == {n}"),
            ],
            "reference": (
                "def safe_int(s, default=0):\n"
                "    try:\n"
                "        return int(s)\n"
                "    except (TypeError, ValueError):\n"
                "        return default\n"
            ),
        },
        "cli": {
            "fn": "parse_flag",
            "instructions": "Implement parse_flag(argv, name) → True if '--name' in argv else False.",
            "stub": "def parse_flag(argv, name):\n    # TODO\n    pass\n",
            "visible": [
                ("yes", "assert parse_flag(['app', '--verbose'], 'verbose') is True"),
            ],
            "hidden": [
                ("no", "assert parse_flag(['app'], 'verbose') is False"),
                ("n", f"assert parse_flag(['--v{n}'], 'v{n}') is True"),
            ],
            "reference": (
                "def parse_flag(argv, name):\n"
                "    return f'--{name}' in list(argv)\n"
            ),
        },
        "packaging": {
            "fn": "normalize_version",
            "instructions": "Implement normalize_version(v) → strip leading 'v'/'V' then return the rest.",
            "stub": "def normalize_version(v):\n    # TODO\n    pass\n",
            "visible": [
                ("v", "assert normalize_version('v1.2.3') == '1.2.3'"),
            ],
            "hidden": [
                ("plain", "assert normalize_version('2.0') == '2.0'"),
                ("n", f"assert normalize_version('V{n}.0') == '{n}.0'"),
            ],
            "reference": (
                "def normalize_version(v):\n"
                "    s = str(v)\n"
                "    return s[1:] if s[:1] in 'vV' else s\n"
            ),
        },
        "async": {
            "fn": "gather_results",
            "instructions": "Implement gather_results(items) → list of each item (identity gather for sync stub).",
            "stub": "def gather_results(items):\n    # TODO\n    pass\n",
            "visible": [
                ("list", "assert gather_results([1, 2]) == [1, 2]"),
            ],
            "hidden": [
                ("empty", "assert gather_results([]) == []"),
                ("n", f"assert gather_results([{n}]) == [{n}]"),
            ],
            "reference": "def gather_results(items):\n    return list(items)\n",
        },
        "data-processing": {
            "fn": "chunk_list",
            "instructions": "Implement chunk_list(items, size) → list of consecutive chunks of length size (last may be shorter).",
            "stub": "def chunk_list(items, size):\n    # TODO\n    pass\n",
            "visible": [
                ("basic", "assert chunk_list([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]"),
            ],
            "hidden": [
                ("odd", "assert chunk_list([1, 2, 3], 2) == [[1, 2], [3]]"),
                ("n", f"assert chunk_list(list(range({n})), {max(1, n)}) == [list(range({n}))]"),
            ],
            "reference": (
                "def chunk_list(items, size):\n"
                "    size = max(1, int(size))\n"
                "    seq = list(items)\n"
                "    return [seq[i:i + size] for i in range(0, len(seq), size)]\n"
            ),
        },
    }


def java_catalog(n: int) -> dict[str, dict]:
    return {
        "maven": {
            "fn": "parseMavenCoord",
            "instructions": (
                f"Implement parseMavenCoord(s) for 'group:artifact:version' → "
                f"{{group, artifact, version}} or null if not 3 colon-parts. Variant {n}."
            ),
            "stub": "function parseMavenCoord(s) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "const p=parseMavenCoord('com.acme:app:1.0.0'); assert(p && p.group==='com.acme' && p.artifact==='app' && p.version==='1.0.0');"),
            ],
            "hidden": [
                ("bad", "assert(parseMavenCoord('only:two') === null);"),
                ("n", f"assert(parseMavenCoord('g:a:{n}.0').version === '{n}.0');"),
            ],
        },
        "gradle": {
            "fn": "gradleTaskName",
            "instructions": "Implement gradleTaskName(project, task) → ':project:task' (no double colons).",
            "stub": "function gradleTaskName(project, task) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(gradleTaskName('app', 'test') === ':app:test');"),
            ],
            "hidden": [
                ("colon", "assert(gradleTaskName(':app', 'build') === ':app:build');"),
                ("n", f"assert(gradleTaskName('lib', 't{n}') === ':lib:t{n}');"),
            ],
        },
        "spring-boot": {
            "fn": "healthStatus",
            "instructions": "Implement healthStatus(up) → 'UP' if truthy else 'DOWN'.",
            "stub": "function healthStatus(up) {\n  // TODO\n}\n",
            "visible": [
                ("up", "assert(healthStatus(true) === 'UP');"),
            ],
            "hidden": [
                ("down", "assert(healthStatus(false) === 'DOWN');"),
                ("n", f"assert(healthStatus({n} > 0) === 'UP');"),
            ],
        },
        "junit": {
            "fn": "assertSame",
            "instructions": "Implement assertSame(a, b) → true if Object.is(a,b), else throw Error.",
            "stub": "function assertSame(a, b) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(assertSame(1, 1) === true);"),
            ],
            "hidden": [
                ("fail", "let t=false; try{assertSame(1,2);}catch(e){t=true;} assert(t);"),
                ("str", f"assert(assertSame('v{n}', 'v{n}') === true);"),
            ],
        },
        "logging": {
            "fn": "formatLog",
            "instructions": "Implement formatLog(level, msg) → `[LEVEL] msg` with level uppercased.",
            "stub": "function formatLog(level, msg) {\n  // TODO\n}\n",
            "visible": [
                ("info", "assert(formatLog('info', 'hi') === '[INFO] hi');"),
            ],
            "hidden": [
                ("err", "assert(formatLog('error', 'x') === '[ERROR] x');"),
                ("n", f"assert(formatLog('debug', 'n{n}') === '[DEBUG] n{n}');"),
            ],
        },
        "jdbc": {
            "fn": "jdbcUrl",
            "instructions": "Implement jdbcUrl(host, db) → `jdbc:postgresql://host/db`.",
            "stub": "function jdbcUrl(host, db) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(jdbcUrl('db', 'app') === 'jdbc:postgresql://db/app');"),
            ],
            "hidden": [
                ("n", f"assert(jdbcUrl('h{n}', 'd') === 'jdbc:postgresql://h{n}/d');"),
            ],
        },
        "jvm-memory": {
            "fn": "heapMb",
            "instructions": "Implement heapMb(bytes) → floor(bytes / 1048576).",
            "stub": "function heapMb(bytes) {\n  // TODO\n}\n",
            "visible": [
                ("one", "assert(heapMb(1048576) === 1);"),
            ],
            "hidden": [
                ("zero", "assert(heapMb(0) === 0);"),
                ("n", f"assert(heapMb({n} * 1048576) === {n});"),
            ],
        },
        "security": {
            "fn": "maskSecret",
            "instructions": "Implement maskSecret(s) → first 2 chars + '***' + last char (or '***' if length < 4).",
            "stub": "function maskSecret(s) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(maskSecret('password') === 'pa***d');"),
            ],
            "hidden": [
                ("short", "assert(maskSecret('ab') === '***');"),
                ("n", f"assert(maskSecret('xx{n}y').endsWith('y'));"),
            ],
        },
        "rest-api": {
            "fn": "statusClass",
            "instructions": "Implement statusClass(code) → '2xx'|'3xx'|'4xx'|'5xx'|'other'.",
            "stub": "function statusClass(code) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(statusClass(200) === '2xx');"),
            ],
            "hidden": [
                ("nf", "assert(statusClass(404) === '4xx');"),
                ("n", f"assert(statusClass({200 + (n % 10)}) === '2xx');"),
            ],
        },
        "packaging": {
            "fn": "jarName",
            "instructions": "Implement jarName(artifact, version) → `artifact-version.jar`.",
            "stub": "function jarName(artifact, version) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(jarName('app', '1.0') === 'app-1.0.jar');"),
            ],
            "hidden": [
                ("n", f"assert(jarName('svc', '{n}.2') === 'svc-{n}.2.jar');"),
            ],
        },
    }


def shell_catalog(n: int) -> dict[str, dict]:
    pipe_demo = " | ".join(["x"] * (n + 1))
    return {
        "variables": {
            "fn": "expandVar",
            "instructions": f"Implement expandVar(template, value) replacing '$X' with value. Variant {n}.",
            "stub": "function expandVar(template, value) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(expandVar('hi $X', 'Ada') === 'hi Ada');"),
            ],
            "hidden": [
                ("multi", "assert(expandVar('$X-$X', 'a') === 'a-a');"),
                ("n", f"assert(expandVar('n$X', '{n}') === 'n{n}');"),
            ],
        },
        "conditionals": {
            "fn": "shellTruthy",
            "instructions": "Implement shellTruthy(s) → false for '', '0', 'false' (case-insensitive); else true.",
            "stub": "function shellTruthy(s) {\n  // TODO\n}\n",
            "visible": [
                ("yes", "assert(shellTruthy('yes') === true);"),
            ],
            "hidden": [
                ("zero", "assert(shellTruthy('0') === false);"),
                ("false", "assert(shellTruthy('FALSE') === false);"),
                ("n", f"assert(shellTruthy('{n}') === true);"),
            ],
        },
        "loops": {
            "fn": "seqSum",
            "instructions": "Implement seqSum(from, to) → sum of inclusive integers from..to.",
            "stub": "function seqSum(from, to) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(seqSum(1, 3) === 6);"),
            ],
            "hidden": [
                ("same", "assert(seqSum(5, 5) === 5);"),
                ("n", f"assert(seqSum(1, {n}) === {(n * (n + 1)) // 2});"),
            ],
        },
        "functions": {
            "fn": "repeat",
            "instructions": "Implement repeat(s, times) → s repeated times (times<=0 → '').",
            "stub": "function repeat(s, times) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(repeat('ab', 2) === 'abab');"),
            ],
            "hidden": [
                ("zero", "assert(repeat('x', 0) === '');"),
                ("n", f"assert(repeat('z', {n}).length === {n});"),
            ],
        },
        "pipes": {
            "fn": "pipeCount",
            "instructions": "Implement pipeCount(cmd) → number of '|' characters.",
            "stub": "function pipeCount(cmd) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(pipeCount('a | b | c') === 2);"),
            ],
            "hidden": [
                ("none", "assert(pipeCount('echo hi') === 0);"),
                ("n", f"assert(pipeCount('{pipe_demo}') === {n});"),
            ],
        },
        "traps": {
            "fn": "trapSignal",
            "instructions": "Implement trapSignal(sig) → uppercase signal name without 'SIG' prefix (e.g. SIGINT→INT).",
            "stub": "function trapSignal(sig) {\n  // TODO\n}\n",
            "visible": [
                ("int", "assert(trapSignal('SIGINT') === 'INT');"),
            ],
            "hidden": [
                ("term", "assert(trapSignal('SIGTERM') === 'TERM');"),
                ("raw", "assert(trapSignal('HUP') === 'HUP');"),
            ],
        },
        "cron": {
            "fn": "cronFields",
            "instructions": "Implement cronFields(expr) → array of 5 fields or null if not 5 tokens.",
            "stub": "function cronFields(expr) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(JSON.stringify(cronFields('0 2 * * *')) === JSON.stringify(['0','2','*','*','*']));"),
            ],
            "hidden": [
                ("bad", "assert(cronFields('* * *') === null);"),
                ("n", f"assert(cronFields('{n} * * * *')[0] === '{n}');"),
            ],
        },
        "logging": {
            "fn": "logLine",
            "instructions": "Implement logLine(ts, msg) → `ts msg`.",
            "stub": "function logLine(ts, msg) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(logLine('12:00', 'ok') === '12:00 ok');"),
            ],
            "hidden": [
                ("n", f"assert(logLine('t', 'v{n}') === 't v{n}');"),
            ],
        },
        "safe-delete": {
            "fn": "isSafePath",
            "instructions": "Implement isSafePath(p) → false for '/', '/etc', '/etc/', empty; else true.",
            "stub": "function isSafePath(p) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(isSafePath('/tmp/a') === true);"),
            ],
            "hidden": [
                ("root", "assert(isSafePath('/') === false);"),
                ("etc", "assert(isSafePath('/etc') === false);"),
                ("n", f"assert(isSafePath('/var/log/a{n}') === true);"),
            ],
        },
        "args": {
            "fn": "parseFlag",
            "instructions": "Implement parseFlag(argv, flag) → value after flag, or null.",
            "stub": "function parseFlag(argv, flag) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(parseFlag(['-f','a.txt'], '-f') === 'a.txt');"),
            ],
            "hidden": [
                ("miss", "assert(parseFlag(['-x'], '-f') === null);"),
                ("n", f"assert(parseFlag(['-n','{n}'], '-n') === '{n}');"),
            ],
        },
    }


def nodejs_catalog(n: int) -> dict[str, dict]:
    return {
        "express": {
            "fn": "routePath",
            "instructions": f"Implement routePath(base, resource) → join with single '/' (no doubles). Variant {n}.",
            "stub": "function routePath(base, resource) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(routePath('/api', 'users') === '/api/users');"),
            ],
            "hidden": [
                ("slash", "assert(routePath('/api/', '/users') === '/api/users');"),
                ("n", f"assert(routePath('/v{n}', 'x') === '/v{n}/x');"),
            ],
        },
        "middleware": {
            "fn": "composeMiddleware",
            "instructions": "Implement composeMiddleware(a, b) so composeMiddleware(a,b)(x) === b(a(x)).",
            "stub": "function composeMiddleware(a, b) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "const a=x=>x+1,b=x=>x*2; assert(composeMiddleware(a,b)(3)===8);"),
            ],
            "hidden": [
                ("n", f"assert(composeMiddleware(x=>x+{n}, x=>x)(1)==={1+n});"),
            ],
        },
        "env-config": {
            "fn": "envInt",
            "instructions": "Implement envInt(raw, fallback) → parseInt(raw,10) or fallback if NaN.",
            "stub": "function envInt(raw, fallback) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(envInt('42', 0) === 42);"),
            ],
            "hidden": [
                ("bad", "assert(envInt('x', 7) === 7);"),
                ("n", f"assert(envInt('{n}', 0) === {n});"),
            ],
        },
        "logging": {
            "fn": "jsonLog",
            "instructions": "Implement jsonLog(level, msg) → JSON.stringify({{level, msg}}).",
            "stub": "function jsonLog(level, msg) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(JSON.parse(jsonLog('info','hi')).msg === 'hi');"),
            ],
            "hidden": [
                ("n", f"assert(JSON.parse(jsonLog('warn','w{n}')).level === 'warn');"),
            ],
        },
        "streams": {
            "fn": "chunkJoin",
            "instructions": "Implement chunkJoin(chunks) → chunks joined with ''.",
            "stub": "function chunkJoin(chunks) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(chunkJoin(['a','b']) === 'ab');"),
            ],
            "hidden": [
                ("empty", "assert(chunkJoin([]) === '');"),
                ("n", f"assert(chunkJoin(['x','{n}']) === 'x{n}');"),
            ],
        },
        "workers": {
            "fn": "shardIndex",
            "instructions": "Implement shardIndex(id, shards) → id % shards (non-negative).",
            "stub": "function shardIndex(id, shards) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(shardIndex(5, 3) === 2);"),
            ],
            "hidden": [
                ("zero", "assert(shardIndex(0, 4) === 0);"),
                ("n", f"assert(shardIndex({n}, 10) === {n % 10});"),
            ],
        },
        "security": {
            "fn": "sanitizeHeader",
            "instructions": "Implement sanitizeHeader(v) → strip CR/LF characters.",
            "stub": "function sanitizeHeader(v) {\n  // TODO\n}\n",
            "visible": [
                ("crlf", "assert(sanitizeHeader('a\\r\\nb') === 'ab');"),
            ],
            "hidden": [
                ("ok", "assert(sanitizeHeader('ok') === 'ok');"),
                ("n", f"assert(sanitizeHeader('v{n}\\n') === 'v{n}');"),
            ],
        },
        "testing": {
            "fn": "expectEq",
            "instructions": "Implement expectEq(a, b) → true if equal else throw Error.",
            "stub": "function expectEq(a, b) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(expectEq(1, 1) === true);"),
            ],
            "hidden": [
                ("fail", "let t=false; try{expectEq(1,2);}catch(e){t=true;} assert(t);"),
                ("n", f"assert(expectEq('{n}', '{n}') === true);"),
            ],
        },
        "database": {
            "fn": "sqlIdent",
            "instructions": "Implement sqlIdent(name) → double-quote name and escape internal quotes by doubling.",
            "stub": "function sqlIdent(name) {\n  // TODO\n}\n",
            "visible": [
                ("basic", "assert(sqlIdent('users') === '\"users\"');"),
            ],
            "hidden": [
                ("q", "assert(sqlIdent('a\"b') === '\"a\"\"b\"');"),
                ("n", f"assert(sqlIdent('t{n}') === '\"t{n}\"');"),
            ],
        },
        "deployment": {
            "fn": "healthOk",
            "instructions": "Implement healthOk(statusCode) → true iff 200 <= code < 300.",
            "stub": "function healthOk(statusCode) {\n  // TODO\n}\n",
            "visible": [
                ("ok", "assert(healthOk(200) === true);"),
            ],
            "hidden": [
                ("nf", "assert(healthOk(503) === false);"),
                ("n", f"assert(healthOk({200 + (n % 50)}) === true);"),
            ],
        },
    }


def hero_topic_for(tech: str, slug: str) -> str:
    """Map non-academy hero slug → catalog topic key."""
    s = slug.lower()
    if tech == "java":
        keys = (
            "maven", "gradle", "spring-boot", "junit", "logging", "jdbc",
            "jvm-memory", "security", "rest-api", "packaging",
        )
        for k in keys:
            if k.replace("-", "") in s.replace("-", "") or k in s:
                return k
        if "spring" in s or "boot" in s or "actuator" in s:
            return "spring-boot"
        if "gradle" in s:
            return "gradle"
        if "maven" in s or "pom" in s:
            return "maven"
        if "junit" in s or "jacoco" in s or "test" in s:
            return "junit"
        if "jdbc" in s or "hibernate" in s or "jpa" in s:
            return "jdbc"
        if "heap" in s or "oom" in s or "gc" in s or "memory" in s:
            return "jvm-memory"
        if "jackson" in s or "rest" in s or "http" in s:
            return "rest-api"
        if "key" in s or "ssl" in s or "auth" in s:
            return "security"
        return "maven"
    if tech == "shell-script":
        if "arg" in s:
            return "args"
        if "cond" in s or "if" in s or "test" in s:
            return "conditionals"
        if "loop" in s or "for" in s or "while" in s or "arith" in s:
            return "loops"
        if "func" in s:
            return "functions"
        if "pipe" in s:
            return "pipes"
        if "trap" in s or "signal" in s:
            return "traps"
        if "cron" in s:
            return "cron"
        if "log" in s:
            return "logging"
        if "rm" in s or "delete" in s or "safe" in s:
            return "safe-delete"
        if "var" in s or "unbound" in s or "quote" in s:
            return "variables"
        return "variables"
    if tech == "nodejs":
        if "express" in s or "route" in s:
            return "express"
        if "middle" in s:
            return "middleware"
        if "env" in s or "config" in s:
            return "env-config"
        if "log" in s:
            return "logging"
        if "stream" in s:
            return "streams"
        if "worker" in s or "cluster" in s:
            return "workers"
        if "sec" in s or "auth" in s or "helmet" in s:
            return "security"
        if "test" in s or "jest" in s:
            return "testing"
        if "db" in s or "mongo" in s or "sql" in s or "database" in s:
            return "database"
        if "deploy" in s or "health" in s or "docker" in s:
            return "deployment"
        return "express"
    return "variables"


def html_hero_spec(slug: str, n: int = 1) -> dict:
    """Build a PAGE_HTML coding_spec for a non-academy HTML hero."""
    s = slug.lower()
    if "doctype" in s:
        instructions = "Add a valid HTML5 doctype (`<!DOCTYPE html>`) as the first line."
        html = "<html lang=\"en\"><head><title>Lab</title></head><body><h1>Hi</h1></body></html>\n"
        visible = [("doctype", "assert(/^\\s*<!DOCTYPE\\s+html>/i.test(PAGE_HTML), 'missing HTML5 doctype');")]
        hidden = [("html", "assert(/<html/i.test(PAGE_HTML));")]
    elif "aria" in s:
        instructions = "Add role=\"main\" on the primary content container."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>A</title></head><body><div id=\"content\"><h1>Hi</h1></div></body></html>\n"
        visible = [("role", "assert(/role\\s*=\\s*[\"']main[\"']/i.test(PAGE_HTML), 'missing role=main');")]
        hidden = [("main", "assert(/<main|role\\s*=\\s*[\"']main[\"']/i.test(PAGE_HTML));")]
    elif "form" in s:
        instructions = "Give the form an action attribute (non-empty) and a submit button."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>F</title></head><body><form><input name=\"q\" /><button type=\"button\">Go</button></form></body></html>\n"
        visible = [("action", "assert(/<form[^>]*action\\s*=/i.test(PAGE_HTML), 'form needs action');")]
        hidden = [("submit", "assert(/type\\s*=\\s*[\"']submit[\"']/i.test(PAGE_HTML) || /<button[^>]*>\\s*submit/i.test(PAGE_HTML) || /type\\s*=\\s*[\"']submit[\"']/i.test(PAGE_HTML) || /<button/i.test(PAGE_HTML));")]
    elif "charset" in s:
        instructions = "Put `<meta charset=\"utf-8\">` in <head> before <title>."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>C</title></head><body></body></html>\n"
        visible = [("charset", "assert(/<meta[^>]*charset\\s*=\\s*[\"']?utf-8/i.test(PAGE_HTML), 'missing charset');")]
        hidden = [("head", "assert(/<head[\\s\\S]*charset[\\s\\S]*<\\/head>/i.test(PAGE_HTML));")]
    elif "canonical" in s:
        instructions = "Add `<link rel=\"canonical\" href=\"https://example.com/\">` in head."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>C</title></head><body></body></html>\n"
        visible = [("canon", "assert(/rel\\s*=\\s*[\"']canonical[\"']/i.test(PAGE_HTML));")]
        hidden = [("href", "assert(/canonical[^>]*href\\s*=/i.test(PAGE_HTML));")]
    elif "title" in s:
        instructions = "Ensure exactly one non-empty <title> in <head>."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title></title><title>Dup</title></head><body></body></html>\n"
        visible = [("one", "const m=PAGE_HTML.match(/<title[^>]*>/gi)||[]; assert(m.length===1, 'need exactly one title');")]
        hidden = [("text", "assert(/<title[^>]*>\\s*\\S+/i.test(PAGE_HTML));")]
    elif "link" in s or "relative" in s:
        instructions = "Fix the broken link: use an absolute path starting with / for the nav href."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>L</title></head><body><a href=\"../oops\">Home</a></body></html>\n"
        visible = [("abs", "assert(/href\\s*=\\s*[\"']\\//i.test(PAGE_HTML), 'use root-relative href');")]
        hidden = [("a", "assert(/<a\\s/i.test(PAGE_HTML));")]
    else:
        instructions = f"Add a landmark <main> wrapping the page content. Variant {n}."
        html = "<!DOCTYPE html><html lang=\"en\"><head><title>Lab</title></head><body><h1>Welcome</h1></body></html>\n"
        visible = [("main", "assert(/<main[\\s>]/i.test(PAGE_HTML), 'wrap content in <main>');")]
        hidden = [("doctype", "assert(/<!DOCTYPE\\s+html>/i.test(PAGE_HTML));")]
    return {
        "language": "javascript",
        "entrypoint": "solution.js",
        "kind": "impl",
        "instructions": instructions + "\nEdit index.html / styles.css, use Preview, then Check Solution.\n",
        "files": [
            {"path": "index.html", "content": html, "readonly": False},
            {"path": "styles.css", "content": "body { font-family: system-ui, sans-serif; }\n", "readonly": False},
            {
                "path": "solution.js",
                "content": (
                    "// Grader harness — PAGE_HTML / PAGE_CSS are injected server-side.\n"
                    "// Keep this file; edit index.html and styles.css instead.\n"
                ),
                "readonly": True,
            },
        ],
        "visible_tests": [{"name": name, "code": code} for name, code in visible],
        "hidden_tests": [{"name": name, "code": code} for name, code in hidden],
        "timeout": 8,
    }
