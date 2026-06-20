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
