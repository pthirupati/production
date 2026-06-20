"""JavaScript coding scenarios for the FixitLab browser IDE.

The JS grader injects only ``assert(cond, msg)`` and runs each test as
``USER_SRC + test.code`` inside a fresh Function. Native globals (JSON, Math,
Set, Map, Object, Array) are available; use assert(...) (NOT console.assert).
Each Scenario ships a BROKEN starter (fails) and a REFERENCE solution (passes);
the generator proves both before writing YAML.
"""

from framework import Scenario, Test

S = []


def add(scn):
    S.append(scn)


# Helper: deep-equality assertion snippet reused by many tests.
def eq(expr, expected):
    return f"assert(JSON.stringify({expr}) === JSON.stringify({expected}), JSON.stringify({expr}));"


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: broken-code-fix
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-fix-sum-array-init",
    title="Fix sumArray Accumulator Start",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "sumArray(nums) should add up all the numbers, but reduce is called "
        "without an initial value, so on an EMPTY array it throws 'Reduce of "
        "empty array with no initial value'. Provide the initial accumulator so "
        "empty returns 0 and totals stay correct."),
    objectives=[
        "Reproduce the empty-array reduce error",
        "Pass 0 as the reduce initial value",
        "Return correct sums including the empty case",
    ],
    instructions=(
        "Fix sumArray(nums) to return the sum of the array, and 0 for an empty "
        "array.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function sumArray(nums) {\n"
        "  return nums.reduce((acc, n) => acc + n); // no initial value\n"
        "}\n"),
    reference=(
        "function sumArray(nums) {\n"
        "  return nums.reduce((acc, n) => acc + n, 0);\n"
        "}\n"),
    visible_tests=[
        Test("basic sum", "assert(sumArray([1, 2, 3]) === 6);"),
        Test("empty is zero", "assert(sumArray([]) === 0, 'empty should be 0');"),
    ],
    hidden_tests=[
        Test("single element", "assert(sumArray([7]) === 7);"),
        Test("negatives", "assert(sumArray([-1, -2, 3]) === 0);"),
        Test("empty does not throw", "assert(sumArray([]) === 0);"),
        Test("floats", "assert(Math.abs(sumArray([0.1, 0.2]) - 0.3) < 1e-9);"),
    ],
    hints=[
        "sumArray([]) throws because reduce has no seed value to return.",
        "reduce(fn, initialValue) — supply the initial accumulator.",
        "Pass 0 as the second argument to reduce.",
    ],
    solution_explanation=(
        "Without an initial value, reduce on an empty array throws. Seeding the "
        "accumulator with 0 makes empty return 0 and keeps sums correct."),
))

add(Scenario(
    slug="js-fix-equality-loose-vs-strict",
    title="Fix the Loose-Equality Bug in isZero",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "isZero(x) should return true ONLY for the number 0, but it uses loose "
        "equality (==), so '', false, '0', and [] all coerce to 0 and wrongly "
        "return true. Switch to strict equality and a type check."),
    objectives=[
        "See coercion make non-numbers look like zero",
        "Use strict equality (===)",
        "Return true only for the actual number 0",
    ],
    instructions=(
        "Fix isZero(x) to return true only when x is the number 0 (not '', not "
        "false, not '0').\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function isZero(x) {\n"
        "  return x == 0; // loose equality coerces '', false, [], '0'\n"
        "}\n"),
    reference=(
        "function isZero(x) {\n"
        "  return x === 0;\n"
        "}\n"),
    visible_tests=[
        Test("number zero", "assert(isZero(0) === true);"),
        Test("empty string is not zero", "assert(isZero('') === false, \"'' should not be zero\");"),
    ],
    hidden_tests=[
        Test("false is not zero", "assert(isZero(false) === false);"),
        Test("string zero is not number zero", "assert(isZero('0') === false);"),
        Test("empty array is not zero", "assert(isZero([]) === false);"),
        Test("nonzero number", "assert(isZero(5) === false);"),
        Test("still true for 0", "assert(isZero(0) === true);"),
    ],
    hints=[
        "isZero('') returns true because '' == 0 is true in JS.",
        "== performs type coercion; === does not.",
        "Use x === 0.",
    ],
    solution_explanation=(
        "Loose == coerces operands, so many falsy values equal 0. Strict === "
        "compares type and value, matching only the number 0."),
))

add(Scenario(
    slug="js-fix-ternary-precedence",
    title="Fix the Operator Precedence in describe",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "describe(n) should return a string like 'positive: 5' / 'non-positive: "
        "-2', but the string concatenation and ternary are mixed without "
        "parentheses, so '+' binds before '?:' and the label is wrong. Fix the "
        "precedence with parentheses so the ternary chooses the label."),
    objectives=[
        "See the wrong label produced by precedence",
        "Parenthesize the ternary so it evaluates first",
        "Return the correctly labelled string",
    ],
    instructions=(
        "Fix describe(n): return 'positive: <n>' when n > 0, otherwise "
        "'non-positive: <n>'.\n"
        "  describe(5) -> 'positive: 5'; describe(-2) -> 'non-positive: -2'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function describe(n) {\n"
        "  // '+' binds tighter than '?:', so the ternary never picks the label\n"
        "  return 'label: ' + n > 0 ? 'positive: ' + n : 'non-positive: ' + n;\n"
        "}\n"),
    reference=(
        "function describe(n) {\n"
        "  return (n > 0 ? 'positive: ' : 'non-positive: ') + n;\n"
        "}\n"),
    visible_tests=[
        Test("positive", "assert(describe(5) === 'positive: 5', describe(5));"),
        Test("negative", "assert(describe(-2) === 'non-positive: -2', describe(-2));"),
    ],
    hidden_tests=[
        Test("zero is non-positive", "assert(describe(0) === 'non-positive: 0', describe(0));"),
        Test("large positive", "assert(describe(100) === 'positive: 100');"),
        Test("no stray label text",
             "assert(describe(3).indexOf('label') === -1, describe(3));"),
        Test("one", "assert(describe(1) === 'positive: 1');"),
    ],
    hints=[
        "describe(5) returns the wrong string because 'label: ' + n is evaluated before the ?: .",
        "In JS, + has higher precedence than the conditional operator ?:.",
        "Wrap the ternary in parentheses: (n > 0 ? 'positive: ' : 'non-positive: ') + n.",
    ],
    solution_explanation=(
        "Because + binds tighter than ?:, the original concatenated first and fed "
        "a truthy string into the condition. Parenthesizing the ternary makes it "
        "select the label, which is then concatenated with n."),
))

add(Scenario(
    slug="js-fix-closure-loop-var",
    title="Fix the Closure-in-Loop Capture Bug",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "makeCounters(n) should return an array of n functions where the i-th "
        "function returns i, but it declares the loop variable with `var`, so "
        "every closure captures the SAME final value of i. Fix the capture so "
        "each function returns its own index."),
    objectives=[
        "See every counter return the same number",
        "Give each iteration its own binding",
        "Make the i-th function return i",
    ],
    instructions=(
        "Fix makeCounters(n): return an array of n functions; calling the i-th "
        "returns i (0-indexed).\n"
        "  const fns = makeCounters(3); fns[0]() -> 0, fns[2]() -> 2\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function makeCounters(n) {\n"
        "  const fns = [];\n"
        "  for (var i = 0; i < n; i++) {  // var: shared binding\n"
        "    fns.push(function () { return i; });\n"
        "  }\n"
        "  return fns;\n"
        "}\n"),
    reference=(
        "function makeCounters(n) {\n"
        "  const fns = [];\n"
        "  for (let i = 0; i < n; i++) {\n"
        "    fns.push(function () { return i; });\n"
        "  }\n"
        "  return fns;\n"
        "}\n"),
    visible_tests=[
        Test("each returns its index",
             "const fns = makeCounters(3);\n"
             "assert(fns[0]() === 0 && fns[1]() === 1 && fns[2]() === 2);"),
        Test("count matches n",
             "assert(makeCounters(5).length === 5);"),
    ],
    hidden_tests=[
        Test("last function",
             "const fns = makeCounters(4);\nassert(fns[3]() === 3, 'got ' + fns[3]());"),
        Test("all distinct",
             "const fns = makeCounters(3);\n"
             "const vals = fns.map(f => f());\nassert(JSON.stringify(vals) === JSON.stringify([0,1,2]));"),
        Test("zero counters",
             "assert(makeCounters(0).length === 0);"),
    ],
    hints=[
        "All counters return n (e.g. 3 for makeCounters(3)) — they share one i.",
        "var is function-scoped, so every closure sees the same final i.",
        "Declare the loop variable with let to get a fresh binding per iteration.",
    ],
    solution_explanation=(
        "var creates a single shared binding, so all closures read the final i. "
        "let gives each loop iteration its own binding, capturing the right value."),
))

add(Scenario(
    slug="js-fix-floating-point-rounding",
    title="Fix the Money Rounding Bug",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "roundMoney(x) should round a number to 2 decimal places, but it uses "
        "Math.round(x) which rounds to the nearest integer, dropping the cents. "
        "Fix it to round to 2 decimals and return a number."),
    objectives=[
        "See cents disappear (1.005 -> 1)",
        "Scale by 100 before rounding, then divide back",
        "Return a number rounded to 2 decimals",
    ],
    instructions=(
        "Fix roundMoney(x) to round to 2 decimal places.\n"
        "  roundMoney(1.005) -> 1.01 (approx), roundMoney(2.345) -> 2.35\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function roundMoney(x) {\n"
        "  return Math.round(x); // rounds to whole number, loses cents\n"
        "}\n"),
    reference=(
        "function roundMoney(x) {\n"
        "  return Math.round(x * 100) / 100;\n"
        "}\n"),
    visible_tests=[
        Test("two decimals", "assert(roundMoney(2.345) === 2.35, roundMoney(2.345));"),
        Test("already rounded", "assert(roundMoney(3.10) === 3.1);"),
    ],
    hidden_tests=[
        Test("rounds down", "assert(roundMoney(1.234) === 1.23);"),
        Test("rounds up", "assert(roundMoney(1.236) === 1.24);"),
        Test("whole number", "assert(roundMoney(5) === 5);"),
        Test("keeps cents", "assert(roundMoney(9.99) === 9.99);"),
    ],
    hints=[
        "roundMoney(2.345) returns 2 — Math.round goes to the nearest integer.",
        "Multiply by 100 first so the cents become whole numbers.",
        "Return Math.round(x * 100) / 100.",
    ],
    solution_explanation=(
        "Math.round alone rounds to an integer. Scaling by 100, rounding, then "
        "dividing rounds to two decimals."),
))

add(Scenario(
    slug="js-fix-array-sort-numeric",
    title="Fix the Numeric Sort (Lexicographic Bug)",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "sortNumbers(nums) should return the array sorted in ascending NUMERIC "
        "order, but it calls .sort() with no comparator, so JS sorts by string, "
        "putting 10 before 2. Provide a numeric comparator. Also, return a new "
        "array (don't mutate the input)."),
    objectives=[
        "See the lexicographic ordering bug (10 before 2)",
        "Provide an (a, b) => a - b comparator",
        "Return a sorted copy without mutating input",
    ],
    instructions=(
        "Fix sortNumbers(nums) to sort ascending numerically and return a NEW "
        "array (do not mutate the input).\n"
        "  sortNumbers([10, 2, 1]) -> [1, 2, 10]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function sortNumbers(nums) {\n"
        "  return nums.sort(); // lexicographic AND mutates input\n"
        "}\n"),
    reference=(
        "function sortNumbers(nums) {\n"
        "  return [...nums].sort((a, b) => a - b);\n"
        "}\n"),
    visible_tests=[
        Test("numeric order", eq("sortNumbers([10, 2, 1])", "[1, 2, 10]")),
        Test("already sorted", eq("sortNumbers([1, 2, 3])", "[1, 2, 3]")),
    ],
    hidden_tests=[
        Test("multi-digit", eq("sortNumbers([100, 25, 9, 1000])", "[9, 25, 100, 1000]")),
        Test("negatives", eq("sortNumbers([3, -1, -10, 2])", "[-10, -1, 2, 3]")),
        Test("does not mutate input",
             "const src = [3, 1, 2];\nsortNumbers(src);\n"
             "assert(JSON.stringify(src) === JSON.stringify([3, 1, 2]), 'input mutated');"),
        Test("empty", eq("sortNumbers([])", "[]")),
    ],
    hints=[
        "sortNumbers([10, 2, 1]) gives [1, 10, 2] — string comparison, not numeric.",
        "Pass a comparator (a, b) => a - b to sort.",
        "Also copy first with [...nums] so the caller's array isn't sorted in place.",
    ],
    solution_explanation=(
        "Default sort compares string representations. A numeric comparator orders "
        "by value, and spreading into a new array avoids mutating the input."),
))

add(Scenario(
    slug="js-fix-this-binding-method",
    title="Fix the Lost `this` in a Callback",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "makeAdder(base) returns an object whose addAll(nums) should add `base` to "
        "each number, but it uses a normal function callback in map, so `this` is "
        "undefined inside it and base can't be read. Fix the binding (arrow "
        "function) so addAll works."),
    objectives=[
        "See `this` lost inside the map callback",
        "Use an arrow function to preserve `this`",
        "Add base to each element correctly",
    ],
    instructions=(
        "Fix makeAdder(base): the returned object's addAll(nums) must return a new "
        "array with base added to each number.\n"
        "  makeAdder(10).addAll([1, 2]) -> [11, 12]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function makeAdder(base) {\n"
        "  return {\n"
        "    base: base,\n"
        "    addAll(nums) {\n"
        "      return nums.map(function (n) { return n + this.base; }); // this is undefined\n"
        "    }\n"
        "  };\n"
        "}\n"),
    reference=(
        "function makeAdder(base) {\n"
        "  return {\n"
        "    base: base,\n"
        "    addAll(nums) {\n"
        "      return nums.map((n) => n + this.base);\n"
        "    }\n"
        "  };\n"
        "}\n"),
    visible_tests=[
        Test("adds base", eq("makeAdder(10).addAll([1, 2])", "[11, 12]")),
        Test("base zero", eq("makeAdder(0).addAll([5, 6])", "[5, 6]")),
    ],
    hidden_tests=[
        Test("negative base", eq("makeAdder(-1).addAll([3, 4])", "[2, 3]")),
        Test("empty input", eq("makeAdder(5).addAll([])", "[]")),
        Test("does not produce NaN",
             "const r = makeAdder(7).addAll([1]);\nassert(r[0] === 8, 'got ' + r[0]);"),
    ],
    hints=[
        "Inside the plain function callback, this.base is undefined, yielding NaN.",
        "A normal function gets its own `this`; an arrow function inherits the method's `this`.",
        "Change the map callback to an arrow function: (n) => n + this.base.",
    ],
    solution_explanation=(
        "A standalone function callback rebinds `this`, so this.base is undefined. "
        "An arrow function lexically captures the method's `this`, keeping base."),
))

add(Scenario(
    slug="js-fix-spread-shallow-copy",
    title="Fix the Object Mutation in updateUser",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "updateUser(user, patch) should return a NEW object with patch applied, "
        "leaving the original user unchanged, but it mutates user with "
        "Object.assign(user, patch). Fix it to copy first so the input is not "
        "mutated and patch overrides."),
    objectives=[
        "See the original user object get mutated",
        "Build a new object via spread/assign-into-empty",
        "Apply patch on top so it overrides",
    ],
    instructions=(
        "Fix updateUser(user, patch): return a NEW object combining user and "
        "patch (patch wins), WITHOUT mutating user.\n"
        "  updateUser({a:1,b:2}, {b:9}) -> {a:1, b:9}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function updateUser(user, patch) {\n"
        "  return Object.assign(user, patch); // mutates user\n"
        "}\n"),
    reference=(
        "function updateUser(user, patch) {\n"
        "  return { ...user, ...patch };\n"
        "}\n"),
    visible_tests=[
        Test("patch overrides", eq("updateUser({a:1,b:2}, {b:9})", "{a:1,b:9}")),
        Test("adds new key", eq("updateUser({a:1}, {c:3})", "{a:1,c:3}")),
    ],
    hidden_tests=[
        Test("does not mutate user",
             "const u = {a:1,b:2};\nupdateUser(u, {b:9});\n"
             "assert(JSON.stringify(u) === JSON.stringify({a:1,b:2}), 'user mutated');"),
        Test("returns a new object",
             "const u = {a:1};\nconst r = updateUser(u, {});\nassert(r !== u);"),
        Test("empty patch copies", eq("updateUser({x:5}, {})", "{x:5}")),
    ],
    hints=[
        "After updateUser(u, {b:9}), u itself changed — that's the mutation bug.",
        "Object.assign(target, src) writes into target; use a fresh target.",
        "Return { ...user, ...patch } to copy then override.",
    ],
    solution_explanation=(
        "Object.assign(user, patch) mutates user. Spreading into a new object "
        "literal copies user, then patch overrides, leaving the input intact."),
))

add(Scenario(
    slug="js-fix-parseint-radix",
    title="Fix parseInt Radix in toBase10",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "toBase10(str) parses a decimal numeric string, but it calls "
        "parseInt(str) without a radix. For inputs with leading zeros this is "
        "fragile, and the intent is explicit base-10 parsing. Also it returns NaN "
        "silently for bad input where it should throw. Fix: always pass radix 10 "
        "and throw a RangeError on non-numeric input."),
    objectives=[
        "Always specify radix 10 to parseInt",
        "Parse leading-zero strings as decimal (not octal-ish)",
        "Throw on input that does not parse",
    ],
    instructions=(
        "Fix toBase10(str): return the base-10 integer value. Use radix 10 "
        "explicitly. If the result is NaN, throw a RangeError('not a number').\n"
        "  toBase10('010') -> 10, toBase10('42') -> 42\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function toBase10(str) {\n"
        "  return parseInt(str); // no radix; returns NaN silently on bad input\n"
        "}\n"),
    reference=(
        "function toBase10(str) {\n"
        "  const n = parseInt(str, 10);\n"
        "  if (Number.isNaN(n)) {\n"
        "    throw new RangeError('not a number');\n"
        "  }\n"
        "  return n;\n"
        "}\n"),
    visible_tests=[
        Test("plain number", "assert(toBase10('42') === 42);"),
        Test("leading zeros decimal", "assert(toBase10('010') === 10, toBase10('010'));"),
    ],
    hidden_tests=[
        Test("negative", "assert(toBase10('-7') === -7);"),
        Test("trailing text parses prefix", "assert(toBase10('15px') === 15);"),
        Test("throws on non-numeric",
             "let threw = false;\ntry { toBase10('abc'); } catch (e) { threw = e instanceof RangeError; }\n"
             "assert(threw, 'should throw RangeError');"),
        Test("zero", "assert(toBase10('0') === 0);"),
    ],
    hints=[
        "parseInt without a radix is ambiguous and returns NaN quietly for 'abc'.",
        "Always pass 10 as the second argument: parseInt(str, 10).",
        "After parsing, if Number.isNaN(n) throw new RangeError('not a number').",
    ],
    solution_explanation=(
        "Specifying radix 10 makes parsing unambiguous, and checking for NaN turns "
        "silent bad input into an explicit RangeError."),
))

add(Scenario(
    slug="js-fix-includes-vs-indexof",
    title="Fix the Truthiness Bug with indexOf",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "hasValue(arr, x) should return whether x is in the array, but it returns "
        "`arr.indexOf(x)` (a number) and treats it as a boolean — and index 0 is "
        "falsy, so a match at position 0 wrongly reports false. Fix it to return a "
        "real boolean."),
    objectives=[
        "See a match at index 0 report false",
        "Compare indexOf against -1, or use includes",
        "Return a strict boolean",
    ],
    instructions=(
        "Fix hasValue(arr, x) to return true/false for membership.\n"
        "  hasValue([5, 6], 5) -> true (even though it's at index 0)\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function hasValue(arr, x) {\n"
        "  return Boolean(arr.indexOf(x)); // index 0 is falsy -> wrong\n"
        "}\n"),
    reference=(
        "function hasValue(arr, x) {\n"
        "  return arr.indexOf(x) !== -1;\n"
        "}\n"),
    visible_tests=[
        Test("present at index 0", "assert(hasValue([5, 6], 5) === true, 'index 0 match');"),
        Test("absent", "assert(hasValue([1, 2], 9) === false);"),
    ],
    hidden_tests=[
        Test("present later", "assert(hasValue([1, 2, 3], 3) === true);"),
        Test("empty array", "assert(hasValue([], 1) === false);"),
        Test("returns boolean", "assert(hasValue([1], 1) === true && hasValue([1], 2) === false);"),
        Test("strings", "assert(hasValue(['a', 'b'], 'a') === true);"),
    ],
    hints=[
        "hasValue([5,6], 5) returns false because indexOf is 0, which is falsy.",
        "indexOf returns -1 when absent, and a real index (possibly 0) when present.",
        "Return arr.indexOf(x) !== -1 (or arr.includes(x)).",
    ],
    solution_explanation=(
        "Coercing the index to boolean misreads a valid index of 0 as false. "
        "Comparing against -1 (or using includes) returns correct membership."),
))

add(Scenario(
    slug="js-fix-splice-vs-slice",
    title="Fix takeFirst Mutating the Input",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "takeFirst(arr, k) should return the first k elements WITHOUT modifying "
        "the input, but it uses splice, which removes elements from the original "
        "array. Use slice instead so the input is untouched."),
    objectives=[
        "See the input array get shortened",
        "Use slice (non-mutating) instead of splice",
        "Return the first k elements as a copy",
    ],
    instructions=(
        "Fix takeFirst(arr, k): return the first k elements as a NEW array, "
        "leaving arr unchanged.\n"
        "  takeFirst([1,2,3,4], 2) -> [1,2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function takeFirst(arr, k) {\n"
        "  return arr.splice(0, k); // splice mutates arr\n"
        "}\n"),
    reference=(
        "function takeFirst(arr, k) {\n"
        "  return arr.slice(0, k);\n"
        "}\n"),
    visible_tests=[
        Test("first two", eq("takeFirst([1,2,3,4], 2)", "[1,2]")),
        Test("k zero", eq("takeFirst([1,2], 0)", "[]")),
    ],
    hidden_tests=[
        Test("does not mutate input",
             "const src = [1,2,3,4];\ntakeFirst(src, 2);\n"
             "assert(JSON.stringify(src) === JSON.stringify([1,2,3,4]), 'input mutated');"),
        Test("k larger than length", eq("takeFirst([1,2], 5)", "[1,2]")),
        Test("empty array", eq("takeFirst([], 3)", "[]")),
    ],
    hints=[
        "After takeFirst(src, 2), src lost its first two elements.",
        "splice removes from the array; slice returns a copy.",
        "Return arr.slice(0, k).",
    ],
    solution_explanation=(
        "splice mutates by removing elements. slice returns a shallow copy of the "
        "requested range and leaves the source array intact."),
))

add(Scenario(
    slug="js-fix-nan-check",
    title="Fix the NaN Check in isInvalid",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "isInvalid(x) should return true when x is NaN, but it compares `x === "
        "NaN`, which is ALWAYS false because NaN is not equal to itself. Use the "
        "correct NaN test."),
    objectives=[
        "Understand NaN !== NaN",
        "Use Number.isNaN to detect NaN",
        "Return false for all valid numbers",
    ],
    instructions=(
        "Fix isInvalid(x): return true only when x is the NaN value.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function isInvalid(x) {\n"
        "  return x === NaN; // always false: NaN !== NaN\n"
        "}\n"),
    reference=(
        "function isInvalid(x) {\n"
        "  return Number.isNaN(x);\n"
        "}\n"),
    visible_tests=[
        Test("detects NaN", "assert(isInvalid(NaN) === true, 'should detect NaN');"),
        Test("number is valid", "assert(isInvalid(5) === false);"),
    ],
    hidden_tests=[
        Test("zero is valid", "assert(isInvalid(0) === false);"),
        Test("computed NaN", "assert(isInvalid(0 / 0) === true);"),
        Test("string is not NaN value", "assert(isInvalid('abc') === false);"),
        Test("Infinity is not NaN", "assert(isInvalid(Infinity) === false);"),
    ],
    hints=[
        "x === NaN is always false because NaN is the only value not equal to itself.",
        "Use the built-in Number.isNaN to test for NaN specifically.",
        "Return Number.isNaN(x).",
    ],
    solution_explanation=(
        "NaN compares unequal to everything, including itself, so === NaN never "
        "works. Number.isNaN(x) reliably detects the NaN value without coercion."),
))

add(Scenario(
    slug="js-fix-default-param-falsy",
    title="Fix the Falsy Default in greet",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "greet(name, greeting) defaults greeting to 'Hello' using `greeting || "
        "'Hello'`, but that also overrides a deliberately empty string ''. The "
        "intent is to default only when greeting is undefined. Fix it using the "
        "nullish-coalescing operator (??) or a default parameter."),
    objectives=[
        "See an empty-string greeting get replaced",
        "Default only for undefined, not all falsy values",
        "Preserve an explicit empty greeting",
    ],
    instructions=(
        "Fix greet(name, greeting): return `${greeting} ${name}`. greeting "
        "defaults to 'Hello' only when it is undefined; an explicit '' must be "
        "kept.\n"
        "  greet('Sam') -> 'Hello Sam'; greet('Sam', '') -> ' Sam'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function greet(name, greeting) {\n"
        "  greeting = greeting || 'Hello'; // overrides '' too\n"
        "  return greeting + ' ' + name;\n"
        "}\n"),
    reference=(
        "function greet(name, greeting) {\n"
        "  greeting = greeting ?? 'Hello';\n"
        "  return greeting + ' ' + name;\n"
        "}\n"),
    visible_tests=[
        Test("default greeting", "assert(greet('Sam') === 'Hello Sam');"),
        Test("explicit empty kept", "assert(greet('Sam', '') === ' Sam', JSON.stringify(greet('Sam', '')));"),
    ],
    hidden_tests=[
        Test("custom greeting", "assert(greet('Sam', 'Hi') === 'Hi Sam');"),
        Test("undefined defaults", "assert(greet('Lee', undefined) === 'Hello Lee');"),
        Test("null defaults", "assert(greet('Lee', null) === 'Hello Lee');"),
    ],
    hints=[
        "greet('Sam', '') returns 'Hello Sam', but the empty greeting should be kept.",
        "|| treats '' as falsy and replaces it; ?? only replaces null/undefined.",
        "Use greeting ?? 'Hello'.",
    ],
    solution_explanation=(
        "The || operator replaces every falsy value, including ''. Nullish "
        "coalescing (??) defaults only for null/undefined, preserving an empty "
        "string."),
))

add(Scenario(
    slug="js-fix-map-vs-foreach-return",
    title="Fix doubleAll Returning undefined",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "doubleAll(nums) should return a new array with each value doubled, but it "
        "uses forEach (which returns undefined) instead of map, so the function "
        "returns undefined. Switch to map."),
    objectives=[
        "See the function return undefined",
        "Use map to build and return the array",
        "Double each element",
    ],
    instructions=(
        "Fix doubleAll(nums): return a new array of doubled values.\n"
        "  doubleAll([1,2,3]) -> [2,4,6]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function doubleAll(nums) {\n"
        "  nums.forEach((n) => n * 2); // forEach returns undefined\n"
        "}\n"),
    reference=(
        "function doubleAll(nums) {\n"
        "  return nums.map((n) => n * 2);\n"
        "}\n"),
    visible_tests=[
        Test("doubles", eq("doubleAll([1,2,3])", "[2,4,6]")),
        Test("empty", eq("doubleAll([])", "[]")),
    ],
    hidden_tests=[
        Test("returns an array",
             "assert(Array.isArray(doubleAll([1])), 'should return an array');"),
        Test("negatives", eq("doubleAll([-1, 0, 2])", "[-2, 0, 4]")),
        Test("does not mutate input",
             "const src = [1,2];\ndoubleAll(src);\nassert(JSON.stringify(src) === JSON.stringify([1,2]));"),
    ],
    hints=[
        "doubleAll([1,2,3]) returns undefined — forEach doesn't build a result.",
        "map transforms each element into a new array; forEach just iterates.",
        "Return nums.map((n) => n * 2).",
    ],
    solution_explanation=(
        "forEach returns undefined and discards the callback results. map collects "
        "the transformed values into a new array, which we return."),
))

add(Scenario(
    slug="js-fix-string-replace-all",
    title="Fix replace Only Hitting the First Match",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "censor(text, word) should replace EVERY occurrence of word with '***', "
        "but it uses String.replace with a plain string, which replaces only the "
        "first match. Replace all occurrences."),
    objectives=[
        "See only the first occurrence replaced",
        "Replace all matches (replaceAll or a global regex split/join)",
        "Leave text without the word unchanged",
    ],
    instructions=(
        "Fix censor(text, word): replace every occurrence of word with '***'.\n"
        "  censor('bad bad wolf', 'bad') -> '*** *** wolf'\n"
        "Assume word contains no regex special characters.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function censor(text, word) {\n"
        "  return text.replace(word, '***'); // replaces only the first match\n"
        "}\n"),
    reference=(
        "function censor(text, word) {\n"
        "  return text.split(word).join('***');\n"
        "}\n"),
    visible_tests=[
        Test("replaces all",
             "assert(censor('bad bad wolf', 'bad') === '*** *** wolf', censor('bad bad wolf', 'bad'));"),
        Test("single occurrence", "assert(censor('a bad day', 'bad') === 'a *** day');"),
    ],
    hidden_tests=[
        Test("three occurrences",
             "assert(censor('no no no', 'no') === '*** *** ***');"),
        Test("word absent unchanged", "assert(censor('clean text', 'bad') === 'clean text');"),
        Test("adjacent occurrences",
             "assert(censor('xx', 'x') === '******');"),
    ],
    hints=[
        "censor('bad bad wolf', 'bad') leaves the second 'bad' — replace only hits the first.",
        "split(word).join('***') replaces every occurrence; so does replaceAll.",
        "Return text.split(word).join('***').",
    ],
    solution_explanation=(
        "String.replace with a string target replaces only the first match. "
        "Splitting on the word and joining with '***' replaces every occurrence."),
))

add(Scenario(
    slug="js-fix-object-key-iteration",
    title="Fix sumValues Iterating Keys Not Values",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "sumValues(obj) should sum the numeric VALUES of an object, but it sums "
        "Object.keys (the keys), producing NaN/string concatenation. Iterate the "
        "values instead."),
    objectives=[
        "See it operate on keys, not values",
        "Iterate Object.values",
        "Return the numeric sum",
    ],
    instructions=(
        "Fix sumValues(obj): return the sum of the object's numeric values.\n"
        "  sumValues({a:1, b:2, c:3}) -> 6\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function sumValues(obj) {\n"
        "  return Object.keys(obj).reduce((acc, k) => acc + k, 0); // adds keys\n"
        "}\n"),
    reference=(
        "function sumValues(obj) {\n"
        "  return Object.values(obj).reduce((acc, v) => acc + v, 0);\n"
        "}\n"),
    visible_tests=[
        Test("basic", "assert(sumValues({a:1, b:2, c:3}) === 6);"),
        Test("empty object", "assert(sumValues({}) === 0);"),
    ],
    hidden_tests=[
        Test("single", "assert(sumValues({x: 42}) === 42);"),
        Test("negatives", "assert(sumValues({a: -5, b: 5}) === 0);"),
        Test("is a number", "assert(typeof sumValues({a: 1}) === 'number' && sumValues({a:1}) === 1);"),
    ],
    hints=[
        "sumValues({a:1}) currently does 0 + 'a' = '0a' — it's adding keys.",
        "Object.values(obj) gives the values; Object.keys gives the keys.",
        "Reduce over Object.values(obj).",
    ],
    solution_explanation=(
        "Reducing over Object.keys adds the property names. Object.values yields "
        "the values, which reduce sums numerically."),
))

add(Scenario(
    slug="js-fix-recursion-base-case-js",
    title="Fix the Recursive sumTo Base Case",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "sumTo(n) recursively sums 1..n, but its base case is wrong — it stops at "
        "n === 1 returning 0, so the result is off by one (it drops the final 1). "
        "Also it overflows the stack for n === 0. Fix the base case to handle n "
        "<= 0 (return 0) and include 1."),
    objectives=[
        "See sums come out one short",
        "Stop recursion at n <= 0",
        "Include 1 in the total",
    ],
    instructions=(
        "Fix sumTo(n): return 1 + 2 + ... + n (0 for n <= 0).\n"
        "  sumTo(5) -> 15, sumTo(0) -> 0\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function sumTo(n) {\n"
        "  if (n === 1) return 0; // bug: drops 1 and recurses forever for n<=0\n"
        "  return n + sumTo(n - 1);\n"
        "}\n"),
    reference=(
        "function sumTo(n) {\n"
        "  if (n <= 0) return 0;\n"
        "  return n + sumTo(n - 1);\n"
        "}\n"),
    visible_tests=[
        Test("sum to 5", "assert(sumTo(5) === 15, sumTo(5));"),
        Test("sum to 1", "assert(sumTo(1) === 1, sumTo(1));"),
    ],
    hidden_tests=[
        Test("sum to 0", "assert(sumTo(0) === 0);"),
        Test("sum to 10", "assert(sumTo(10) === 55);"),
        Test("sum to 3", "assert(sumTo(3) === 6);"),
        Test("negative is 0", "assert(sumTo(-3) === 0);"),
    ],
    hints=[
        "sumTo(5) returns 14 — one short, because the base case returns 0 at n === 1.",
        "The base case should return when n <= 0 and must let n === 1 add its 1.",
        "Use `if (n <= 0) return 0;` and keep `return n + sumTo(n - 1);`.",
    ],
    solution_explanation=(
        "Returning 0 at n === 1 drops the final 1 and never terminates for n <= 0. "
        "Basing out at n <= 0 includes 1 and handles non-positive inputs."),
))

add(Scenario(
    slug="js-fix-set-dedupe",
    title="Fix unique Losing Order / Not Deduping",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "unique(arr) should remove duplicates while preserving first-seen order, "
        "but the current filter compares each element to the WRONG index "
        "(indexOf vs the loop index is inverted), so it removes the wrong items. "
        "Fix the dedupe to keep first occurrences in order."),
    objectives=[
        "See wrong elements removed",
        "Keep an element only at its first index",
        "Preserve order",
    ],
    instructions=(
        "Fix unique(arr): return a new array with duplicates removed, preserving "
        "first-seen order.\n"
        "  unique([3,1,3,2,1]) -> [3,1,2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function unique(arr) {\n"
        "  return arr.filter((v, i) => arr.lastIndexOf(v) === i); // keeps LAST occurrence\n"
        "}\n"),
    reference=(
        "function unique(arr) {\n"
        "  return arr.filter((v, i) => arr.indexOf(v) === i);\n"
        "}\n"),
    visible_tests=[
        Test("preserves first-seen order", eq("unique([3,1,3,2,1])", "[3,1,2]")),
        Test("already unique", eq("unique([1,2,3])", "[1,2,3]")),
    ],
    hidden_tests=[
        Test("keeps first not last", eq("unique([1,2,1])", "[1,2]")),
        Test("strings", eq("unique(['b','a','b','c'])", "['b','a','c']")),
        Test("empty", eq("unique([])", "[]")),
        Test("all same", eq("unique([5,5,5])", "[5]")),
    ],
    hints=[
        "unique([1,2,1]) returns [2,1] instead of [1,2] — it keeps the LAST occurrence.",
        "To keep the FIRST occurrence, an element survives only at its indexOf position.",
        "Use arr.indexOf(v) === i (not lastIndexOf).",
    ],
    solution_explanation=(
        "lastIndexOf keeps the final occurrence, reordering output. Filtering where "
        "indexOf(v) === i keeps each element at its first position, preserving order."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: implement-missing
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-impl-flatten",
    title="Implement flatten (Deep)",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement flatten(arr): fully flatten an arbitrarily nested array of "
        "numbers into a single-level array, in order, without using "
        "flat(Infinity), and without mutating the input. The stub is empty so "
        "tests fail."),
    objectives=[
        "Recurse into nested arrays",
        "Preserve left-to-right order",
        "Do not mutate the input or use flat(Infinity)",
    ],
    instructions=(
        "Implement flatten(arr) -> single-level array, any depth.\n"
        "  flatten([1, [2, [3, [4]], 5]]) -> [1, 2, 3, 4, 5]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function flatten(arr) {\n"
        "  // TODO: return a new flat array of all numbers, in order.\n"
        "}\n"),
    reference=(
        "function flatten(arr) {\n"
        "  const out = [];\n"
        "  for (const el of arr) {\n"
        "    if (Array.isArray(el)) {\n"
        "      out.push(...flatten(el));\n"
        "    } else {\n"
        "      out.push(el);\n"
        "    }\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("one level", eq("flatten([1, [2, 3], 4])", "[1, 2, 3, 4]")),
        Test("deep example", eq("flatten([1, [2, [3, [4]], 5]])", "[1, 2, 3, 4, 5]")),
    ],
    hidden_tests=[
        Test("already flat", eq("flatten([1, 2, 3])", "[1, 2, 3]")),
        Test("nested empties", eq("flatten([[], [[]], []])", "[]")),
        Test("very deep", eq("flatten([[[[9]]]])", "[9]")),
        Test("does not mutate input",
             "const input = [1, [2, [3]]];\nconst snap = JSON.stringify(input);\nflatten(input);\n"
             "assert(JSON.stringify(input) === snap, 'input mutated');"),
    ],
    hints=[
        "For each element decide: array (recurse) or value (collect).",
        "Use Array.isArray(el) to test; push the flattened sub-result.",
        "out.push(...flatten(el)) for arrays, out.push(el) otherwise.",
    ],
    solution_explanation=(
        "Recursing into any array element and pushing scalars in order flattens "
        "arbitrary depth while building a new array."),
))

add(Scenario(
    slug="js-impl-debounce-logic",
    title="Implement a Simple Memoize",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement memoize(fn): return a function that caches results by its "
        "single argument so fn is only called once per distinct argument. A call "
        "counter is exposed by the tests via a wrapped fn. The stub is empty so "
        "tests fail."),
    objectives=[
        "Cache results keyed by the argument",
        "Return the cached value on repeat calls",
        "Call the underlying fn only once per distinct argument",
    ],
    instructions=(
        "Implement memoize(fn) -> memoized function of one argument. Repeated "
        "calls with the same argument return the cached result without re-calling "
        "fn.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function memoize(fn) {\n"
        "  // TODO: return a function that caches results by argument\n"
        "}\n"),
    reference=(
        "function memoize(fn) {\n"
        "  const cache = new Map();\n"
        "  return function (arg) {\n"
        "    if (cache.has(arg)) {\n"
        "      return cache.get(arg);\n"
        "    }\n"
        "    const result = fn(arg);\n"
        "    cache.set(arg, result);\n"
        "    return result;\n"
        "  };\n"
        "}\n"),
    visible_tests=[
        Test("returns correct result",
             "const sq = memoize((n) => n * n);\nassert(sq(4) === 16 && sq(5) === 25);"),
        Test("caches repeated call",
             "let calls = 0;\nconst f = memoize((n) => { calls++; return n + 1; });\n"
             "f(2); f(2); f(2);\nassert(calls === 1, 'fn called ' + calls + ' times');"),
    ],
    hidden_tests=[
        Test("distinct args each computed once",
             "let calls = 0;\nconst f = memoize((n) => { calls++; return n * 2; });\n"
             "f(1); f(2); f(1); f(2);\nassert(calls === 2, 'calls=' + calls);"),
        Test("cached value is correct after repeat",
             "const f = memoize((n) => n + 100);\nassert(f(7) === 107 && f(7) === 107);"),
        Test("string keys",
             "let calls = 0;\nconst f = memoize((s) => { calls++; return s.length; });\n"
             "f('ab'); f('ab');\nassert(f('ab') === 2 && calls === 1);"),
    ],
    hints=[
        "Keep a cache (a Map works well) keyed by the argument.",
        "On call: if the cache has the arg, return it; otherwise compute, store, return.",
        "Return a closure over the cache so it persists across calls.",
    ],
    solution_explanation=(
        "A Map captured in the returned closure stores results per argument; a "
        "cache hit short-circuits the call, so fn runs once per distinct input."),
))

add(Scenario(
    slug="js-impl-group-by",
    title="Implement groupBy",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement groupBy(items, keyFn): return an object mapping each key "
        "produced by keyFn to an array of the items with that key, preserving "
        "input order within each group. The stub is empty so tests fail."),
    objectives=[
        "Compute a key per item via keyFn",
        "Accumulate items into per-key arrays",
        "Preserve order within each group",
    ],
    instructions=(
        "Implement groupBy(items, keyFn) -> { key: [items...] }.\n"
        "  groupBy([1,2,3,4], n => n % 2 === 0 ? 'even' : 'odd') "
        "-> {odd:[1,3], even:[2,4]}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function groupBy(items, keyFn) {\n"
        "  // TODO: return an object of key -> array of items\n"
        "}\n"),
    reference=(
        "function groupBy(items, keyFn) {\n"
        "  const out = {};\n"
        "  for (const item of items) {\n"
        "    const key = keyFn(item);\n"
        "    if (!out[key]) {\n"
        "      out[key] = [];\n"
        "    }\n"
        "    out[key].push(item);\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("even/odd",
             eq("groupBy([1,2,3,4], n => n % 2 === 0 ? 'even' : 'odd')",
                "{odd:[1,3], even:[2,4]}")),
        Test("single group",
             eq("groupBy([2,4], () => 'all')", "{all:[2,4]}")),
    ],
    hidden_tests=[
        Test("by length",
             eq("groupBy(['a','bb','cc','d'], s => s.length)", "{1:['a','d'], 2:['bb','cc']}")),
        Test("empty", eq("groupBy([], () => 'x')", "{}")),
        Test("order preserved within group",
             eq("groupBy([10,20,11], n => n % 10)", "{0:[10,20], 1:[11]}")),
    ],
    hints=[
        "For each item compute keyFn(item) and use it as an object property.",
        "Initialize out[key] to [] the first time you see a key.",
        "Push the item into out[key] in input order.",
    ],
    solution_explanation=(
        "Bucketing items into per-key arrays (initialized on first sight) and "
        "pushing in iteration order produces ordered groups keyed by keyFn."),
))

add(Scenario(
    slug="js-impl-chunk",
    title="Implement chunk",
    language="javascript", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement chunk(arr, size): split arr into consecutive sub-arrays of "
        "length size (last may be shorter). Do not mutate the input. The stub is "
        "empty so tests fail."),
    objectives=[
        "Walk the array in steps of size",
        "Slice each window into a sub-array",
        "Handle a short final chunk and empty input",
    ],
    instructions=(
        "Implement chunk(arr, size) -> array of sub-arrays.\n"
        "  chunk([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function chunk(arr, size) {\n"
        "  // TODO: return arr split into chunks of length size\n"
        "}\n"),
    reference=(
        "function chunk(arr, size) {\n"
        "  const out = [];\n"
        "  for (let i = 0; i < arr.length; i += size) {\n"
        "    out.push(arr.slice(i, i + size));\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("uneven", eq("chunk([1,2,3,4,5], 2)", "[[1,2],[3,4],[5]]")),
        Test("even", eq("chunk([1,2,3,4], 2)", "[[1,2],[3,4]]")),
    ],
    hidden_tests=[
        Test("size three", eq("chunk([1,2,3,4,5,6,7], 3)", "[[1,2,3],[4,5,6],[7]]")),
        Test("size larger than array", eq("chunk([1,2], 5)", "[[1,2]]")),
        Test("empty", eq("chunk([], 3)", "[]")),
        Test("does not mutate",
             "const src = [1,2,3,4];\nchunk(src, 2);\nassert(JSON.stringify(src) === JSON.stringify([1,2,3,4]));"),
    ],
    hints=[
        "Step an index i from 0 by `size` each iteration.",
        "slice(i, i + size) copies one chunk without mutating the source.",
        "Push each slice into the output array.",
    ],
    solution_explanation=(
        "Iterating in steps of size and slicing [i, i+size) builds non-overlapping "
        "chunks; slice handles the short final chunk and never mutates the input."),
))

add(Scenario(
    slug="js-impl-title-case",
    title="Implement titleCase",
    language="javascript", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement titleCase(s): capitalize the first letter of each "
        "space-separated word and lowercase the rest. Single spaces between words. "
        "The stub is empty so tests fail."),
    objectives=[
        "Split on spaces into words",
        "Capitalize the first letter, lowercase the rest of each word",
        "Rejoin with single spaces",
    ],
    instructions=(
        "Implement titleCase(s).\n"
        "  titleCase('hello WORLD') -> 'Hello World'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function titleCase(s) {\n"
        "  // TODO: capitalize each word, lowercasing the rest\n"
        "}\n"),
    reference=(
        "function titleCase(s) {\n"
        "  return s\n"
        "    .split(' ')\n"
        "    .map((w) => (w.length === 0 ? w : w[0].toUpperCase() + w.slice(1).toLowerCase()))\n"
        "    .join(' ');\n"
        "}\n"),
    visible_tests=[
        Test("mixed case", "assert(titleCase('hello WORLD') === 'Hello World');"),
        Test("single word", "assert(titleCase('javaSCRIPT') === 'Javascript');"),
    ],
    hidden_tests=[
        Test("three words", "assert(titleCase('the quick brown') === 'The Quick Brown');"),
        Test("already title", "assert(titleCase('Foo Bar') === 'Foo Bar');"),
        Test("empty", "assert(titleCase('') === '');"),
        Test("single letters", "assert(titleCase('a b c') === 'A B C');"),
    ],
    hints=[
        "Split on ' ' to get words.",
        "For each word: uppercase the first char, lowercase the rest.",
        "w[0].toUpperCase() + w.slice(1).toLowerCase(), then join(' '). Guard empty words.",
    ],
    solution_explanation=(
        "Splitting on spaces, transforming each word's first letter up and the "
        "remainder down, then rejoining produces clean title case."),
))

add(Scenario(
    slug="js-impl-fibonacci-iter",
    title="Implement Fibonacci (Iterative)",
    language="javascript", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement fib(n): the n-th Fibonacci number, 0-indexed (0,1,1,2,3,5,...). "
        "It must be efficient (no exponential recursion) so large n is fast. The "
        "stub is empty so tests fail."),
    objectives=[
        "Return the correct base cases",
        "Iterate to avoid exponential recursion",
        "Compute large n quickly",
    ],
    instructions=(
        "Implement fib(n), 0-indexed.\n"
        "  fib(0)=0, fib(1)=1, fib(10)=55\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function fib(n) {\n"
        "  // TODO: return the n-th Fibonacci number (0-indexed)\n"
        "}\n"),
    reference=(
        "function fib(n) {\n"
        "  if (n < 2) return n;\n"
        "  let a = 0;\n"
        "  let b = 1;\n"
        "  for (let i = 2; i <= n; i++) {\n"
        "    const next = a + b;\n"
        "    a = b;\n"
        "    b = next;\n"
        "  }\n"
        "  return b;\n"
        "}\n"),
    visible_tests=[
        Test("base cases", "assert(fib(0) === 0 && fib(1) === 1);"),
        Test("fib(10)", "assert(fib(10) === 55);"),
    ],
    hidden_tests=[
        Test("fib(2)", "assert(fib(2) === 1);"),
        Test("fib(20)", "assert(fib(20) === 6765);"),
        Test("fib(30) fast", "assert(fib(30) === 832040);"),
        Test("sequence prefix",
             eq("[0,1,2,3,4,5,6].map(fib)", "[0,1,1,2,3,5,8]")),
    ],
    hints=[
        "fib(0)=0 and fib(1)=1 are the base cases.",
        "Use a loop with two running values a and b instead of recursion.",
        "Each step: next = a + b; a = b; b = next.",
    ],
    solution_explanation=(
        "Iterating with two rolling variables computes Fibonacci in O(n) without "
        "the exponential blowup of naive recursion."),
))

add(Scenario(
    slug="js-impl-deep-equal",
    title="Implement deepEqual",
    language="javascript", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement deepEqual(a, b): structural equality for JSON-like values — "
        "primitives, arrays, and plain objects (nested). Order of object keys "
        "doesn't matter; array order does. The stub is empty so tests fail."),
    objectives=[
        "Compare primitives strictly",
        "Recurse into arrays (order-sensitive) and objects (order-insensitive)",
        "Return false on any structural difference",
    ],
    instructions=(
        "Implement deepEqual(a, b) -> boolean for nested arrays/objects/primitives.\n"
        "  deepEqual({x:[1,2]}, {x:[1,2]}) -> true\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function deepEqual(a, b) {\n"
        "  // TODO: structural equality for primitives, arrays, plain objects\n"
        "}\n"),
    reference=(
        "function deepEqual(a, b) {\n"
        "  if (a === b) return true;\n"
        "  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) {\n"
        "    return false;\n"
        "  }\n"
        "  const aArr = Array.isArray(a);\n"
        "  const bArr = Array.isArray(b);\n"
        "  if (aArr !== bArr) return false;\n"
        "  if (aArr) {\n"
        "    if (a.length !== b.length) return false;\n"
        "    for (let i = 0; i < a.length; i++) {\n"
        "      if (!deepEqual(a[i], b[i])) return false;\n"
        "    }\n"
        "    return true;\n"
        "  }\n"
        "  const aKeys = Object.keys(a);\n"
        "  const bKeys = Object.keys(b);\n"
        "  if (aKeys.length !== bKeys.length) return false;\n"
        "  for (const k of aKeys) {\n"
        "    if (!Object.prototype.hasOwnProperty.call(b, k)) return false;\n"
        "    if (!deepEqual(a[k], b[k])) return false;\n"
        "  }\n"
        "  return true;\n"
        "}\n"),
    visible_tests=[
        Test("nested equal", "assert(deepEqual({x:[1,2]}, {x:[1,2]}) === true);"),
        Test("different value", "assert(deepEqual({x:1}, {x:2}) === false);"),
    ],
    hidden_tests=[
        Test("key order irrelevant", "assert(deepEqual({a:1,b:2}, {b:2,a:1}) === true);"),
        Test("array order matters", "assert(deepEqual([1,2], [2,1]) === false);"),
        Test("primitives", "assert(deepEqual(3, 3) === true && deepEqual('a', 'b') === false);"),
        Test("nested deep", "assert(deepEqual({a:{b:{c:[1]}}}, {a:{b:{c:[1]}}}) === true);"),
        Test("missing key", "assert(deepEqual({a:1}, {a:1,b:2}) === false);"),
        Test("array vs object", "assert(deepEqual([], {}) === false);"),
    ],
    hints=[
        "Strict-equal primitives short-circuit; otherwise both must be objects.",
        "Arrays compare length + each index in order; objects compare key sets + each value.",
        "Recurse on each element/value with deepEqual.",
    ],
    solution_explanation=(
        "After a strict-equality fast path, the function distinguishes arrays from "
        "objects, checks matching shape (length / key set), and recurses element- "
        "and value-wise."),
))

add(Scenario(
    slug="js-impl-validate-credit-card",
    title="Implement the Luhn Checksum",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement luhnValid(digits): given a string of digits, return true if it "
        "passes the Luhn checksum (used for credit-card numbers). The stub is "
        "empty so tests fail. Non-digit characters should make it false."),
    objectives=[
        "Double every second digit from the right",
        "Subtract 9 from doubled values over 9",
        "Return true only when the total is a multiple of 10",
    ],
    instructions=(
        "Implement luhnValid(digits) -> boolean (Luhn algorithm). Reject strings "
        "with any non-digit.\n"
        "  luhnValid('4539148803436467') -> true\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function luhnValid(digits) {\n"
        "  // TODO: return true iff digits passes the Luhn checksum\n"
        "}\n"),
    reference=(
        "function luhnValid(digits) {\n"
        "  if (!/^[0-9]+$/.test(digits)) return false;\n"
        "  let sum = 0;\n"
        "  let double = false;\n"
        "  for (let i = digits.length - 1; i >= 0; i--) {\n"
        "    let d = digits.charCodeAt(i) - 48;\n"
        "    if (double) {\n"
        "      d *= 2;\n"
        "      if (d > 9) d -= 9;\n"
        "    }\n"
        "    sum += d;\n"
        "    double = !double;\n"
        "  }\n"
        "  return sum % 10 === 0;\n"
        "}\n"),
    visible_tests=[
        Test("valid number", "assert(luhnValid('4539148803436467') === true);"),
        Test("invalid number", "assert(luhnValid('1234567812345678') === false);"),
    ],
    hidden_tests=[
        Test("simple valid", "assert(luhnValid('79927398713') === true);"),
        Test("off by one invalid", "assert(luhnValid('79927398710') === false);"),
        Test("non-digit rejected", "assert(luhnValid('1234a') === false);"),
        Test("empty rejected", "assert(luhnValid('') === false);"),
    ],
    hints=[
        "Walk the digits from right to left, doubling every second one.",
        "If a doubled digit exceeds 9, subtract 9.",
        "The number is valid iff the summed total is divisible by 10. Reject non-digits first.",
    ],
    solution_explanation=(
        "The Luhn algorithm doubles alternate digits from the right (subtracting 9 "
        "when over 9) and checks the total modulo 10; non-digit input is rejected."),
))

add(Scenario(
    slug="js-impl-event-emitter",
    title="Implement a Tiny EventEmitter",
    language="javascript", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement an EventEmitter class with on(event, handler), off(event, "
        "handler), and emit(event, ...args). emit calls every handler registered "
        "for the event, in registration order, with the provided args. off "
        "removes a specific handler. The stub is empty so tests fail."),
    objectives=[
        "Register handlers per event name",
        "emit invokes all handlers in order with args",
        "off removes the specific handler",
    ],
    instructions=(
        "Implement class EventEmitter with on(event, handler), off(event, "
        "handler), emit(event, ...args). Handlers fire in registration order.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "class EventEmitter {\n"
        "  // TODO: implement on, off, emit\n"
        "}\n"),
    reference=(
        "class EventEmitter {\n"
        "  constructor() {\n"
        "    this.handlers = {};\n"
        "  }\n"
        "  on(event, handler) {\n"
        "    if (!this.handlers[event]) this.handlers[event] = [];\n"
        "    this.handlers[event].push(handler);\n"
        "  }\n"
        "  off(event, handler) {\n"
        "    if (!this.handlers[event]) return;\n"
        "    this.handlers[event] = this.handlers[event].filter((h) => h !== handler);\n"
        "  }\n"
        "  emit(event, ...args) {\n"
        "    const list = this.handlers[event] || [];\n"
        "    for (const h of list.slice()) {\n"
        "      h(...args);\n"
        "    }\n"
        "  }\n"
        "}\n"),
    visible_tests=[
        Test("on and emit",
             "const e = new EventEmitter();\nlet got = 0;\n"
             "e.on('tick', (n) => { got = n; });\ne.emit('tick', 42);\nassert(got === 42);"),
        Test("multiple handlers in order",
             "const e = new EventEmitter();\nconst seen = [];\n"
             "e.on('x', () => seen.push(1));\ne.on('x', () => seen.push(2));\ne.emit('x');\n"
             "assert(JSON.stringify(seen) === JSON.stringify([1, 2]));"),
    ],
    hidden_tests=[
        Test("off removes a handler",
             "const e = new EventEmitter();\nlet calls = 0;\nconst h = () => { calls++; };\n"
             "e.on('a', h);\ne.off('a', h);\ne.emit('a');\nassert(calls === 0, 'calls=' + calls);"),
        Test("off keeps other handlers",
             "const e = new EventEmitter();\nconst seen = [];\nconst h1 = () => seen.push(1);\nconst h2 = () => seen.push(2);\n"
             "e.on('a', h1);\ne.on('a', h2);\ne.off('a', h1);\ne.emit('a');\n"
             "assert(JSON.stringify(seen) === JSON.stringify([2]));"),
        Test("emit with multiple args",
             "const e = new EventEmitter();\nlet sum = 0;\ne.on('add', (a, b) => { sum = a + b; });\ne.emit('add', 3, 4);\nassert(sum === 7);"),
        Test("emit unknown event is a no-op",
             "const e = new EventEmitter();\ne.emit('nope');\nassert(true);"),
    ],
    hints=[
        "Store handlers in an object keyed by event name, each value an array.",
        "on pushes the handler; emit iterates the array calling each with ...args.",
        "off filters out the exact handler reference from that event's array.",
    ],
    solution_explanation=(
        "A map of event -> handler array supports registration order on emit, and "
        "filtering by reference in off removes a specific handler."),
))

add(Scenario(
    slug="js-impl-curry-add",
    title="Implement a Range Function",
    language="javascript", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement range(start, end, step=1): return an array of numbers from "
        "start (inclusive) up to but NOT including end, advancing by step. Assume "
        "step > 0 and end >= start. The stub is empty so tests fail."),
    objectives=[
        "Generate values from start while < end",
        "Advance by step (default 1)",
        "Exclude the end value",
    ],
    instructions=(
        "Implement range(start, end, step=1) -> array [start, start+step, ...] < "
        "end.\n"
        "  range(0, 5) -> [0,1,2,3,4]; range(0, 10, 2) -> [0,2,4,6,8]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function range(start, end, step = 1) {\n"
        "  // TODO: return [start .. end) advancing by step\n"
        "}\n"),
    reference=(
        "function range(start, end, step = 1) {\n"
        "  const out = [];\n"
        "  for (let i = start; i < end; i += step) {\n"
        "    out.push(i);\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("default step", eq("range(0, 5)", "[0,1,2,3,4]")),
        Test("step two", eq("range(0, 10, 2)", "[0,2,4,6,8]")),
    ],
    hidden_tests=[
        Test("non-zero start", eq("range(3, 7)", "[3,4,5,6]")),
        Test("empty when start equals end", eq("range(4, 4)", "[]")),
        Test("step three", eq("range(1, 10, 3)", "[1,4,7]")),
        Test("excludes end", "assert(range(0, 5).indexOf(5) === -1);"),
    ],
    hints=[
        "Loop a counter from start while it is strictly less than end.",
        "Increment the counter by step each iteration (default step is 1).",
        "Push each value; the end value is never included.",
    ],
    solution_explanation=(
        "A loop from start while i < end, stepping by step, collects the half-open "
        "range [start, end)."),
))

add(Scenario(
    slug="js-impl-counter-frequency",
    title="Implement wordFrequency",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement wordFrequency(text): return an object mapping each lowercased "
        "word to its count. Words are separated by whitespace; trim surrounding "
        "punctuation (.,!?). The stub is empty so tests fail."),
    objectives=[
        "Split on whitespace and lowercase",
        "Strip surrounding punctuation from words",
        "Count occurrences into an object",
    ],
    instructions=(
        "Implement wordFrequency(text) -> { word: count }. Lowercase words; strip "
        "leading/trailing .,!? ; split on whitespace; ignore empty tokens.\n"
        "  wordFrequency('Cat cat, dog.') -> {cat:2, dog:1}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function wordFrequency(text) {\n"
        "  // TODO: return a map of normalized word -> count\n"
        "}\n"),
    reference=(
        "function wordFrequency(text) {\n"
        "  const out = {};\n"
        "  const tokens = text.split(/\\s+/);\n"
        "  for (const raw of tokens) {\n"
        "    const word = raw.replace(/^[.,!?]+|[.,!?]+$/g, '').toLowerCase();\n"
        "    if (word === '') continue;\n"
        "    out[word] = (out[word] || 0) + 1;\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("counts and normalizes",
             eq("wordFrequency('Cat cat, dog.')", "{cat:2, dog:1}")),
        Test("single", eq("wordFrequency('hello')", "{hello:1}")),
    ],
    hidden_tests=[
        Test("punctuation stripped", eq("wordFrequency('hi! hi? hi.')", "{hi:3}")),
        Test("case folded", eq("wordFrequency('The THE the')", "{the:3}")),
        Test("extra spaces",
             eq("wordFrequency('a   a  b')", "{a:2, b:1}")),
        Test("empty text", eq("wordFrequency('')", "{}")),
    ],
    hints=[
        "Split on /\\s+/ to tolerate multiple spaces.",
        "Strip leading/trailing punctuation with a regex and lowercase the word.",
        "Accumulate counts with out[word] = (out[word] || 0) + 1; skip empty tokens.",
    ],
    solution_explanation=(
        "Splitting on whitespace, stripping edge punctuation, lowercasing, and "
        "accumulating into an object yields a normalized frequency map."),
))

add(Scenario(
    slug="js-impl-promise-retry-sync",
    title="Implement pick (Object Subset)",
    language="javascript", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement pick(obj, keys): return a NEW object containing only the "
        "entries of obj whose key is in the keys array. Keys not present in obj "
        "are skipped. The original object is not mutated. The stub is empty so "
        "tests fail."),
    objectives=[
        "Copy only the requested keys",
        "Skip keys absent from the source",
        "Return a new object without mutating the input",
    ],
    instructions=(
        "Implement pick(obj, keys) -> new object with only those keys that exist "
        "in obj.\n"
        "  pick({a:1,b:2,c:3}, ['a','c']) -> {a:1, c:3}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function pick(obj, keys) {\n"
        "  // TODO: return a new object with only the selected keys\n"
        "}\n"),
    reference=(
        "function pick(obj, keys) {\n"
        "  const out = {};\n"
        "  for (const k of keys) {\n"
        "    if (Object.prototype.hasOwnProperty.call(obj, k)) {\n"
        "      out[k] = obj[k];\n"
        "    }\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("subset", eq("pick({a:1,b:2,c:3}, ['a','c'])", "{a:1,c:3}")),
        Test("empty keys", eq("pick({a:1}, [])", "{}")),
    ],
    hidden_tests=[
        Test("missing key skipped", eq("pick({a:1}, ['a','z'])", "{a:1}")),
        Test("all keys", eq("pick({x:1,y:2}, ['x','y'])", "{x:1,y:2}")),
        Test("does not mutate source",
             "const src = {a:1,b:2};\npick(src, ['a']);\nassert(JSON.stringify(src) === JSON.stringify({a:1,b:2}));"),
        Test("falsy values kept",
             eq("pick({a:0, b:false, c:1}, ['a','b'])", "{a:0, b:false}")),
    ],
    hints=[
        "Iterate over the keys array, not the object.",
        "Use hasOwnProperty to copy only keys that actually exist on obj.",
        "Build into a fresh object so the source isn't mutated; keep falsy values like 0/false.",
    ],
    solution_explanation=(
        "Iterating the requested keys and copying only those present (via "
        "hasOwnProperty, so falsy values are retained) yields the subset without "
        "mutating the source."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: log-analysis + fix
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-logfix-cannot-read-undefined",
    title="Log Analysis: Fix 'Cannot read properties of undefined'",
    language="javascript", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "Production logged: `TypeError: Cannot read properties of undefined "
        "(reading 'city')` in getCity(). The user object may lack an `address`. "
        "Use optional chaining (or guards) to return the city or a fallback "
        "'unknown' without crashing."),
    objectives=[
        "Read the TypeError and find the unsafe nested access",
        "Use optional chaining / guards for the missing address",
        "Return 'unknown' when the path is absent",
    ],
    instructions=(
        "Fix getCity(user): return user.address.city, or 'unknown' if address (or "
        "city) is missing. The log shows it crashes when address is undefined.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "// Production log:\n"
        "//   TypeError: Cannot read properties of undefined (reading 'city')\n"
        "//     at getCity (user.js:2)\n"
        "\n"
        "function getCity(user) {\n"
        "  return user.address.city; // crashes when address is undefined\n"
        "}\n"),
    reference=(
        "function getCity(user) {\n"
        "  return user?.address?.city ?? 'unknown';\n"
        "}\n"),
    visible_tests=[
        Test("has address", "assert(getCity({ address: { city: 'NYC' } }) === 'NYC');"),
        Test("missing address", "assert(getCity({}) === 'unknown', getCity({}));"),
    ],
    hidden_tests=[
        Test("missing city", "assert(getCity({ address: {} }) === 'unknown');"),
        Test("null user", "assert(getCity(null) === 'unknown');"),
        Test("does not throw on undefined", "assert(getCity(undefined) === 'unknown');"),
        Test("real city returned", "assert(getCity({ address: { city: 'Paris' } }) === 'Paris');"),
    ],
    hints=[
        "The log shows reading .city on an undefined address.",
        "Optional chaining (?.) short-circuits to undefined instead of throwing.",
        "Return user?.address?.city ?? 'unknown'.",
    ],
    solution_explanation=(
        "Optional chaining stops at the first nullish link and yields undefined, "
        "and ?? supplies the 'unknown' fallback — no TypeError."),
))

add(Scenario(
    slug="js-logfix-json-parse-throw",
    title="Log Analysis: Fix the JSON.parse Crash",
    language="javascript", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "The log shows `SyntaxError: Unexpected token ... in JSON` from "
        "safeParse() because JSON.parse throws on malformed input. Wrap it so "
        "invalid JSON returns a provided fallback instead of crashing."),
    objectives=[
        "Identify the throwing JSON.parse from the log",
        "Catch the parse error",
        "Return the fallback on failure",
    ],
    instructions=(
        "Fix safeParse(str, fallback): return the parsed JSON, or `fallback` if "
        "str is not valid JSON. Never throw.\n"
        "  safeParse('{\"a\":1}', null) -> {a:1}; safeParse('oops', null) -> null\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "// Production log:\n"
        "//   SyntaxError: Unexpected token o in JSON at position 0\n"
        "//     at safeParse -> JSON.parse(str)\n"
        "\n"
        "function safeParse(str, fallback) {\n"
        "  return JSON.parse(str); // throws on invalid JSON\n"
        "}\n"),
    reference=(
        "function safeParse(str, fallback) {\n"
        "  try {\n"
        "    return JSON.parse(str);\n"
        "  } catch (e) {\n"
        "    return fallback;\n"
        "  }\n"
        "}\n"),
    visible_tests=[
        Test("valid json", eq("safeParse('{\"a\":1}', null)", "{a:1}")),
        Test("invalid returns fallback", "assert(safeParse('oops', null) === null);"),
    ],
    hidden_tests=[
        Test("array json", eq("safeParse('[1,2,3]', [])", "[1,2,3]")),
        Test("invalid uses custom fallback",
             eq("safeParse('not json', {error: true})", "{error: true}")),
        Test("does not throw",
             "let threw = false;\ntry { safeParse('{bad', 0); } catch (e) { threw = true; }\nassert(threw === false);"),
        Test("number json", "assert(safeParse('42', null) === 42);"),
    ],
    hints=[
        "The log shows JSON.parse throwing a SyntaxError on bad input.",
        "Wrap JSON.parse in try/catch.",
        "Return fallback from the catch block.",
    ],
    solution_explanation=(
        "JSON.parse throws on malformed input. A try/catch returning the fallback "
        "makes parsing total and crash-free."),
))

add(Scenario(
    slug="js-logfix-maximum-call-stack",
    title="Log Analysis: Fix the Maximum Call Stack Error",
    language="javascript", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "The log shows `RangeError: Maximum call stack size exceeded` from "
        "countdown() because it recurses without ever hitting a base case (it "
        "decrements but never stops at 0). Add the base case so it terminates and "
        "returns the list of values from n down to 1."),
    objectives=[
        "Read the stack-overflow error and find the missing base case",
        "Stop recursion at n <= 0",
        "Return the countdown array",
    ],
    instructions=(
        "Fix countdown(n): return [n, n-1, ..., 1] (empty for n <= 0). The log "
        "shows infinite recursion.\n"
        "  countdown(3) -> [3, 2, 1]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "// Production log:\n"
        "//   RangeError: Maximum call stack size exceeded\n"
        "//     at countdown (count.js:2)\n"
        "\n"
        "function countdown(n) {\n"
        "  return [n, ...countdown(n - 1)]; // never stops\n"
        "}\n"),
    reference=(
        "function countdown(n) {\n"
        "  if (n <= 0) return [];\n"
        "  return [n, ...countdown(n - 1)];\n"
        "}\n"),
    visible_tests=[
        Test("countdown 3", eq("countdown(3)", "[3, 2, 1]")),
        Test("countdown 1", eq("countdown(1)", "[1]")),
    ],
    hidden_tests=[
        Test("countdown 0 empty", eq("countdown(0)", "[]")),
        Test("countdown 5", eq("countdown(5)", "[5, 4, 3, 2, 1]")),
        Test("negative empty", eq("countdown(-2)", "[]")),
        Test("does not overflow",
             "let ok = true;\ntry { countdown(4); } catch (e) { ok = false; }\nassert(ok);"),
    ],
    hints=[
        "The log shows recursion that never terminates — no base case.",
        "Recursion must stop when n reaches 0 (or below).",
        "Add `if (n <= 0) return [];` before the recursive spread.",
    ],
    solution_explanation=(
        "Without a base case the recursion descends forever. Returning [] for n <= "
        "0 terminates it and builds the countdown array."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: code-review / refactor
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-review-pure-no-mutate-sort",
    title="Refactor: Make sortedCopy Pure",
    language="javascript", kind="review", difficulty="medium", scenario_type="fix",
    description=(
        "sortedCopy(arr) is supposed to return a sorted COPY, leaving the input "
        "untouched, but it sorts arr in place and returns it, so callers see their "
        "array reordered. Refactor it to sort a copy. The hidden test pins the "
        "no-mutation contract."),
    objectives=[
        "Recognize the in-place sort side effect",
        "Sort a copy instead of the original",
        "Return ascending-sorted values without mutating input",
    ],
    instructions=(
        "Refactor sortedCopy(arr): return a new ascending-sorted array; do NOT "
        "mutate the input.\n"
        "  sortedCopy([3,1,2]) -> [1,2,3], original stays [3,1,2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function sortedCopy(arr) {\n"
        "  return arr.sort((a, b) => a - b); // sorts in place, mutates input\n"
        "}\n"),
    reference=(
        "function sortedCopy(arr) {\n"
        "  return [...arr].sort((a, b) => a - b);\n"
        "}\n"),
    visible_tests=[
        Test("sorts ascending", eq("sortedCopy([3,1,2])", "[1,2,3]")),
        Test("already sorted", eq("sortedCopy([1,2,3])", "[1,2,3]")),
    ],
    hidden_tests=[
        Test("does not mutate input",
             "const src = [3, 1, 2];\nsortedCopy(src);\n"
             "assert(JSON.stringify(src) === JSON.stringify([3, 1, 2]), 'input mutated');"),
        Test("returns a new array",
             "const src = [2, 1];\nconst out = sortedCopy(src);\nassert(out !== src);"),
        Test("negatives", eq("sortedCopy([0, -5, 3, -1])", "[-5, -1, 0, 3]")),
    ],
    hints=[
        "After sortedCopy(src), src is itself sorted — Array.sort mutates in place.",
        "Copy the array first, then sort the copy.",
        "Return [...arr].sort((a, b) => a - b).",
    ],
    solution_explanation=(
        "Array.sort mutates its receiver. Spreading into a new array first sorts a "
        "copy and leaves the caller's array intact."),
))

add(Scenario(
    slug="js-review-guard-clause-validate",
    title="Refactor: Validate the Shipping Calculator",
    language="javascript", kind="review", difficulty="medium", scenario_type="fix",
    description=(
        "shippingCost(weight) returns a cost based on weight, but it has no "
        "validation: negative weights produce negative costs, and zero should be "
        "free. Refactor with guard clauses: weight < 0 throws a RangeError; weight "
        "=== 0 returns 0; otherwise base 5 + 2 per kg. The tests pin these rules."),
    objectives=[
        "Reject negative weights with a guard clause",
        "Return 0 for zero weight",
        "Compute the documented cost otherwise",
    ],
    instructions=(
        "Refactor shippingCost(weight): if weight < 0 throw RangeError; if weight "
        "=== 0 return 0; else return 5 + 2 * weight.\n"
        "  shippingCost(3) -> 11\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function shippingCost(weight) {\n"
        "  return 5 + 2 * weight; // no validation; negative -> negative cost; 0 not free\n"
        "}\n"),
    reference=(
        "function shippingCost(weight) {\n"
        "  if (weight < 0) {\n"
        "    throw new RangeError('weight cannot be negative');\n"
        "  }\n"
        "  if (weight === 0) {\n"
        "    return 0;\n"
        "  }\n"
        "  return 5 + 2 * weight;\n"
        "}\n"),
    visible_tests=[
        Test("normal weight", "assert(shippingCost(3) === 11);"),
        Test("zero is free", "assert(shippingCost(0) === 0, shippingCost(0));"),
    ],
    hidden_tests=[
        Test("negative throws",
             "let threw = false;\ntry { shippingCost(-1); } catch (e) { threw = e instanceof RangeError; }\n"
             "assert(threw, 'should throw RangeError on negative');"),
        Test("one kg", "assert(shippingCost(1) === 7);"),
        Test("large weight", "assert(shippingCost(10) === 25);"),
    ],
    hints=[
        "shippingCost(-1) returns 3, and shippingCost(0) returns 5 — both wrong.",
        "Add guard clauses at the top for the negative and zero cases.",
        "Throw RangeError for < 0, return 0 for === 0, else 5 + 2 * weight.",
    ],
    solution_explanation=(
        "Guard clauses make the edge cases explicit: negatives are rejected and "
        "zero is free, leaving the formula for the normal path."),
))

add(Scenario(
    slug="js-review-array-reduce-clarity",
    title="Refactor: Fix countBy Aggregation",
    language="javascript", kind="review", difficulty="medium", scenario_type="fix",
    description=(
        "countBy(items, keyFn) should return an object mapping each key to the "
        "NUMBER of items with that key, but it stores the last item instead of a "
        "count. Refactor it to accumulate counts. The tests pin the count "
        "contract."),
    objectives=[
        "See values are items, not counts",
        "Increment a numeric counter per key",
        "Return the correct frequency object",
    ],
    instructions=(
        "Fix countBy(items, keyFn): return { key: count }.\n"
        "  countBy([1,2,3,4], n => n % 2 ? 'odd' : 'even') -> {odd:2, even:2}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function countBy(items, keyFn) {\n"
        "  const out = {};\n"
        "  for (const item of items) {\n"
        "    out[keyFn(item)] = item; // bug: stores the item, not a count\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    reference=(
        "function countBy(items, keyFn) {\n"
        "  const out = {};\n"
        "  for (const item of items) {\n"
        "    const key = keyFn(item);\n"
        "    out[key] = (out[key] || 0) + 1;\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("odd/even counts",
             eq("countBy([1,2,3,4], n => n % 2 ? 'odd' : 'even')", "{odd:2, even:2}")),
        Test("single key", eq("countBy([2,4,6], () => 'all')", "{all:3}")),
    ],
    hidden_tests=[
        Test("by length", eq("countBy(['a','bb','cc'], s => s.length)", "{1:1, 2:2}")),
        Test("empty", eq("countBy([], () => 'x')", "{}")),
        Test("values are numbers",
             "const r = countBy([1,1,1], () => 'k');\nassert(r.k === 3 && typeof r.k === 'number');"),
    ],
    hints=[
        "countBy([1,3], () => 'odd') returns {odd: 3} — it stored the item, not a count.",
        "Each key should map to a running integer count.",
        "Use out[key] = (out[key] || 0) + 1.",
    ],
    solution_explanation=(
        "Assigning the item overwrites with a value, not a tally. Initializing to "
        "0 and incrementing accumulates the count per key."),
))

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 2 (37 -> 50): more fix-bug, implement, log-analysis, refactor.
#
# Timing-based utilities (debounce/throttle) are graded deterministically: the
# tests monkeypatch the global setTimeout/clearTimeout with a controllable queue
# and a manual flush(), restoring the originals in a finally block. No real
# timers fire, so grading is synchronous and reproducible. Promise/async LOGIC
# is exercised through synchronously-resolvable shapes — never via assertions
# inside a .then callback (those would run AFTER the verdict is emitted).
# ─────────────────────────────────────────────────────────────────────────────

# ── fix-bug ──────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-fix-async-await-in-loop",
    title="Fix the Sequential await Inside forEach",
    language="javascript", kind="fix", difficulty="hard", scenario_type="fix",
    description=(
        "runAll(tasks) should run each thunk and return an array of their results "
        "in order, but it uses `forEach(async ...)` — forEach ignores the returned "
        "promises, so the function returns undefined and nothing is collected. "
        "Each task here is SYNCHRONOUS (returns a value), so the fix is to collect "
        "results with map and return the array. The stub returns undefined."),
    objectives=[
        "See forEach swallow the per-item results",
        "Collect each task's result into an array",
        "Return the results in input order",
    ],
    instructions=(
        "Fix runAll(tasks): call each task (a zero-arg function) and return an "
        "array of the results, in order.\n"
        "  runAll([() => 1, () => 2]) -> [1, 2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function runAll(tasks) {\n"
        "  const out = [];\n"
        "  tasks.forEach((task) => { task(); }); // results discarded; returns undefined\n"
        "}\n"),
    reference=(
        "function runAll(tasks) {\n"
        "  return tasks.map((task) => task());\n"
        "}\n"),
    visible_tests=[
        Test("collects results", eq("runAll([() => 1, () => 2])", "[1, 2]")),
        Test("returns an array",
             "assert(Array.isArray(runAll([() => 'x'])), 'should return an array');"),
    ],
    hidden_tests=[
        Test("order preserved", eq("runAll([() => 'a', () => 'b', () => 'c'])", "['a','b','c']")),
        Test("empty", eq("runAll([])", "[]")),
        Test("computes values",
             "const r = runAll([() => 2 + 2, () => 3 * 3]);\nassert(r[0] === 4 && r[1] === 9, JSON.stringify(r));"),
        Test("not undefined",
             "assert(runAll([() => 1]) !== undefined, 'forEach returns undefined');"),
    ],
    hints=[
        "runAll([() => 1]) returns undefined — forEach throws away each task() result.",
        "forEach is for side effects; it never builds or returns a value.",
        "Use tasks.map((task) => task()) and return it.",
    ],
    solution_explanation=(
        "forEach evaluates each task but discards the return values and yields "
        "undefined. map collects each result into a new array, returned in order."),
))

add(Scenario(
    slug="js-fix-filter-truthy-predicate",
    title="Fix compact Dropping Valid Falsy-ish Values",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "compact(arr) should remove only null and undefined, keeping every other "
        "value (including 0, '', false, NaN). It currently filters with the value "
        "itself as the predicate (`arr.filter(x => x)`), which also drops 0, '', "
        "false, and NaN. Fix the predicate to reject only null/undefined."),
    objectives=[
        "See 0, '', false, NaN wrongly removed",
        "Keep all defined values, including falsy ones",
        "Remove only null and undefined",
    ],
    instructions=(
        "Fix compact(arr): return a new array with only null and undefined "
        "removed; keep 0, '', false, and NaN.\n"
        "  compact([0, null, 1, undefined, '']) -> [0, 1, '']\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function compact(arr) {\n"
        "  return arr.filter((x) => x); // also drops 0, '', false, NaN\n"
        "}\n"),
    reference=(
        "function compact(arr) {\n"
        "  return arr.filter((x) => x !== null && x !== undefined);\n"
        "}\n"),
    visible_tests=[
        Test("keeps falsy, drops nullish",
             eq("compact([0, null, 1, undefined, ''])", "[0, 1, '']")),
        Test("keeps false", eq("compact([false, null])", "[false]")),
    ],
    hidden_tests=[
        Test("keeps zero", eq("compact([0, 0, null])", "[0, 0]")),
        Test("drops only nullish",
             eq("compact([1, null, 2, undefined, 3])", "[1, 2, 3]")),
        Test("keeps NaN",
             "const r = compact([NaN, null, 1]);\nassert(r.length === 2 && Number.isNaN(r[0]) && r[1] === 1, JSON.stringify(r));"),
        Test("nothing to drop", eq("compact([1, 2, 3])", "[1, 2, 3]")),
        Test("all nullish", eq("compact([null, undefined])", "[]")),
    ],
    hints=[
        "compact([0, '']) returns [] because 0 and '' are falsy and the predicate is just `x`.",
        "You want to remove ONLY null and undefined, not all falsy values.",
        "Filter with (x) => x !== null && x !== undefined (or x != null).",
    ],
    solution_explanation=(
        "Using the value as the predicate drops every falsy value. Explicitly "
        "comparing against null and undefined keeps legitimate falsy values like "
        "0, '', false, and NaN."),
))

add(Scenario(
    slug="js-fix-hoisting-tdz",
    title="Fix the Hoisting Bug in buildLabels",
    language="javascript", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "buildLabels(items) should return ['#0: a', '#1: b', ...], but the helper "
        "result variable is USED before it is declared with const, and the loop "
        "reads `label` outside its block. Function-declaration hoisting masks the "
        "intent and the labels come out wrong/undefined. Fix the declaration order "
        "and scoping so each label is built correctly."),
    objectives=[
        "See undefined / wrong values from use-before-declare",
        "Declare variables before use, in the right scope",
        "Return the correctly numbered labels",
    ],
    instructions=(
        "Fix buildLabels(items): return an array where item i becomes '#i: ' + "
        "item.\n"
        "  buildLabels(['a','b']) -> ['#0: a', '#1: b']\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function buildLabels(items) {\n"
        "  const out = [];\n"
        "  for (let i = 0; i < items.length; i++) {\n"
        "    out.push(label);              // used before declaration (undefined/TDZ)\n"
        "    var label = '#' + i + ': ' + items[i];\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    reference=(
        "function buildLabels(items) {\n"
        "  const out = [];\n"
        "  for (let i = 0; i < items.length; i++) {\n"
        "    const label = '#' + i + ': ' + items[i];\n"
        "    out.push(label);\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("two items", eq("buildLabels(['a', 'b'])", "['#0: a', '#1: b']")),
        Test("single", eq("buildLabels(['x'])", "['#0: x']")),
    ],
    hidden_tests=[
        Test("three items", eq("buildLabels(['p', 'q', 'r'])", "['#0: p', '#1: q', '#2: r']")),
        Test("no undefined leaked",
             "const r = buildLabels(['a']);\nassert(r[0].indexOf('undefined') === -1, r[0]);"),
        Test("empty", eq("buildLabels([])", "[]")),
        Test("numbers as items", eq("buildLabels([10, 20])", "['#0: 10', '#1: 20']")),
    ],
    hints=[
        "buildLabels(['a']) pushes undefined because `label` is read before it is assigned.",
        "var is hoisted (initialized undefined) so the push sees undefined, not the string.",
        "Declare `const label = ...;` BEFORE out.push(label) inside the loop body.",
    ],
    solution_explanation=(
        "Reading a var before its assignment yields undefined due to hoisting. "
        "Declaring the label with const before pushing it builds each entry "
        "correctly within the loop's block scope."),
))

add(Scenario(
    slug="js-fix-coercion-plus-concat",
    title="Fix the String-Concatenation Bug in addUp",
    language="javascript", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "addUp(values) should numerically sum an array that may contain numeric "
        "STRINGS (like '3'), but reduce uses `+` directly, so a string operand "
        "turns the whole thing into string concatenation ('0' + 3 -> '03'). "
        "Coerce each value to a Number before adding."),
    objectives=[
        "See numbers concatenated instead of added",
        "Convert each value to a Number before summing",
        "Return a numeric total",
    ],
    instructions=(
        "Fix addUp(values): return the numeric sum, coercing numeric strings.\n"
        "  addUp([1, '2', 3]) -> 6\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function addUp(values) {\n"
        "  return values.reduce((acc, v) => acc + v, 0); // '2' makes acc a string\n"
        "}\n"),
    reference=(
        "function addUp(values) {\n"
        "  return values.reduce((acc, v) => acc + Number(v), 0);\n"
        "}\n"),
    visible_tests=[
        Test("mixed strings and numbers", "assert(addUp([1, '2', 3]) === 6, addUp([1, '2', 3]));"),
        Test("all numbers", "assert(addUp([1, 2, 3]) === 6);"),
    ],
    hidden_tests=[
        Test("all strings", "assert(addUp(['10', '20']) === 30, addUp(['10', '20']));"),
        Test("returns a number",
             "assert(typeof addUp(['1', 2]) === 'number' && addUp(['1', 2]) === 3);"),
        Test("empty is zero", "assert(addUp([]) === 0);"),
        Test("negatives as strings", "assert(addUp(['-5', 5]) === 0);"),
    ],
    hints=[
        "addUp([1, '2', 3]) returns '0123' — once acc meets a string, + concatenates.",
        "The + operator concatenates if either side is a string.",
        "Add Number(v) (or +v) so every operand is numeric: acc + Number(v).",
    ],
    solution_explanation=(
        "A single string operand flips + into concatenation. Coercing each value "
        "with Number keeps the reduce arithmetic and returns a numeric total."),
))

add(Scenario(
    slug="js-fix-regex-global-lastindex",
    title="Fix the Stateful Global Regex in isHex",
    language="javascript", kind="fix", difficulty="hard", scenario_type="fix",
    description=(
        "isHex(s) should return whether s is a string of one or more hex digits, "
        "but it reuses a single regex literal declared with the global (g) flag "
        "and calls .test() on it. A global regex keeps lastIndex between calls, so "
        "repeated tests of the SAME string alternate true/false. Fix it so each "
        "call is independent (drop the g flag, or reset/avoid shared state)."),
    objectives=[
        "Reproduce the alternating true/false on repeated calls",
        "Understand that /g regexes carry lastIndex across .test()",
        "Make every call independent and correct",
    ],
    instructions=(
        "Fix isHex(s): return true iff s is one or more hex digits (0-9a-fA-F). "
        "Repeated calls with the same input must give the same answer.\n"
        "  isHex('1a2f') -> true (every time)\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "const HEX = /^[0-9a-f]+$/gi; // global flag => stateful lastIndex\n"
        "\n"
        "function isHex(s) {\n"
        "  return HEX.test(s); // alternates true/false on repeated same input\n"
        "}\n"),
    reference=(
        "function isHex(s) {\n"
        "  return /^[0-9a-f]+$/i.test(s);\n"
        "}\n"),
    visible_tests=[
        Test("valid hex", "assert(isHex('1a2f') === true, 'should be hex');"),
        Test("stable on repeat",
             "assert(isHex('1a2f') === true && isHex('1a2f') === true && isHex('1a2f') === true, 'must not alternate');"),
    ],
    hidden_tests=[
        Test("uppercase hex", "assert(isHex('FF') === true);"),
        Test("non-hex", "assert(isHex('xyz') === false);"),
        Test("empty is false", "assert(isHex('') === false);"),
        Test("repeated non-hex stable",
             "assert(isHex('zz') === false && isHex('zz') === false);"),
        Test("mixed invalid", "assert(isHex('1g') === false);"),
    ],
    hints=[
        "Call isHex('1a2f') twice — it returns true then false. The regex is stateful.",
        "A regex with the g flag advances lastIndex on each .test(), so it desyncs across calls.",
        "Drop the g flag (use /^[0-9a-f]+$/i) or build a fresh regex each call.",
    ],
    solution_explanation=(
        "A global-flag regex remembers lastIndex between .test() calls, so it "
        "alternates results for the same input. Removing the g flag makes each "
        "match start from the beginning, so the test is stateless and correct."),
))

# ── implement ────────────────────────────────────────────────────────────────

add(Scenario(
    slug="js-impl-debounce",
    title="Implement debounce",
    language="javascript", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement debounce(fn, delay): return a function that postpones calling "
        "fn until `delay` ms have passed since the LAST invocation; rapid repeated "
        "calls collapse into a single trailing call with the most recent "
        "arguments. Use setTimeout/clearTimeout. The stub is empty so tests fail."),
    objectives=[
        "Schedule the call with setTimeout after delay",
        "Cancel the pending timer on each new call (clearTimeout)",
        "Fire once, with the latest arguments",
    ],
    instructions=(
        "Implement debounce(fn, delay) -> debounced function. Only the final call "
        "in a burst runs, after `delay` ms of quiet, with the latest args.\n"
        "Use the global setTimeout/clearTimeout.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function debounce(fn, delay) {\n"
        "  // TODO: return a function that defers fn until `delay` ms after the last call\n"
        "}\n"),
    reference=(
        "function debounce(fn, delay) {\n"
        "  let timer = null;\n"
        "  return function (...args) {\n"
        "    clearTimeout(timer);\n"
        "    timer = setTimeout(() => { fn.apply(this, args); }, delay);\n"
        "  };\n"
        "}\n"),
    visible_tests=[
        Test("defers until flush",
             "const _oST=globalThis.setTimeout,_oCT=globalThis.clearTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{const id={};_q.push({id,cb});return id;};\n"
             "globalThis.clearTimeout=(id)=>{_q=_q.filter(e=>e.id!==id);};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(e=>e.cb());};\n"
             "try {\n"
             "  let calls=0; const d=debounce(()=>{calls++;},100);\n"
             "  d(); d(); d();\n"
             "  assert(calls===0,'should not fire before flush, got '+calls);\n"
             "  flush();\n"
             "  assert(calls===1,'should fire once after quiet, got '+calls);\n"
             "} finally { globalThis.setTimeout=_oST; globalThis.clearTimeout=_oCT; }"),
        Test("uses latest args",
             "const _oST=globalThis.setTimeout,_oCT=globalThis.clearTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{const id={};_q.push({id,cb});return id;};\n"
             "globalThis.clearTimeout=(id)=>{_q=_q.filter(e=>e.id!==id);};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(e=>e.cb());};\n"
             "try {\n"
             "  let last=null; const d=debounce((x)=>{last=x;},50);\n"
             "  d(1); d(2); d(3); flush();\n"
             "  assert(last===3,'expected latest arg 3, got '+last);\n"
             "} finally { globalThis.setTimeout=_oST; globalThis.clearTimeout=_oCT; }"),
    ],
    hidden_tests=[
        Test("only one timer survives a burst",
             "const _oST=globalThis.setTimeout,_oCT=globalThis.clearTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{const id={};_q.push({id,cb});return id;};\n"
             "globalThis.clearTimeout=(id)=>{_q=_q.filter(e=>e.id!==id);};\n"
             "try {\n"
             "  const d=debounce(()=>{},10); d(); d(); d(); d();\n"
             "  assert(_q.length===1,'expected 1 pending timer, got '+_q.length);\n"
             "} finally { globalThis.setTimeout=_oST; globalThis.clearTimeout=_oCT; }"),
        Test("separate bursts each fire",
             "const _oST=globalThis.setTimeout,_oCT=globalThis.clearTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{const id={};_q.push({id,cb});return id;};\n"
             "globalThis.clearTimeout=(id)=>{_q=_q.filter(e=>e.id!==id);};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(e=>e.cb());};\n"
             "try {\n"
             "  let calls=0; const d=debounce(()=>{calls++;},10);\n"
             "  d(); flush(); d(); flush();\n"
             "  assert(calls===2,'expected 2 calls across bursts, got '+calls);\n"
             "} finally { globalThis.setTimeout=_oST; globalThis.clearTimeout=_oCT; }"),
        Test("returns a function",
             "assert(typeof debounce(()=>{},10)==='function');"),
        Test("forwards multiple args",
             "const _oST=globalThis.setTimeout,_oCT=globalThis.clearTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{const id={};_q.push({id,cb});return id;};\n"
             "globalThis.clearTimeout=(id)=>{_q=_q.filter(e=>e.id!==id);};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(e=>e.cb());};\n"
             "try {\n"
             "  let sum=0; const d=debounce((a,b)=>{sum=a+b;},10);\n"
             "  d(2,3); flush();\n"
             "  assert(sum===5,'expected 5, got '+sum);\n"
             "} finally { globalThis.setTimeout=_oST; globalThis.clearTimeout=_oCT; }"),
    ],
    hints=[
        "Keep a timer handle in a closure variable shared across calls.",
        "On each call, clearTimeout the previous handle, then setTimeout a new one for `delay`.",
        "In the timeout callback, call fn with the latest args (fn.apply(this, args)).",
    ],
    solution_explanation=(
        "A closure holds the pending timer. Each call cancels the previous timer "
        "and schedules a fresh one, so only the final call in a burst survives and "
        "fires after `delay` ms with the most recent arguments."),
))

add(Scenario(
    slug="js-impl-throttle",
    title="Implement throttle (Leading Edge)",
    language="javascript", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement throttle(fn, interval): return a function that calls fn "
        "immediately on the first invocation, then ignores further calls until "
        "`interval` ms have elapsed (leading-edge throttling). Use setTimeout to "
        "re-open the gate. The stub is empty so tests fail."),
    objectives=[
        "Call fn immediately on the leading edge",
        "Block calls during the cooldown window",
        "Re-open after `interval` ms via setTimeout",
    ],
    instructions=(
        "Implement throttle(fn, interval) -> throttled function. The first call "
        "runs fn right away; calls during the next `interval` ms are dropped; "
        "after the window the next call runs again.\n"
        "Use the global setTimeout.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function throttle(fn, interval) {\n"
        "  // TODO: run fn on the leading edge, then ignore calls for `interval` ms\n"
        "}\n"),
    reference=(
        "function throttle(fn, interval) {\n"
        "  let blocked = false;\n"
        "  return function (...args) {\n"
        "    if (blocked) return;\n"
        "    blocked = true;\n"
        "    fn.apply(this, args);\n"
        "    setTimeout(() => { blocked = false; }, interval);\n"
        "  };\n"
        "}\n"),
    visible_tests=[
        Test("fires immediately, then blocks",
             "const _oST=globalThis.setTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{_q.push(cb);return {};};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(cb=>cb());};\n"
             "try {\n"
             "  let calls=0; const t=throttle(()=>{calls++;},100);\n"
             "  t(); t(); t();\n"
             "  assert(calls===1,'leading call only, got '+calls);\n"
             "  flush();\n"
             "  t();\n"
             "  assert(calls===2,'fires again after window, got '+calls);\n"
             "} finally { globalThis.setTimeout=_oST; }"),
        Test("returns a function",
             "assert(typeof throttle(()=>{},10)==='function');"),
    ],
    hidden_tests=[
        Test("first arg used on leading call",
             "const _oST=globalThis.setTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{_q.push(cb);return {};};\n"
             "try {\n"
             "  let seen=null; const t=throttle((x)=>{seen=x;},50);\n"
             "  t('a'); t('b');\n"
             "  assert(seen==='a','leading arg should be a, got '+seen);\n"
             "} finally { globalThis.setTimeout=_oST; }"),
        Test("blocks every call within the window",
             "const _oST=globalThis.setTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{_q.push(cb);return {};};\n"
             "try {\n"
             "  let calls=0; const t=throttle(()=>{calls++;},100);\n"
             "  for (let i=0;i<10;i++) t();\n"
             "  assert(calls===1,'only one call in window, got '+calls);\n"
             "} finally { globalThis.setTimeout=_oST; }"),
        Test("multiple windows",
             "const _oST=globalThis.setTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{_q.push(cb);return {};};\n"
             "const flush=()=>{const live=_q.slice();_q=[];live.forEach(cb=>cb());};\n"
             "try {\n"
             "  let calls=0; const t=throttle(()=>{calls++;},10);\n"
             "  t(); flush(); t(); flush(); t();\n"
             "  assert(calls===3,'expected 3 across windows, got '+calls);\n"
             "} finally { globalThis.setTimeout=_oST; }"),
        Test("forwards multiple args on leading call",
             "const _oST=globalThis.setTimeout;let _q=[];\n"
             "globalThis.setTimeout=(cb)=>{_q.push(cb);return {};};\n"
             "try {\n"
             "  let sum=0; const t=throttle((a,b)=>{sum=a+b;},10);\n"
             "  t(4,5); t(1,1);\n"
             "  assert(sum===9,'expected 9 from leading call, got '+sum);\n"
             "} finally { globalThis.setTimeout=_oST; }"),
    ],
    hints=[
        "Track a `blocked` flag in a closure.",
        "If blocked, return early; otherwise set blocked, call fn, and schedule clearing the flag.",
        "Use setTimeout(() => { blocked = false; }, interval) to re-open the gate.",
    ],
    solution_explanation=(
        "A closure flag gates calls: the first call runs fn and sets the flag; "
        "subsequent calls return until a setTimeout clears the flag after "
        "`interval` ms, implementing leading-edge throttling."),
))

add(Scenario(
    slug="js-impl-deep-clone",
    title="Implement deepClone",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement deepClone(value): return a deep copy of a JSON-like value "
        "(primitives, arrays, plain objects, nested). Mutating the clone must not "
        "affect the original, at any depth. Do not use structuredClone. The stub "
        "is empty so tests fail."),
    objectives=[
        "Return primitives as-is",
        "Recursively copy arrays and plain objects",
        "Ensure nested mutations don't leak back to the source",
    ],
    instructions=(
        "Implement deepClone(value) -> a deep copy. Nested arrays/objects are "
        "copied recursively so the clone is fully independent.\n"
        "  const c = deepClone({a:[1,2]}); c.a.push(3); // original.a stays [1,2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function deepClone(value) {\n"
        "  // TODO: return a deep copy of value (primitives, arrays, plain objects)\n"
        "}\n"),
    reference=(
        "function deepClone(value) {\n"
        "  if (value === null || typeof value !== 'object') {\n"
        "    return value;\n"
        "  }\n"
        "  if (Array.isArray(value)) {\n"
        "    return value.map((v) => deepClone(v));\n"
        "  }\n"
        "  const out = {};\n"
        "  for (const k of Object.keys(value)) {\n"
        "    out[k] = deepClone(value[k]);\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("clones nested object",
             "const src = {a:1, b:{c:2}};\nconst c = deepClone(src);\n"
             "assert(JSON.stringify(c) === JSON.stringify(src) && c !== src && c.b !== src.b, 'shallow or unequal');"),
        Test("primitive passthrough",
             "assert(deepClone(5) === 5 && deepClone('x') === 'x' && deepClone(null) === null);"),
    ],
    hidden_tests=[
        Test("nested mutation does not leak",
             "const src = {a:[1,2]};\nconst c = deepClone(src);\nc.a.push(3);\n"
             "assert(JSON.stringify(src.a) === JSON.stringify([1,2]), 'source mutated: ' + JSON.stringify(src.a));"),
        Test("array of objects independent",
             "const src = [{n:1}, {n:2}];\nconst c = deepClone(src);\nc[0].n = 99;\n"
             "assert(src[0].n === 1, 'source element mutated');"),
        Test("deep equality preserved",
             "const src = {a:{b:{c:[1,{d:2}]}}};\nassert(JSON.stringify(deepClone(src)) === JSON.stringify(src));"),
        Test("empty structures",
             "assert(JSON.stringify(deepClone({})) === '{}' && JSON.stringify(deepClone([])) === '[]');"),
        Test("top-level array copy is new",
             "const src = [1,2,3];\nconst c = deepClone(src);\nassert(c !== src && JSON.stringify(c) === JSON.stringify(src));"),
    ],
    hints=[
        "Primitives (and null) can be returned directly — there's nothing to copy.",
        "For arrays, map each element through deepClone; for objects, rebuild key by key.",
        "Recurse on every element/value so nested containers are also fresh copies.",
    ],
    solution_explanation=(
        "Primitives are returned as-is; arrays and plain objects are rebuilt with "
        "each element/value recursively cloned, producing a structure that shares "
        "no references with the original at any depth."),
))

add(Scenario(
    slug="js-impl-retry-backoff",
    title="Implement retry with Backoff (Synchronous)",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement retry(fn, maxAttempts, onWait): call the synchronous fn; if it "
        "throws, retry up to maxAttempts total attempts. Before each RETRY (not "
        "the first attempt), call onWait(attemptNumber) so a caller can observe "
        "the backoff schedule. Return fn's value on success; if all attempts "
        "throw, rethrow the last error. The stub is empty so tests fail."),
    objectives=[
        "Attempt fn and return its value on success",
        "Retry on throw up to maxAttempts, signalling each wait via onWait",
        "Rethrow the final error if every attempt fails",
    ],
    instructions=(
        "Implement retry(fn, maxAttempts, onWait) -> fn's result, retrying on "
        "throw. Call onWait(n) before the n-th retry (n starts at 1). Rethrow the "
        "last error if all attempts fail.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function retry(fn, maxAttempts, onWait) {\n"
        "  // TODO: call fn; on throw, retry up to maxAttempts, onWait(n) before each retry\n"
        "}\n"),
    reference=(
        "function retry(fn, maxAttempts, onWait) {\n"
        "  let lastError;\n"
        "  for (let attempt = 1; attempt <= maxAttempts; attempt++) {\n"
        "    try {\n"
        "      return fn();\n"
        "    } catch (e) {\n"
        "      lastError = e;\n"
        "      if (attempt < maxAttempts) {\n"
        "        onWait(attempt);\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  throw lastError;\n"
        "}\n"),
    visible_tests=[
        Test("succeeds after failures",
             "let n = 0;\nconst r = retry(() => { n++; if (n < 3) throw new Error('no'); return 'ok'; }, 5, () => {});\n"
             "assert(r === 'ok' && n === 3, 'r=' + r + ' n=' + n);"),
        Test("first try success calls fn once",
             "let n = 0;\nconst r = retry(() => { n++; return 42; }, 3, () => {});\n"
             "assert(r === 42 && n === 1, 'n=' + n);"),
    ],
    hidden_tests=[
        Test("rethrows after exhausting attempts",
             "let threw = false; let n = 0;\n"
             "try { retry(() => { n++; throw new Error('always'); }, 3, () => {}); }\n"
             "catch (e) { threw = (e.message === 'always'); }\n"
             "assert(threw && n === 3, 'threw=' + threw + ' n=' + n);"),
        Test("onWait called once per retry, not before first",
             "let waits = [];\nlet n = 0;\nretry(() => { n++; if (n < 3) throw new Error('x'); return 1; }, 5, (a) => waits.push(a));\n"
             "assert(JSON.stringify(waits) === JSON.stringify([1, 2]), 'waits=' + JSON.stringify(waits));"),
        Test("no wait on immediate success",
             "let waited = false;\nretry(() => 'done', 3, () => { waited = true; });\n"
             "assert(waited === false, 'should not wait on success');"),
        Test("single attempt rethrows without waiting",
             "let waited = false; let threw = false;\n"
             "try { retry(() => { throw new Error('one'); }, 1, () => { waited = true; }); }\n"
             "catch (e) { threw = true; }\n"
             "assert(threw && waited === false, 'threw=' + threw + ' waited=' + waited);"),
    ],
    hints=[
        "Loop attempt from 1 to maxAttempts; return fn() inside a try.",
        "On catch, remember the error; if more attempts remain, call onWait(attempt).",
        "After the loop (all failed), throw the last error you saved.",
    ],
    solution_explanation=(
        "A loop tries fn each attempt, returning on success. On failure it records "
        "the error and, when attempts remain, signals onWait(attempt) for the "
        "backoff. If the loop ends without success, the last error is rethrown."),
))

add(Scenario(
    slug="js-impl-binary-search",
    title="Implement binarySearch",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement binarySearch(sortedArr, target): return the index of target in "
        "an ascending-sorted array, or -1 if absent. Must be O(log n) (halve the "
        "search range each step), not a linear scan. The stub is empty so tests "
        "fail."),
    objectives=[
        "Maintain low/high bounds and inspect the midpoint",
        "Halve the range based on the comparison",
        "Return the index, or -1 when not found",
    ],
    instructions=(
        "Implement binarySearch(sortedArr, target) -> index or -1.\n"
        "  binarySearch([1,3,5,7,9], 7) -> 3; binarySearch([1,3,5], 4) -> -1\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function binarySearch(sortedArr, target) {\n"
        "  // TODO: return index of target via binary search, or -1\n"
        "}\n"),
    reference=(
        "function binarySearch(sortedArr, target) {\n"
        "  let low = 0;\n"
        "  let high = sortedArr.length - 1;\n"
        "  while (low <= high) {\n"
        "    const mid = Math.floor((low + high) / 2);\n"
        "    if (sortedArr[mid] === target) {\n"
        "      return mid;\n"
        "    }\n"
        "    if (sortedArr[mid] < target) {\n"
        "      low = mid + 1;\n"
        "    } else {\n"
        "      high = mid - 1;\n"
        "    }\n"
        "  }\n"
        "  return -1;\n"
        "}\n"),
    visible_tests=[
        Test("finds middle", "assert(binarySearch([1,3,5,7,9], 7) === 3, binarySearch([1,3,5,7,9], 7));"),
        Test("absent is -1", "assert(binarySearch([1,3,5], 4) === -1);"),
    ],
    hidden_tests=[
        Test("first element", "assert(binarySearch([2,4,6], 2) === 0);"),
        Test("last element", "assert(binarySearch([2,4,6,8], 8) === 3);"),
        Test("empty array", "assert(binarySearch([], 1) === -1);"),
        Test("single found", "assert(binarySearch([5], 5) === 0);"),
        Test("single absent", "assert(binarySearch([5], 9) === -1);"),
        Test("below range", "assert(binarySearch([10,20,30], 5) === -1);"),
        Test("all positions",
             "const a = [1,2,3,4,5,6,7,8];\nlet ok = true;\nfor (let i = 0; i < a.length; i++) { if (binarySearch(a, a[i]) !== i) ok = false; }\nassert(ok, 'wrong index somewhere');"),
    ],
    hints=[
        "Track low and high indices bounding the remaining search range.",
        "Compare the middle element to target: equal -> return mid; smaller -> search right; larger -> search left.",
        "Loop while low <= high; return -1 if the range empties.",
    ],
    solution_explanation=(
        "Binary search keeps a [low, high] window, compares the midpoint to the "
        "target, and discards half the range each iteration, finding the index in "
        "O(log n) or returning -1 when the window closes."),
))

add(Scenario(
    slug="js-impl-parse-query-string",
    title="Implement parseQueryString",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement parseQueryString(qs): parse a URL query string into an object. "
        "Accept an optional leading '?'. Split on '&', then on the first '='. "
        "URL-decode keys and values (decodeURIComponent). A key with no '=' maps "
        "to ''. Ignore empty segments. The stub is empty so tests fail."),
    objectives=[
        "Strip an optional leading '?' and split on '&'",
        "Split each pair on the FIRST '=' and decode both sides",
        "Map a bare key to '' and skip empty segments",
    ],
    instructions=(
        "Implement parseQueryString(qs) -> { key: value }.\n"
        "  parseQueryString('?a=1&b=2') -> {a:'1', b:'2'}\n"
        "  parseQueryString('q=hello%20world') -> {q:'hello world'}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function parseQueryString(qs) {\n"
        "  // TODO: parse a query string into an object (handle '?', '&', '=', decoding)\n"
        "}\n"),
    reference=(
        "function parseQueryString(qs) {\n"
        "  const out = {};\n"
        "  let s = qs;\n"
        "  if (s.charAt(0) === '?') {\n"
        "    s = s.slice(1);\n"
        "  }\n"
        "  if (s === '') {\n"
        "    return out;\n"
        "  }\n"
        "  for (const pair of s.split('&')) {\n"
        "    if (pair === '') {\n"
        "      continue;\n"
        "    }\n"
        "    const eq = pair.indexOf('=');\n"
        "    let key;\n"
        "    let value;\n"
        "    if (eq === -1) {\n"
        "      key = pair;\n"
        "      value = '';\n"
        "    } else {\n"
        "      key = pair.slice(0, eq);\n"
        "      value = pair.slice(eq + 1);\n"
        "    }\n"
        "    out[decodeURIComponent(key)] = decodeURIComponent(value);\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("basic pairs", eq("parseQueryString('?a=1&b=2')", "{a:'1', b:'2'}")),
        Test("decodes percent-encoding",
             eq("parseQueryString('q=hello%20world')", "{q:'hello world'}")),
    ],
    hidden_tests=[
        Test("no leading question mark", eq("parseQueryString('x=10&y=20')", "{x:'10', y:'20'}")),
        Test("empty string", eq("parseQueryString('')", "{}")),
        Test("bare key maps to empty", eq("parseQueryString('flag')", "{flag:''}")),
        Test("value containing equals",
             eq("parseQueryString('eq=a=b')", "{eq:'a=b'}")),
        Test("decodes keys too",
             eq("parseQueryString('a%20b=c')", "{'a b':'c'}")),
        Test("skips empty segments",
             eq("parseQueryString('a=1&&b=2')", "{a:'1', b:'2'}")),
    ],
    hints=[
        "If the string starts with '?', drop it; an empty remainder means {}.",
        "Split on '&'; for each pair, find the FIRST '=' (indexOf) so values may contain '='.",
        "decodeURIComponent both the key and the value; a pair with no '=' has value ''.",
    ],
    solution_explanation=(
        "After stripping an optional '?', the string is split on '&'; each "
        "non-empty pair is split at its first '=' and both halves are URL-decoded, "
        "with a bare key mapping to an empty string."),
))

add(Scenario(
    slug="js-impl-flatten-deep-depth",
    title="Implement flattenDepth",
    language="javascript", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement flattenDepth(arr, depth): flatten a nested array by AT MOST "
        "`depth` levels (depth defaults to 1). Elements deeper than `depth` stay "
        "nested. Do not use Array.prototype.flat, and do not mutate the input. The "
        "stub is empty so tests fail."),
    objectives=[
        "Flatten exactly `depth` levels, no more",
        "Leave deeper nesting intact",
        "Default depth to 1 and avoid flat()/mutation",
    ],
    instructions=(
        "Implement flattenDepth(arr, depth=1) -> array flattened up to `depth` "
        "levels.\n"
        "  flattenDepth([1, [2, [3, [4]]]], 1) -> [1, 2, [3, [4]]]\n"
        "  flattenDepth([1, [2, [3, [4]]]], 2) -> [1, 2, 3, [4]]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "function flattenDepth(arr, depth = 1) {\n"
        "  // TODO: flatten up to `depth` levels (no flat(), no mutation)\n"
        "}\n"),
    reference=(
        "function flattenDepth(arr, depth = 1) {\n"
        "  const out = [];\n"
        "  for (const el of arr) {\n"
        "    if (Array.isArray(el) && depth > 0) {\n"
        "      out.push(...flattenDepth(el, depth - 1));\n"
        "    } else {\n"
        "      out.push(el);\n"
        "    }\n"
        "  }\n"
        "  return out;\n"
        "}\n"),
    visible_tests=[
        Test("depth one", eq("flattenDepth([1, [2, [3, [4]]]], 1)", "[1, 2, [3, [4]]]")),
        Test("depth two", eq("flattenDepth([1, [2, [3, [4]]]], 2)", "[1, 2, 3, [4]]")),
    ],
    hidden_tests=[
        Test("default depth is one",
             eq("flattenDepth([1, [2, [3]]])", "[1, 2, [3]]")),
        Test("depth zero is unchanged",
             eq("flattenDepth([1, [2, [3]]], 0)", "[1, [2, [3]]]")),
        Test("deep enough fully flattens",
             eq("flattenDepth([1, [2, [3, [4]]]], 5)", "[1, 2, 3, 4]")),
        Test("already flat", eq("flattenDepth([1, 2, 3], 3)", "[1, 2, 3]")),
        Test("does not mutate input",
             "const src = [1, [2, [3]]];\nconst snap = JSON.stringify(src);\nflattenDepth(src, 2);\n"
             "assert(JSON.stringify(src) === snap, 'input mutated');"),
        Test("mixed shapes",
             eq("flattenDepth([[1, 2], [3, [4]]], 1)", "[1, 2, 3, [4]]")),
    ],
    hints=[
        "Walk the array; for an array element, only recurse when depth > 0.",
        "When you recurse, decrement depth so each level is counted once.",
        "When depth hits 0, push remaining arrays as-is (don't flatten further).",
    ],
    solution_explanation=(
        "Recursing into array elements only while depth > 0, decrementing depth "
        "per level, flattens exactly the requested number of levels and leaves "
        "deeper structure untouched without mutating the input."),
))

# ── log-analysis + fix ───────────────────────────────────────────────────────

add(Scenario(
    slug="js-logfix-assignment-in-condition",
    title="Log Analysis: Fix the Accidental Assignment in an if",
    language="javascript", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "QA reported that classify(n) labels EVERYTHING 'special', even normal "
        "numbers. The log shows the branch always taken. The bug: the if condition "
        "uses assignment (=) instead of comparison (===), so it assigns 0 to a "
        "variable and the truthiness is wrong. Fix the comparison so only n === 0 "
        "is 'special'."),
    objectives=[
        "Read the log and spot the always-true branch",
        "Replace assignment (=) with comparison (===)",
        "Label only 0 as 'special'",
    ],
    instructions=(
        "Fix classify(n): return 'special' when n === 0, otherwise 'normal'. The "
        "log shows the branch is always taken because of an accidental "
        "assignment.\n"
        "  classify(0) -> 'special'; classify(5) -> 'normal'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.js",
    broken=(
        "// QA log:\n"
        "//   classify(5) -> 'special'  (expected 'normal')\n"
        "//   classify(9) -> 'special'  (expected 'normal')\n"
        "//   every input takes the 'special' branch\n"
        "\n"
        "function classify(n) {\n"
        "  let flag = 1;\n"
        "  if (flag = 0) {            // assignment, not comparison\n"
        "    return 'normal';\n"
        "  }\n"
        "  return 'special';\n"
        "}\n"),
    reference=(
        "function classify(n) {\n"
        "  if (n === 0) {\n"
        "    return 'special';\n"
        "  }\n"
        "  return 'normal';\n"
        "}\n"),
    visible_tests=[
        Test("zero is special", "assert(classify(0) === 'special', classify(0));"),
        Test("nonzero is normal", "assert(classify(5) === 'normal', classify(5));"),
    ],
    hidden_tests=[
        Test("negative is normal", "assert(classify(-3) === 'normal');"),
        Test("large is normal", "assert(classify(1000) === 'normal');"),
        Test("one is normal", "assert(classify(1) === 'normal');"),
        Test("zero stays special", "assert(classify(0) === 'special');"),
    ],
    hints=[
        "The log shows every input is 'special' — the if branch never runs as intended.",
        "`if (flag = 0)` assigns 0 (falsy) and evaluates to 0, so the branch is always skipped.",
        "Compare n to 0 with ===: `if (n === 0) return 'special';` else 'normal'.",
    ],
    solution_explanation=(
        "A single = assigns instead of compares, so the condition's value was the "
        "assigned operand, not a comparison. Using n === 0 tests the actual value "
        "and labels only zero as special."),
))
