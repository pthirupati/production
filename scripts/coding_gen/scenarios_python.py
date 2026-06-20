"""Python coding scenarios for the FixitLab browser IDE.

Every Scenario provides a BROKEN starter (fails hidden tests) and a REFERENCE
solution (passes). The generator proves both before writing YAML.
"""

from framework import Scenario, Test

S = []


def add(scn):
    S.append(scn)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: broken-code-fix (logic / runtime / off-by-one / perf / security)
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="py-fix-off-by-one-sum-range",
    title="Fix the Off-by-One in sum_range",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "sum_range(a, b) should return the sum of all integers from a to b "
        "INCLUSIVE, but it drops the final value because of an off-by-one error "
        "in the range bounds. Find and fix the boundary so both endpoints are "
        "counted."),
    objectives=[
        "Reproduce the wrong total for a small inclusive range",
        "Locate the off-by-one in the range() upper bound",
        "Make both endpoints inclusive so all tests pass",
    ],
    instructions=(
        "Fix sum_range(a, b) so it returns the sum of every integer from a to b, "
        "inclusive of both ends.\n"
        "  sum_range(1, 5) -> 15  (1+2+3+4+5)\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def sum_range(a, b):\n"
        "    total = 0\n"
        "    for i in range(a, b):   # bug: excludes b\n"
        "        total += i\n"
        "    return total\n"),
    reference=(
        "def sum_range(a, b):\n"
        "    total = 0\n"
        "    for i in range(a, b + 1):\n"
        "        total += i\n"
        "    return total\n"),
    visible_tests=[
        Test("1..5 inclusive", "assert sum_range(1, 5) == 15, sum_range(1, 5)"),
        Test("single value", "assert sum_range(7, 7) == 7, sum_range(7, 7)"),
    ],
    hidden_tests=[
        Test("zero to four", "assert sum_range(0, 4) == 10, sum_range(0, 4)"),
        Test("includes the endpoint", "assert sum_range(3, 6) == 18, sum_range(3, 6)"),
        Test("ten to ten", "assert sum_range(10, 10) == 10"),
        Test("larger range", "assert sum_range(1, 100) == 5050, sum_range(1, 100)"),
    ],
    hints=[
        "Print sum_range(1, 5): you'll get 10, not 15 — the last number is missing.",
        "range(a, b) stops BEFORE b. To include b you need range(a, b + 1).",
        "Change the loop to `for i in range(a, b + 1):` and re-run — every case passes.",
    ],
    solution_explanation=(
        "range(a, b) is half-open and never yields b, so the upper endpoint was "
        "dropped. Using range(a, b + 1) makes the range inclusive on both ends."),
))

add(Scenario(
    slug="py-fix-average-empty-divzero",
    title="Fix the ZeroDivisionError in average",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "average(nums) crashes with ZeroDivisionError when given an empty list "
        "because it divides by len(nums) without checking. Guard the empty case "
        "(return 0.0) while keeping the correct mean for non-empty lists."),
    objectives=[
        "Trigger the crash on an empty list",
        "Add a guard for the zero-length case",
        "Keep the correct average for non-empty input",
    ],
    instructions=(
        "Fix average(nums) so it returns the arithmetic mean, and returns 0.0 for "
        "an empty list instead of raising ZeroDivisionError.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def average(nums):\n"
        "    return sum(nums) / len(nums)\n"),
    reference=(
        "def average(nums):\n"
        "    if not nums:\n"
        "        return 0.0\n"
        "    return sum(nums) / len(nums)\n"),
    visible_tests=[
        Test("simple mean", "assert average([2, 4, 6]) == 4, average([2, 4, 6])"),
        Test("empty list is 0.0", "assert average([]) == 0.0, average([])"),
    ],
    hidden_tests=[
        Test("single element", "assert average([9]) == 9.0"),
        Test("floats", "assert abs(average([1.0, 2.0]) - 1.5) < 1e-9"),
        Test("negatives", "assert average([-2, 2]) == 0.0"),
        Test("empty does not raise", "r = average([]); assert isinstance(r, float)"),
    ],
    hints=[
        "Call average([]) — it raises ZeroDivisionError because len is 0.",
        "Check `if not nums:` at the top and return 0.0 before dividing.",
        "Guard the empty case, otherwise divide sum(nums) by len(nums) as before.",
    ],
    solution_explanation=(
        "Dividing by len(nums) explodes when the list is empty. An early "
        "`if not nums: return 0.0` guard fixes it without changing the normal path."),
))

add(Scenario(
    slug="py-fix-mutable-default-arg",
    title="Fix the Mutable Default Argument Bug",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "append_item(item, bucket=[]) uses a mutable default list, so the SAME "
        "list is shared across calls and items leak between unrelated calls. Fix "
        "it using the standard None sentinel idiom so each call starts fresh "
        "unless a bucket is explicitly passed."),
    objectives=[
        "Show that two separate calls share state",
        "Replace the mutable default with a None sentinel",
        "Confirm calls are independent but explicit buckets still work",
    ],
    instructions=(
        "Fix append_item so a fresh list is used when no bucket is given. Calling "
        "it twice with no bucket must NOT accumulate across calls.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def append_item(item, bucket=[]):\n"
        "    bucket.append(item)\n"
        "    return bucket\n"),
    reference=(
        "def append_item(item, bucket=None):\n"
        "    if bucket is None:\n"
        "        bucket = []\n"
        "    bucket.append(item)\n"
        "    return bucket\n"),
    visible_tests=[
        Test("appends to fresh list", "assert append_item(1) == [1]"),
        Test("explicit bucket used",
             "b = [0]\nassert append_item(5, b) == [0, 5]\nassert b == [0, 5]"),
    ],
    hidden_tests=[
        Test("calls are independent",
             "assert append_item(1) == [1]\nassert append_item(2) == [2]"),
        Test("repeated default calls do not accumulate",
             "for _ in range(3):\n    r = append_item('x')\n    assert r == ['x'], r"),
        Test("distinct list objects",
             "a = append_item('a')\nb = append_item('b')\nassert a is not b"),
    ],
    hints=[
        "Call append_item(1) then append_item(2). The second returns [1, 2] — the default list persisted.",
        "Default argument values are created ONCE at definition time; a default list is shared.",
        "Use `bucket=None`, then inside: `if bucket is None: bucket = []`.",
    ],
    solution_explanation=(
        "Default arguments are evaluated once when the function is defined, so a "
        "default list is shared across every call. The None-sentinel pattern "
        "allocates a new list per call while still honoring an explicit argument."),
))

add(Scenario(
    slug="py-fix-string-reverse-words",
    title="Fix reverse_words Token Order",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "reverse_words(s) should reverse the ORDER of words while keeping each "
        "word's characters intact, but it reverses the whole string character by "
        "character. Fix it so 'hello world' becomes 'world hello'."),
    objectives=[
        "See that characters are being reversed, not words",
        "Split on whitespace, reverse the list of words, re-join",
        "Preserve single spaces between words",
    ],
    instructions=(
        "Fix reverse_words(s) so it reverses the order of space-separated words.\n"
        "  reverse_words('hello world') -> 'world hello'\n"
        "Assume words are separated by single spaces.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def reverse_words(s):\n"
        "    return s[::-1]\n"),
    reference=(
        "def reverse_words(s):\n"
        "    return ' '.join(s.split(' ')[::-1])\n"),
    visible_tests=[
        Test("two words", "assert reverse_words('hello world') == 'world hello'"),
        Test("single word", "assert reverse_words('python') == 'python'"),
    ],
    hidden_tests=[
        Test("three words", "assert reverse_words('a b c') == 'c b a'"),
        Test("keeps characters intact",
             "assert reverse_words('abc def') == 'def abc'"),
        Test("empty string", "assert reverse_words('') == ''"),
    ],
    hints=[
        "reverse_words('hello world') currently gives 'dlrow olleh' — letters reversed, not words.",
        "Use s.split(' ') to get a list of words, then reverse the LIST.",
        "Return ' '.join(s.split(' ')[::-1]).",
    ],
    solution_explanation=(
        "s[::-1] reverses characters. Splitting into words, reversing that list, "
        "and re-joining with spaces reverses word order while keeping each word."),
))

add(Scenario(
    slug="py-fix-count-vowels-case",
    title="Fix Case-Insensitive Vowel Counting",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "count_vowels(s) is supposed to count vowels case-insensitively, but it "
        "only checks lowercase vowels, so uppercase vowels are missed. Fix it so "
        "'A' and 'a' both count."),
    objectives=[
        "Notice uppercase vowels are not counted",
        "Normalize case before checking membership",
        "Count a, e, i, o, u regardless of case",
    ],
    instructions=(
        "Fix count_vowels(s) to count a, e, i, o, u case-insensitively.\n"
        "  count_vowels('Apple') -> 2\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def count_vowels(s):\n"
        "    vowels = 'aeiou'\n"
        "    return sum(1 for ch in s if ch in vowels)\n"),
    reference=(
        "def count_vowels(s):\n"
        "    vowels = 'aeiou'\n"
        "    return sum(1 for ch in s.lower() if ch in vowels)\n"),
    visible_tests=[
        Test("lowercase word", "assert count_vowels('education') == 5"),
        Test("capitalized", "assert count_vowels('Apple') == 2, count_vowels('Apple')"),
    ],
    hidden_tests=[
        Test("all caps", "assert count_vowels('AEIOU') == 5"),
        Test("mixed case", "assert count_vowels('HeLLo WoRLD') == 3"),
        Test("no vowels", "assert count_vowels('rhythm') == 0"),
    ],
    hints=[
        "count_vowels('Apple') returns 1 — the capital A is ignored.",
        "Lowercase the string first, or include uppercase vowels in the set.",
        "Iterate over s.lower() so 'A' and 'a' are both matched.",
    ],
    solution_explanation=(
        "The vowel set only had lowercase letters. Lowercasing the input before "
        "checking membership makes the count case-insensitive."),
))

add(Scenario(
    slug="py-fix-fibonacci-base-case",
    title="Fix the Fibonacci Base Case",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "fib(n) returns the n-th Fibonacci number (0-indexed: 0,1,1,2,3,5,...), "
        "but the base cases are wrong so the whole sequence is shifted/incorrect. "
        "Fix the base cases so fib(0)=0 and fib(1)=1."),
    objectives=[
        "Check fib(0) and fib(1) against the definition",
        "Correct the base-case return values",
        "Verify the recursive/iterative sequence is right",
    ],
    instructions=(
        "Fix fib(n) so the 0-indexed sequence is 0, 1, 1, 2, 3, 5, 8, ...\n"
        "  fib(0)=0, fib(1)=1, fib(6)=8\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def fib(n):\n"
        "    if n == 0:\n"
        "        return 1\n"   # bug: should be 0
        "    if n == 1:\n"
        "        return 1\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n - 1):\n"
        "        a, b = b, a + b\n"
        "    return b\n"),
    reference=(
        "def fib(n):\n"
        "    if n == 0:\n"
        "        return 0\n"
        "    if n == 1:\n"
        "        return 1\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n - 1):\n"
        "        a, b = b, a + b\n"
        "    return b\n"),
    visible_tests=[
        Test("fib(0)", "assert fib(0) == 0, fib(0)"),
        Test("fib(1)", "assert fib(1) == 1, fib(1)"),
    ],
    hidden_tests=[
        Test("fib(2)", "assert fib(2) == 1, fib(2)"),
        Test("fib(6)", "assert fib(6) == 8, fib(6)"),
        Test("fib(10)", "assert fib(10) == 55, fib(10)"),
        Test("sequence prefix",
             "assert [fib(i) for i in range(7)] == [0, 1, 1, 2, 3, 5, 8]"),
    ],
    hints=[
        "fib(0) returns 1, but by definition it should be 0.",
        "Only the base case for n == 0 is wrong.",
        "Make `if n == 0: return 0`. The iterative part is already correct.",
    ],
    solution_explanation=(
        "fib(0) must be 0. The base case returned 1, shifting the indexing. "
        "Correcting it to return 0 fixes the whole sequence."),
))

add(Scenario(
    slug="py-fix-max-subarray-init",
    title="Fix max_subarray Initialization (Kadane)",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "max_subarray(nums) returns the largest contiguous-sum subarray total "
        "using Kadane's algorithm, but it initializes the best sum to 0, so for "
        "all-negative inputs it wrongly returns 0 instead of the largest (least "
        "negative) element. Fix the initialization."),
    objectives=[
        "Find the wrong answer on an all-negative array",
        "Initialize best/current from the first element, not 0",
        "Keep O(n) and pass all tests",
    ],
    instructions=(
        "Fix max_subarray(nums) so it returns the maximum contiguous subarray "
        "sum, correct even when every number is negative. Assume nums is "
        "non-empty.\n"
        "  max_subarray([-2,1,-3,4,-1,2,1,-5,4]) -> 6\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def max_subarray(nums):\n"
        "    best = 0\n"           # bug: forces non-negative result
        "    cur = 0\n"
        "    for x in nums:\n"
        "        cur = max(x, cur + x)\n"
        "        best = max(best, cur)\n"
        "    return best\n"),
    reference=(
        "def max_subarray(nums):\n"
        "    best = nums[0]\n"
        "    cur = nums[0]\n"
        "    for x in nums[1:]:\n"
        "        cur = max(x, cur + x)\n"
        "        best = max(best, cur)\n"
        "    return best\n"),
    visible_tests=[
        Test("classic example",
             "assert max_subarray([-2,1,-3,4,-1,2,1,-5,4]) == 6"),
        Test("all positive", "assert max_subarray([1, 2, 3]) == 6"),
    ],
    hidden_tests=[
        Test("all negative", "assert max_subarray([-3, -1, -2]) == -1, max_subarray([-3, -1, -2])"),
        Test("single negative", "assert max_subarray([-5]) == -5"),
        Test("single positive", "assert max_subarray([7]) == 7"),
        Test("mixed ending negative", "assert max_subarray([5, -2, 3, -10]) == 6"),
    ],
    hints=[
        "max_subarray([-3,-1,-2]) returns 0, but the answer should be -1 (the best single element).",
        "Starting best at 0 means an empty subarray is allowed, which is wrong here.",
        "Initialize best = cur = nums[0] and iterate from nums[1:].",
    ],
    solution_explanation=(
        "Seeding best/cur with 0 implicitly allows the empty subarray, giving 0 "
        "for all-negative inputs. Seeding from nums[0] makes Kadane correct."),
))

add(Scenario(
    slug="py-fix-binary-search-bounds",
    title="Fix the Binary Search Bounds",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "binary_search(arr, target) returns the index of target in a sorted list "
        "or -1, but the loop condition uses `lo < hi` with an inclusive `hi = "
        "len(arr) - 1`, so it never checks the last element — the final candidate "
        "is skipped. Fix the bound handling."),
    objectives=[
        "Find an input where the last element is missed",
        "Make the loop condition and bounds consistent",
        "Return the correct index, or -1 when absent",
    ],
    instructions=(
        "Fix binary_search(arr, target) so it returns the index of target in the "
        "sorted list arr, or -1 if not present. The current bounds skip the last "
        "element.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo < hi:                  # bug: should be lo <= hi\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        elif arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1\n"),
    reference=(
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        elif arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1\n"),
    visible_tests=[
        Test("found in middle", "assert binary_search([1,3,5,7,9], 5) == 2"),
        Test("absent", "assert binary_search([1,3,5,7,9], 4) == -1"),
    ],
    hidden_tests=[
        Test("last element", "assert binary_search([1,3,5,7,9], 9) == 4, binary_search([1,3,5,7,9], 9)"),
        Test("first element", "assert binary_search([1,3,5,7,9], 1) == 0"),
        Test("single element present", "assert binary_search([42], 42) == 0, binary_search([42], 42)"),
        Test("single element absent", "assert binary_search([42], 7) == -1"),
        Test("two elements last", "assert binary_search([1, 2], 2) == 1"),
    ],
    hints=[
        "Search for the last value (e.g. 9 in [1,3,5,7,9]) — it returns -1 even though it's present.",
        "With an inclusive hi = len-1, the loop must run while lo <= hi, not lo < hi.",
        "Change the condition to `while lo <= hi:`.",
    ],
    solution_explanation=(
        "When hi is inclusive (len-1), `lo < hi` exits before examining the final "
        "single-element window. Using `lo <= hi` checks it."),
))

add(Scenario(
    slug="py-fix-dedupe-preserve-order",
    title="Fix dedupe to Preserve Order",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "dedupe(items) should remove duplicates while preserving first-seen "
        "order, but it returns list(set(items)), which loses order and is "
        "non-deterministic. Fix it to keep the original order of first "
        "appearance."),
    objectives=[
        "See that the output order is wrong/unstable",
        "Track seen items while iterating in order",
        "Return uniques in first-seen order",
    ],
    instructions=(
        "Fix dedupe(items) so duplicates are removed but the order of first "
        "appearance is preserved.\n"
        "  dedupe([3, 1, 3, 2, 1]) -> [3, 1, 2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def dedupe(items):\n"
        "    return list(set(items))\n"),
    reference=(
        "def dedupe(items):\n"
        "    seen = set()\n"
        "    out = []\n"
        "    for it in items:\n"
        "        if it not in seen:\n"
        "            seen.add(it)\n"
        "            out.append(it)\n"
        "    return out\n"),
    visible_tests=[
        Test("preserves order", "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]"),
        Test("already unique", "assert dedupe([1, 2, 3]) == [1, 2, 3]"),
    ],
    hidden_tests=[
        Test("strings keep order", "assert dedupe(['b', 'a', 'b', 'c']) == ['b', 'a', 'c']"),
        Test("empty", "assert dedupe([]) == []"),
        Test("all same", "assert dedupe([5, 5, 5]) == [5]"),
        Test("order is exact",
             "assert dedupe([10, 20, 10, 30, 20, 40]) == [10, 20, 30, 40]"),
    ],
    hints=[
        "list(set(...)) discards ordering — dedupe([3,1,3,2,1]) may not start with 3.",
        "Iterate in order and remember which items you've already emitted.",
        "Keep a `seen` set and append to an output list only the first time you see each item.",
    ],
    solution_explanation=(
        "A set has no order. Iterating in sequence while tracking a `seen` set "
        "preserves first-appearance order deterministically."),
))

add(Scenario(
    slug="py-fix-merge-dicts-overwrite",
    title="Fix merge_dicts Precedence",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "merge_dicts(a, b) should return a new dict where keys from b OVERRIDE "
        "keys from a, but the merge order is reversed so a wins instead. Also it "
        "mutates `a` in place. Fix both: b takes precedence and inputs are not "
        "mutated."),
    objectives=[
        "Show b's values do not win and that a is mutated",
        "Build a new dict without touching the inputs",
        "Apply b after a so b overrides",
    ],
    instructions=(
        "Fix merge_dicts(a, b): return a NEW dict with all keys from both, where "
        "b's value wins on conflicts. Do not mutate a or b.\n"
        "  merge_dicts({'x':1,'y':2}, {'y':9}) -> {'x':1, 'y':9}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def merge_dicts(a, b):\n"
        "    a.update(b)        # mutates a\n"
        "    a.update(a)        # bug: re-applies a over b; and still mutates\n"
        "    return a\n"),
    reference=(
        "def merge_dicts(a, b):\n"
        "    out = dict(a)\n"
        "    out.update(b)\n"
        "    return out\n"),
    visible_tests=[
        Test("b overrides", "assert merge_dicts({'x':1,'y':2}, {'y':9}) == {'x':1,'y':9}"),
        Test("disjoint keys", "assert merge_dicts({'a':1}, {'b':2}) == {'a':1,'b':2}"),
    ],
    hidden_tests=[
        Test("does not mutate a",
             "a = {'k': 1}\nmerge_dicts(a, {'k': 2})\nassert a == {'k': 1}, a"),
        Test("does not mutate b",
             "b = {'k': 2}\nmerge_dicts({'k': 1}, b)\nassert b == {'k': 2}"),
        Test("b wins on multiple conflicts",
             "assert merge_dicts({'a':1,'b':1}, {'a':2,'b':2}) == {'a':2,'b':2}"),
        Test("empty b returns copy of a",
             "a = {'a': 1}\nr = merge_dicts(a, {})\nassert r == {'a':1} and r is not a"),
    ],
    hints=[
        "merge_dicts({'y':2}, {'y':9}) returns y=2 — a wins, and the original a is changed.",
        "Make a copy of a first, then update it with b so b takes precedence.",
        "Return `out = dict(a); out.update(b); return out`.",
    ],
    solution_explanation=(
        "Copying a into a new dict and updating with b means b overrides on "
        "conflicts and neither input is mutated."),
))

add(Scenario(
    slug="py-fix-is-palindrome-normalize",
    title="Fix is_palindrome Normalization",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "is_palindrome(s) should ignore case, spaces, and punctuation (so 'A man, "
        "a plan, a canal: Panama' is a palindrome), but it compares the raw "
        "string, so anything with spaces or capitals fails. Fix the "
        "normalization."),
    objectives=[
        "See that the raw comparison rejects valid palindromes",
        "Strip non-alphanumerics and lowercase before comparing",
        "Compare the cleaned string to its reverse",
    ],
    instructions=(
        "Fix is_palindrome(s) to ignore case and any non-alphanumeric characters.\n"
        "  is_palindrome('A man, a plan, a canal: Panama') -> True\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def is_palindrome(s):\n"
        "    return s == s[::-1]\n"),
    reference=(
        "def is_palindrome(s):\n"
        "    cleaned = ''.join(ch.lower() for ch in s if ch.isalnum())\n"
        "    return cleaned == cleaned[::-1]\n"),
    visible_tests=[
        Test("simple palindrome", "assert is_palindrome('racecar') is True"),
        Test("with punctuation",
             "assert is_palindrome('A man, a plan, a canal: Panama') is True"),
    ],
    hidden_tests=[
        Test("not a palindrome", "assert is_palindrome('hello') is False"),
        Test("case insensitive", "assert is_palindrome('Noon') is True"),
        Test("alphanumeric mix", "assert is_palindrome('Was it a car or a cat I saw?') is True"),
        Test("empty string is palindrome", "assert is_palindrome('') is True"),
    ],
    hints=[
        "is_palindrome('Noon') returns False because 'N' != 'n' in the raw compare.",
        "Keep only alphanumeric characters and lowercase them before comparing.",
        "cleaned = ''.join(c.lower() for c in s if c.isalnum()); return cleaned == cleaned[::-1].",
    ],
    solution_explanation=(
        "Comparing the raw string is sensitive to case and punctuation. Filtering "
        "to lowercase alphanumerics first yields the canonical comparison."),
))

add(Scenario(
    slug="py-fix-grade-boundaries",
    title="Fix the Grade Boundary Logic",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "letter_grade(score) maps a 0-100 score to A/B/C/D/F, but the boundary "
        "comparisons use `>` instead of `>=`, so exact cutoffs (90, 80, 70, 60) "
        "fall into the wrong bucket. Fix the boundaries so 90 is an A, 80 a B, "
        "and so on."),
    objectives=[
        "Test the exact cutoff scores",
        "Use >= at each threshold",
        "Return the correct letter for every score",
    ],
    instructions=(
        "Fix letter_grade(score): 90+ -> 'A', 80+ -> 'B', 70+ -> 'C', 60+ -> 'D', "
        "else 'F'. Cutoffs are INCLUSIVE.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def letter_grade(score):\n"
        "    if score > 90:\n"
        "        return 'A'\n"
        "    elif score > 80:\n"
        "        return 'B'\n"
        "    elif score > 70:\n"
        "        return 'C'\n"
        "    elif score > 60:\n"
        "        return 'D'\n"
        "    return 'F'\n"),
    reference=(
        "def letter_grade(score):\n"
        "    if score >= 90:\n"
        "        return 'A'\n"
        "    elif score >= 80:\n"
        "        return 'B'\n"
        "    elif score >= 70:\n"
        "        return 'C'\n"
        "    elif score >= 60:\n"
        "        return 'D'\n"
        "    return 'F'\n"),
    visible_tests=[
        Test("clear A", "assert letter_grade(95) == 'A'"),
        Test("exact 90 is A", "assert letter_grade(90) == 'A', letter_grade(90)"),
    ],
    hidden_tests=[
        Test("exact 80 is B", "assert letter_grade(80) == 'B', letter_grade(80)"),
        Test("exact 70 is C", "assert letter_grade(70) == 'C'"),
        Test("exact 60 is D", "assert letter_grade(60) == 'D'"),
        Test("fail", "assert letter_grade(59) == 'F'"),
        Test("mid B", "assert letter_grade(85) == 'B'"),
    ],
    hints=[
        "letter_grade(90) returns 'B', but 90 should be an 'A'.",
        "`score > 90` excludes exactly 90. The cutoffs are inclusive.",
        "Use >= at every threshold.",
    ],
    solution_explanation=(
        "Strict `>` excludes the exact cutoff value, bumping boundary scores down "
        "a grade. Using `>=` makes each threshold inclusive."),
))

add(Scenario(
    slug="py-fix-percentage-int-division",
    title="Fix Integer Division in percentage",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "percentage(part, whole) should return what percent `part` is of `whole` "
        "as a float, but it uses floor division (//) so it truncates to whole "
        "numbers (e.g. 1/3 -> 0.0). Fix it to return a true float percentage and "
        "guard whole == 0 (return 0.0)."),
    objectives=[
        "See the truncated 0.0 result",
        "Use true division",
        "Guard division by zero",
    ],
    instructions=(
        "Fix percentage(part, whole): return part/whole * 100 as a float. If "
        "whole is 0, return 0.0.\n"
        "  percentage(1, 4) -> 25.0\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def percentage(part, whole):\n"
        "    if whole == 0:\n"
        "        return 0.0\n"
        "    return part // whole * 100\n"),   # floor division
    reference=(
        "def percentage(part, whole):\n"
        "    if whole == 0:\n"
        "        return 0.0\n"
        "    return part / whole * 100\n"),
    visible_tests=[
        Test("quarter", "assert percentage(1, 4) == 25.0, percentage(1, 4)"),
        Test("zero whole", "assert percentage(5, 0) == 0.0"),
    ],
    hidden_tests=[
        Test("one third", "assert abs(percentage(1, 3) - 33.3333333) < 1e-3, percentage(1, 3)"),
        Test("full", "assert percentage(3, 3) == 100.0"),
        Test("returns float", "assert isinstance(percentage(1, 2), float)"),
        Test("half", "assert percentage(1, 2) == 50.0"),
    ],
    hints=[
        "percentage(1, 4) returns 0.0 because 1 // 4 == 0.",
        "// is floor division; use / for a real fraction.",
        "Return part / whole * 100.",
    ],
    solution_explanation=(
        "Floor division throws away the fractional part before multiplying, so "
        "small ratios collapse to 0. True division keeps the fraction."),
))

add(Scenario(
    slug="py-fix-flatten-shallow-vs-deep",
    title="Fix flatten to Handle Deep Nesting",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "flatten(nested) should fully flatten an arbitrarily nested list of "
        "integers, but it only flattens ONE level, leaving deeper lists intact. "
        "Make it recursive so any depth flattens to a single list, in order."),
    objectives=[
        "See nested sublists survive the shallow flatten",
        "Recurse into list elements",
        "Preserve left-to-right order at any depth",
    ],
    instructions=(
        "Fix flatten(nested) so it returns a single flat list of all integers at "
        "any nesting depth, in order.\n"
        "  flatten([1, [2, [3, [4]]], 5]) -> [1, 2, 3, 4, 5]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def flatten(nested):\n"
        "    out = []\n"
        "    for el in nested:\n"
        "        if isinstance(el, list):\n"
        "            out.extend(el)      # bug: only one level deep\n"
        "        else:\n"
        "            out.append(el)\n"
        "    return out\n"),
    reference=(
        "def flatten(nested):\n"
        "    out = []\n"
        "    for el in nested:\n"
        "        if isinstance(el, list):\n"
        "            out.extend(flatten(el))\n"
        "        else:\n"
        "            out.append(el)\n"
        "    return out\n"),
    visible_tests=[
        Test("one level", "assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]"),
        Test("deep example", "assert flatten([1, [2, [3, [4]]], 5]) == [1, 2, 3, 4, 5]"),
    ],
    hidden_tests=[
        Test("already flat", "assert flatten([1, 2, 3]) == [1, 2, 3]"),
        Test("very deep", "assert flatten([[[[[9]]]]]) == [9]"),
        Test("empty and nested empty", "assert flatten([[], [[], []]]) == []"),
        Test("order preserved", "assert flatten([1, [2, [3]], [4, [5, [6]]]]) == [1,2,3,4,5,6]"),
    ],
    hints=[
        "flatten([1, [2, [3]]]) returns [1, 2, [3]] — the inner list survives.",
        "extend(el) copies one level; you need to flatten el first.",
        "Recurse: out.extend(flatten(el)) when el is a list.",
    ],
    solution_explanation=(
        "Extending with the raw sublist only removes one level. Recursing with "
        "flatten(el) handles arbitrary depth."),
))

add(Scenario(
    slug="py-fix-rotate-list-modulo",
    title="Fix rotate_left for Large k",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "rotate_left(lst, k) rotates a list left by k positions, but it slices "
        "with a raw k, so when k is larger than len(lst) (or the list is empty) "
        "the result is wrong or crashes. Fix it by reducing k modulo the length "
        "and handling the empty list."),
    objectives=[
        "Try k larger than the list length",
        "Reduce k modulo len(lst)",
        "Handle empty list without ZeroDivisionError",
    ],
    instructions=(
        "Fix rotate_left(lst, k): return a new list rotated left by k. k may "
        "exceed len(lst); an empty list returns []. Do not mutate the input.\n"
        "  rotate_left([1,2,3,4,5], 2) -> [3,4,5,1,2]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def rotate_left(lst, k):\n"
        "    return lst[k:] + lst[:k]\n"),  # wrong when k > len; no guard
    reference=(
        "def rotate_left(lst, k):\n"
        "    if not lst:\n"
        "        return []\n"
        "    k %= len(lst)\n"
        "    return lst[k:] + lst[:k]\n"),
    visible_tests=[
        Test("rotate by 2", "assert rotate_left([1,2,3,4,5], 2) == [3,4,5,1,2]"),
        Test("rotate by 0", "assert rotate_left([1,2,3], 0) == [1,2,3]"),
    ],
    hidden_tests=[
        Test("k equals length", "assert rotate_left([1,2,3], 3) == [1,2,3], rotate_left([1,2,3], 3)"),
        Test("k greater than length", "assert rotate_left([1,2,3], 4) == [2,3,1], rotate_left([1,2,3], 4)"),
        Test("empty list", "assert rotate_left([], 5) == []"),
        Test("does not mutate",
             "a = [1,2,3]\nrotate_left(a, 1)\nassert a == [1,2,3]"),
    ],
    hints=[
        "rotate_left([1,2,3], 4) gives [] + [1,2,3] = [1,2,3], but should be [2,3,1].",
        "Rotating by len(lst) is the identity; reduce k modulo the length.",
        "Guard the empty list, then `k %= len(lst)` before slicing.",
    ],
    solution_explanation=(
        "A raw slice index beyond the list length produces wrong results; k % "
        "len(lst) normalizes it, and the empty-list guard avoids modulo by zero."),
))

add(Scenario(
    slug="py-fix-word-frequency-counter",
    title="Fix the Word Frequency Counter",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "word_count(text) should return a dict mapping each lowercased word to "
        "its frequency, but it never lowercases and splits on the default which "
        "leaves trailing punctuation attached, AND it overwrites counts to 1 "
        "instead of incrementing. Fix counting, case, and punctuation."),
    objectives=[
        "Notice counts cap at 1 and case/punctuation split words",
        "Lowercase and strip punctuation from each token",
        "Increment counts correctly",
    ],
    instructions=(
        "Fix word_count(text): return {word: count}. Words are lowercased and "
        "stripped of surrounding punctuation; split on whitespace.\n"
        "  word_count('Cat cat, dog.') -> {'cat': 2, 'dog': 1}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "import string\n"
        "\n"
        "def word_count(text):\n"
        "    counts = {}\n"
        "    for word in text.split():\n"
        "        counts[word] = 1     # bug: overwrites; no normalization\n"
        "    return counts\n"),
    reference=(
        "import string\n"
        "\n"
        "def word_count(text):\n"
        "    counts = {}\n"
        "    for raw in text.split():\n"
        "        word = raw.strip(string.punctuation).lower()\n"
        "        if not word:\n"
        "            continue\n"
        "        counts[word] = counts.get(word, 0) + 1\n"
        "    return counts\n"),
    visible_tests=[
        Test("counts and normalizes",
             "assert word_count('Cat cat, dog.') == {'cat': 2, 'dog': 1}, word_count('Cat cat, dog.')"),
        Test("single word", "assert word_count('hello') == {'hello': 1}"),
    ],
    hidden_tests=[
        Test("punctuation stripped",
             "assert word_count('hi! hi? hi.') == {'hi': 3}, word_count('hi! hi? hi.')"),
        Test("case folded",
             "assert word_count('The THE the') == {'the': 3}"),
        Test("empty text", "assert word_count('') == {}"),
        Test("mixed",
             "assert word_count('a a b A') == {'a': 3, 'b': 1}"),
    ],
    hints=[
        "word_count('cat cat') returns {'cat': 1} — it overwrites instead of adding.",
        "Use counts.get(word, 0) + 1 to accumulate; also lowercase and strip punctuation.",
        "raw.strip(string.punctuation).lower() normalizes each token before counting.",
    ],
    solution_explanation=(
        "Assigning 1 each time discards prior counts; counts.get(word,0)+1 "
        "accumulates. Stripping punctuation and lowercasing merges word variants."),
))

add(Scenario(
    slug="py-fix-sql-injection-param",
    title="Fix the SQL Injection in build_user_query",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "build_user_query(username) builds a SQL string by f-string "
        "interpolation, which is a SQL-injection vulnerability. Refactor it to "
        "return a (query, params) tuple that uses a parameter placeholder (?) so "
        "the username is bound, never concatenated."),
    objectives=[
        "Recognize the injection via string interpolation",
        "Return a parameterized query with a ? placeholder",
        "Pass the username as a bound parameter, not inline text",
    ],
    instructions=(
        "Refactor build_user_query(username) to return a tuple "
        "(sql, params) where sql uses a single ? placeholder and params is a "
        "tuple/list containing username. The raw username must NOT appear in the "
        "SQL string.\n"
        "Expected sql: \"SELECT * FROM users WHERE username = ?\"\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def build_user_query(username):\n"
        "    sql = \"SELECT * FROM users WHERE username = '\" + username + \"'\"\n"
        "    return sql\n"),
    reference=(
        "def build_user_query(username):\n"
        "    sql = \"SELECT * FROM users WHERE username = ?\"\n"
        "    return sql, (username,)\n"),
    visible_tests=[
        Test("returns sql and params tuple",
             "sql, params = build_user_query('alice')\n"
             "assert sql == 'SELECT * FROM users WHERE username = ?', sql\n"
             "assert list(params) == ['alice'], params"),
        Test("uses a placeholder",
             "sql, params = build_user_query('bob')\nassert '?' in sql"),
    ],
    hidden_tests=[
        Test("malicious input is not interpolated",
             "evil = \"x' OR '1'='1\"\n"
             "sql, params = build_user_query(evil)\n"
             "assert evil not in sql, 'username must not be concatenated into SQL'\n"
             "assert list(params) == [evil]"),
        Test("no inline quotes around a value",
             "sql, params = build_user_query('alice')\n"
             "assert \"'alice'\" not in sql"),
        Test("params carries the value",
             "sql, params = build_user_query('zoe')\nassert tuple(params) == ('zoe',)"),
    ],
    hints=[
        "Concatenating username into the SQL string lets an attacker inject `' OR '1'='1`.",
        "Use a ? placeholder in the SQL and return the value separately as params.",
        "return \"SELECT * FROM users WHERE username = ?\", (username,)",
    ],
    solution_explanation=(
        "String interpolation lets crafted input change the query. A "
        "parameterized query with a ? placeholder binds the value at execution "
        "time, so it is treated strictly as data."),
))

add(Scenario(
    slug="py-fix-n-plus-one-perf",
    title="Fix the Quadratic Membership Check",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "common_elements(a, b) returns items present in both lists, but it checks "
        "`x in b` for every x in a where b is a list — an O(n*m) scan that times "
        "out on large inputs. Convert b to a set for O(1) lookups so it scales."),
    objectives=[
        "Recognize the O(n*m) list membership pattern",
        "Use a set for constant-time lookups",
        "Pass the large-input performance test within the timeout",
    ],
    instructions=(
        "Fix common_elements(a, b): return the list of elements of a that also "
        "appear in b, in a's order, without duplicates. Make it efficient enough "
        "for large inputs.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    timeout=6,
    broken=(
        "def common_elements(a, b):\n"
        "    out = []\n"
        "    for x in a:\n"
        "        if x in b and x not in out:   # x in b is O(len(b)); x not in out is O(len(out))\n"
        "            out.append(x)\n"
        "    return out\n"),
    reference=(
        "def common_elements(a, b):\n"
        "    bset = set(b)\n"
        "    seen = set()\n"
        "    out = []\n"
        "    for x in a:\n"
        "        if x in bset and x not in seen:\n"
        "            seen.add(x)\n"
        "            out.append(x)\n"
        "    return out\n"),
    visible_tests=[
        Test("basic intersection", "assert common_elements([1,2,3,4], [2,4,6]) == [2,4]"),
        Test("no overlap", "assert common_elements([1,2], [3,4]) == []"),
    ],
    hidden_tests=[
        Test("preserves a's order and dedupes",
             "assert common_elements([3,1,3,2,1], [1,3]) == [3,1]"),
        Test("large input performance",
             "a = list(range(200000))\n"
             "b = list(range(100000, 300000))\n"
             "r = common_elements(a, b)\n"
             "assert r[0] == 100000 and r[-1] == 199999 and len(r) == 100000"),
        Test("empty inputs", "assert common_elements([], [1,2]) == [] and common_elements([1], []) == []"),
    ],
    hints=[
        "With b as a list, `x in b` scans b every time — that's O(len(a) * len(b)).",
        "Convert b to a set once; membership becomes O(1).",
        "Also track a `seen` set instead of `x not in out` (which is also linear).",
    ],
    solution_explanation=(
        "List membership is linear, so the nested scan is quadratic and times out "
        "on big inputs. Pre-building a set of b (and a `seen` set) makes each "
        "lookup O(1), so the whole pass is linear."),
))

add(Scenario(
    slug="py-fix-recursion-memoize-perf",
    title="Fix the Exponential Recursive Fibonacci",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "fib(n) is implemented with naive double recursion, which is exponential "
        "and times out for moderate n (e.g. n=40). Add memoization (or convert to "
        "iteration) so it computes large n quickly while staying correct."),
    objectives=[
        "Recognize the exponential branching of naive recursion",
        "Cache subresults or iterate",
        "Compute fib(40)+ within the timeout",
    ],
    instructions=(
        "Make fib(n) efficient (0-indexed: 0,1,1,2,3,5,...). It must compute "
        "fib(40) and beyond quickly. You may memoize or rewrite iteratively.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    timeout=6,
    broken=(
        "def fib(n):\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fib(n - 1) + fib(n - 2)   # exponential, times out for large n\n"),
    reference=(
        "from functools import lru_cache\n"
        "\n"
        "@lru_cache(maxsize=None)\n"
        "def fib(n):\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fib(n - 1) + fib(n - 2)\n"),
    visible_tests=[
        Test("small values", "assert fib(0) == 0 and fib(1) == 1 and fib(10) == 55"),
        Test("fib(20)", "assert fib(20) == 6765"),
    ],
    hidden_tests=[
        Test("fib(40) fast", "assert fib(40) == 102334155"),
        Test("fib(60)", "assert fib(60) == 1548008755920"),
        Test("sequence prefix", "assert [fib(i) for i in range(8)] == [0,1,1,2,3,5,8,13]"),
    ],
    hints=[
        "fib(40) recomputes the same subproblems billions of times — it hangs.",
        "Cache results by n so each value is computed once.",
        "Add @lru_cache(maxsize=None) above fib, or build it iteratively with a loop.",
    ],
    solution_explanation=(
        "Naive recursion recomputes overlapping subproblems, giving O(2^n). "
        "Memoizing with lru_cache (or iterating) makes it linear."),
))

add(Scenario(
    slug="py-fix-temperature-conversion",
    title="Fix the Celsius-to-Fahrenheit Formula",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "c_to_f(c) converts Celsius to Fahrenheit but uses the wrong formula "
        "(forgets the *9/5 factor), so every conversion is off. Fix it to the "
        "correct F = C * 9/5 + 32."),
    objectives=[
        "Compare known conversions (0C, 100C) to the output",
        "Apply the correct multiplier and offset",
        "Return a correct float",
    ],
    instructions=(
        "Fix c_to_f(c): Fahrenheit = c * 9/5 + 32.\n"
        "  c_to_f(0) -> 32.0, c_to_f(100) -> 212.0\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def c_to_f(c):\n"
        "    return c + 32      # bug: missing * 9/5\n"),
    reference=(
        "def c_to_f(c):\n"
        "    return c * 9 / 5 + 32\n"),
    visible_tests=[
        Test("freezing", "assert c_to_f(0) == 32.0"),
        Test("boiling", "assert c_to_f(100) == 212.0, c_to_f(100)"),
    ],
    hidden_tests=[
        Test("body temp", "assert abs(c_to_f(37) - 98.6) < 1e-9, c_to_f(37)"),
        Test("negative", "assert c_to_f(-40) == -40.0, c_to_f(-40)"),
        Test("twenty c", "assert c_to_f(20) == 68.0"),
    ],
    hints=[
        "c_to_f(100) returns 132, but boiling water is 212F.",
        "You scaled by nothing — Celsius degrees are larger than Fahrenheit degrees.",
        "Use c * 9 / 5 + 32.",
    ],
    solution_explanation=(
        "The conversion needs the 9/5 scaling factor before adding 32; omitting it "
        "only offsets the value."),
))

add(Scenario(
    slug="py-fix-clamp-bounds",
    title="Fix the clamp Min/Max Swap",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "clamp(x, lo, hi) should constrain x to the [lo, hi] range, but the min "
        "and max are swapped, so it returns the opposite of what you want. Fix the "
        "clamping so values below lo become lo and above hi become hi."),
    objectives=[
        "See out-of-range values clamped to the wrong bound",
        "Apply max(lo, ...) then min(hi, ...) correctly",
        "Leave in-range values unchanged",
    ],
    instructions=(
        "Fix clamp(x, lo, hi): if x < lo return lo, if x > hi return hi, else x.\n"
        "  clamp(15, 0, 10) -> 10, clamp(-3, 0, 10) -> 0\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def clamp(x, lo, hi):\n"
        "    return min(lo, max(hi, x))   # bounds swapped\n"),
    reference=(
        "def clamp(x, lo, hi):\n"
        "    return max(lo, min(hi, x))\n"),
    visible_tests=[
        Test("above range", "assert clamp(15, 0, 10) == 10, clamp(15, 0, 10)"),
        Test("below range", "assert clamp(-3, 0, 10) == 0, clamp(-3, 0, 10)"),
    ],
    hidden_tests=[
        Test("in range", "assert clamp(5, 0, 10) == 5"),
        Test("equals lower bound", "assert clamp(0, 0, 10) == 0"),
        Test("equals upper bound", "assert clamp(10, 0, 10) == 10"),
        Test("negative range", "assert clamp(-5, -10, -1) == -5"),
    ],
    hints=[
        "clamp(15, 0, 10) returns 0 instead of 10 — the bounds are reversed.",
        "To cap at hi use min(hi, x); to floor at lo use max(lo, ...).",
        "Return max(lo, min(hi, x)).",
    ],
    solution_explanation=(
        "Swapping min/lo and max/hi inverts the clamp. The correct nesting is "
        "max(lo, min(hi, x))."),
))

add(Scenario(
    slug="py-fix-chunk-list",
    title="Fix the chunk List Splitter",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "chunk(lst, size) splits a list into consecutive chunks of length size "
        "(last chunk may be shorter), but the step is hard-coded to 1 instead of "
        "size, producing overlapping windows. Fix the step so chunks are "
        "non-overlapping."),
    objectives=[
        "See overlapping windows instead of clean chunks",
        "Step the range by `size`",
        "Handle a final short chunk",
    ],
    instructions=(
        "Fix chunk(lst, size): return a list of consecutive sublists each of "
        "length size (the last may be shorter).\n"
        "  chunk([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def chunk(lst, size):\n"
        "    return [lst[i:i + size] for i in range(0, len(lst))]   # step should be size\n"),
    reference=(
        "def chunk(lst, size):\n"
        "    return [lst[i:i + size] for i in range(0, len(lst), size)]\n"),
    visible_tests=[
        Test("even split", "assert chunk([1,2,3,4], 2) == [[1,2],[3,4]]"),
        Test("uneven split", "assert chunk([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]"),
    ],
    hidden_tests=[
        Test("chunk size 3", "assert chunk([1,2,3,4,5,6,7], 3) == [[1,2,3],[4,5,6],[7]]"),
        Test("size larger than list", "assert chunk([1,2], 5) == [[1,2]]"),
        Test("empty list", "assert chunk([], 3) == []"),
        Test("size one", "assert chunk([1,2,3], 1) == [[1],[2],[3]]"),
    ],
    hints=[
        "chunk([1,2,3,4], 2) currently returns [[1,2],[2,3],[3,4],[4]] — windows overlap.",
        "The range must advance by `size`, not 1.",
        "Use range(0, len(lst), size).",
    ],
    solution_explanation=(
        "Stepping by 1 creates a sliding window. Stepping by `size` yields "
        "disjoint chunks, with slicing handling the short final chunk."),
))

add(Scenario(
    slug="py-fix-roman-numeral-subtractive",
    title="Fix Roman Numeral Subtractive Notation",
    language="python", kind="fix", difficulty="hard", scenario_type="fix",
    description=(
        "to_roman(n) converts 1..3999 to Roman numerals, but its value table omits "
        "the subtractive pairs (4=IV, 9=IX, 40=XL, ...), so it emits IIII instead "
        "of IV. Add the subtractive entries in the right order so output is "
        "canonical."),
    objectives=[
        "See non-canonical output like IIII or VIIII",
        "Add subtractive pairs (IV, IX, XL, XC, CD, CM) in descending order",
        "Produce canonical Roman numerals",
    ],
    instructions=(
        "Fix to_roman(n) for 1 <= n <= 3999 to produce canonical Roman numerals "
        "with subtractive notation.\n"
        "  to_roman(4) -> 'IV', to_roman(1994) -> 'MCMXCIV'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def to_roman(n):\n"
        "    table = [\n"
        "        (1000, 'M'), (500, 'D'), (100, 'C'),\n"
        "        (50, 'L'), (10, 'X'), (5, 'V'), (1, 'I'),\n"
        "    ]\n"
        "    out = []\n"
        "    for value, sym in table:\n"
        "        while n >= value:\n"
        "            out.append(sym)\n"
        "            n -= value\n"
        "    return ''.join(out)\n"),
    reference=(
        "def to_roman(n):\n"
        "    table = [\n"
        "        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),\n"
        "        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),\n"
        "        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),\n"
        "    ]\n"
        "    out = []\n"
        "    for value, sym in table:\n"
        "        while n >= value:\n"
        "            out.append(sym)\n"
        "            n -= value\n"
        "    return ''.join(out)\n"),
    visible_tests=[
        Test("four", "assert to_roman(4) == 'IV', to_roman(4)"),
        Test("nine", "assert to_roman(9) == 'IX', to_roman(9)"),
    ],
    hidden_tests=[
        Test("forty", "assert to_roman(40) == 'XL', to_roman(40)"),
        Test("ninety-nine", "assert to_roman(99) == 'XCIX', to_roman(99)"),
        Test("1994", "assert to_roman(1994) == 'MCMXCIV', to_roman(1994)"),
        Test("3888 (long)", "assert to_roman(3888) == 'MMMDCCCLXXXVIII'"),
        Test("plain values still work", "assert to_roman(3) == 'III' and to_roman(2000) == 'MM'"),
    ],
    hints=[
        "to_roman(4) returns 'IIII' instead of 'IV' — subtractive pairs are missing.",
        "Insert 900/CM, 400/CD, 90/XC, 40/XL, 9/IX, 4/IV into the value table.",
        "Keep the table in strictly descending value order so the greedy loop stays canonical.",
    ],
    solution_explanation=(
        "Greedy conversion only produces canonical numerals when the subtractive "
        "pairs are present as table entries in descending order."),
))

add(Scenario(
    slug="py-fix-parse-int-base-error",
    title="Fix the Number Parsing Crash",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "safe_int(s, default) should parse a string to an int, returning `default` "
        "when the string is not a valid integer, but it lets ValueError propagate "
        "and crash. Wrap the parse so invalid input falls back to default."),
    objectives=[
        "Trigger the ValueError on bad input",
        "Catch the conversion error",
        "Return the provided default on failure",
    ],
    instructions=(
        "Fix safe_int(s, default): return int(s) when s parses, otherwise return "
        "default. Never raise.\n"
        "  safe_int('42', 0) -> 42, safe_int('abc', -1) -> -1\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def safe_int(s, default):\n"
        "    return int(s)        # raises ValueError on bad input\n"),
    reference=(
        "def safe_int(s, default):\n"
        "    try:\n"
        "        return int(s)\n"
        "    except (ValueError, TypeError):\n"
        "        return default\n"),
    visible_tests=[
        Test("valid number", "assert safe_int('42', 0) == 42"),
        Test("invalid falls back", "assert safe_int('abc', -1) == -1"),
    ],
    hidden_tests=[
        Test("empty string", "assert safe_int('', 99) == 99"),
        Test("float string falls back", "assert safe_int('3.14', 0) == 0"),
        Test("negative number", "assert safe_int('-7', 0) == -7"),
        Test("None falls back", "assert safe_int(None, 5) == 5"),
    ],
    hints=[
        "safe_int('abc', -1) raises ValueError instead of returning -1.",
        "Wrap int(s) in try/except.",
        "Catch ValueError (and TypeError for None) and return default.",
    ],
    solution_explanation=(
        "int() raises on non-numeric input. Catching ValueError/TypeError and "
        "returning the default makes parsing safe."),
))

add(Scenario(
    slug="py-fix-group-by-key",
    title="Fix group_by Aggregation",
    language="python", kind="fix", difficulty="medium", scenario_type="fix",
    description=(
        "group_by(items, key) should group items into a dict of {key_value: "
        "[items...]}, but it assigns the latest item instead of appending, so each "
        "group keeps only one item. Fix it to accumulate all items per key."),
    objectives=[
        "See groups collapse to a single item",
        "Append to a per-key list",
        "Preserve item order within each group",
    ],
    instructions=(
        "Fix group_by(items, key): return {key(item): [items with that key], ...} "
        "preserving order. key is a function.\n"
        "  group_by([1,2,3,4], lambda x: x % 2) -> {1: [1,3], 0: [2,4]}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def group_by(items, key):\n"
        "    groups = {}\n"
        "    for it in items:\n"
        "        groups[key(it)] = it      # bug: overwrites the group\n"
        "    return groups\n"),
    reference=(
        "def group_by(items, key):\n"
        "    groups = {}\n"
        "    for it in items:\n"
        "        groups.setdefault(key(it), []).append(it)\n"
        "    return groups\n"),
    visible_tests=[
        Test("parity grouping",
             "g = group_by([1,2,3,4], lambda x: x % 2)\n"
             "assert g == {1: [1,3], 0: [2,4]}, g"),
        Test("single group",
             "assert group_by([2,4,6], lambda x: 'even') == {'even': [2,4,6]}"),
    ],
    hidden_tests=[
        Test("by length",
             "g = group_by(['a','bb','cc','d'], len)\n"
             "assert g == {1: ['a','d'], 2: ['bb','cc']}, g"),
        Test("empty input", "assert group_by([], lambda x: x) == {}"),
        Test("order within group",
             "g = group_by([10,20,11,21], lambda x: x % 10)\n"
             "assert g[0] == [10,20] and g[1] == [11,21]"),
    ],
    hints=[
        "group_by([1,3], lambda x: x%2) returns {1: 3} — only the last item is kept.",
        "Each key should map to a LIST you append to.",
        "Use groups.setdefault(key(it), []).append(it).",
    ],
    solution_explanation=(
        "Assigning the item replaces the group each time. setdefault(key, []) "
        "ensures a list exists, and append accumulates all members in order."),
))

add(Scenario(
    slug="py-fix-running-total-accumulate",
    title="Fix the Running Total (Prefix Sums)",
    language="python", kind="fix", difficulty="easy", scenario_type="fix",
    description=(
        "running_total(nums) should return a list of cumulative sums (prefix "
        "sums), but it resets the accumulator each iteration so it just echoes the "
        "inputs. Fix it so each element is the sum of all elements up to that "
        "index."),
    objectives=[
        "See the output equals the input (no accumulation)",
        "Keep a persistent running sum",
        "Emit the cumulative value at each step",
    ],
    instructions=(
        "Fix running_total(nums): return cumulative sums.\n"
        "  running_total([1,2,3,4]) -> [1,3,6,10]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def running_total(nums):\n"
        "    out = []\n"
        "    for n in nums:\n"
        "        total = 0        # bug: reset every iteration\n"
        "        total += n\n"
        "        out.append(total)\n"
        "    return out\n"),
    reference=(
        "def running_total(nums):\n"
        "    out = []\n"
        "    total = 0\n"
        "    for n in nums:\n"
        "        total += n\n"
        "        out.append(total)\n"
        "    return out\n"),
    visible_tests=[
        Test("basic", "assert running_total([1,2,3,4]) == [1,3,6,10]"),
        Test("single", "assert running_total([5]) == [5]"),
    ],
    hidden_tests=[
        Test("with negatives", "assert running_total([1,-1,2,-2]) == [1,0,2,0]"),
        Test("empty", "assert running_total([]) == []"),
        Test("zeros", "assert running_total([0,0,0]) == [0,0,0]"),
        Test("longer", "assert running_total([2,2,2,2,2]) == [2,4,6,8,10]"),
    ],
    hints=[
        "running_total([1,2,3]) returns [1,2,3] — it isn't accumulating.",
        "The `total = 0` line is inside the loop, so it resets every step.",
        "Move the accumulator initialization OUTSIDE the loop.",
    ],
    solution_explanation=(
        "Re-initializing total inside the loop discards prior sums. Initializing "
        "it once before the loop accumulates correctly."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: implement-missing (functions / classes / business logic / validation)
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="py-impl-fizzbuzz",
    title="Implement FizzBuzz",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement fizzbuzz(n) returning a list for 1..n: 'Fizz' for multiples of "
        "3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of both, otherwise "
        "the number as a string. The stub returns nothing, so the tests fail."),
    objectives=[
        "Read the FizzBuzz contract from the tests",
        "Check the combined 3-and-5 case first",
        "Return the correct list of strings for 1..n",
    ],
    instructions=(
        "Implement fizzbuzz(n) -> list for 1..n. multiples of 3 -> 'Fizz', of 5 -> "
        "'Buzz', of both -> 'FizzBuzz', else str(number).\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def fizzbuzz(n):\n"
        "    # TODO: return the FizzBuzz list for 1..n\n"
        "    pass\n"),
    reference=(
        "def fizzbuzz(n):\n"
        "    out = []\n"
        "    for i in range(1, n + 1):\n"
        "        if i % 15 == 0:\n"
        "            out.append('FizzBuzz')\n"
        "        elif i % 3 == 0:\n"
        "            out.append('Fizz')\n"
        "        elif i % 5 == 0:\n"
        "            out.append('Buzz')\n"
        "        else:\n"
        "            out.append(str(i))\n"
        "    return out\n"),
    visible_tests=[
        Test("length n", "out = fizzbuzz(5)\nassert len(out) == 5"),
        Test("plain numbers", "assert fizzbuzz(2) == ['1', '2']"),
    ],
    hidden_tests=[
        Test("fizz and buzz",
             "out = fizzbuzz(5)\nassert out[2] == 'Fizz' and out[4] == 'Buzz'"),
        Test("fizzbuzz at 15", "assert fizzbuzz(15)[14] == 'FizzBuzz'"),
        Test("full prefix",
             "assert fizzbuzz(16) == ['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz','16']"),
    ],
    hints=[
        "The tests want a list of strings, with numbers stringified.",
        "Check the multiple-of-15 case before the 3 and 5 cases.",
        "if i%15==0:'FizzBuzz' elif i%3==0:'Fizz' elif i%5==0:'Buzz' else str(i).",
    ],
    solution_explanation=(
        "Iterating 1..n and checking the combined %15 case first yields canonical "
        "FizzBuzz output."),
))

add(Scenario(
    slug="py-impl-is-prime",
    title="Implement is_prime",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement is_prime(n): True if n is a prime number, False otherwise. "
        "Handle n < 2 (not prime) and be efficient enough to test moderately large "
        "primes (trial division up to sqrt(n) is fine)."),
    objectives=[
        "Treat n < 2 as not prime",
        "Test divisibility up to sqrt(n)",
        "Return correct booleans including edge cases",
    ],
    instructions=(
        "Implement is_prime(n) -> bool. 0 and 1 are not prime. 2 is prime.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def is_prime(n):\n"
        "    # TODO: return True iff n is prime\n"
        "    pass\n"),
    reference=(
        "def is_prime(n):\n"
        "    if n < 2:\n"
        "        return False\n"
        "    if n < 4:\n"
        "        return True\n"
        "    if n % 2 == 0:\n"
        "        return False\n"
        "    i = 3\n"
        "    while i * i <= n:\n"
        "        if n % i == 0:\n"
        "            return False\n"
        "        i += 2\n"
        "    return True\n"),
    visible_tests=[
        Test("small primes", "assert is_prime(2) and is_prime(3) and is_prime(5)"),
        Test("small composites", "assert not is_prime(4) and not is_prime(9)"),
    ],
    hidden_tests=[
        Test("zero and one", "assert not is_prime(0) and not is_prime(1)"),
        Test("larger prime", "assert is_prime(97)"),
        Test("larger composite", "assert not is_prime(100)"),
        Test("big prime fast", "assert is_prime(104729)"),
        Test("returns bool", "assert is_prime(7) is True and is_prime(8) is False"),
    ],
    hints=[
        "Numbers below 2 are not prime; return False early.",
        "You only need to test divisors up to the square root of n.",
        "Loop i from 3 while i*i <= n stepping by 2 (after handling even numbers).",
    ],
    solution_explanation=(
        "After handling n<2 and even numbers, testing odd divisors up to sqrt(n) "
        "is sufficient and fast."),
))

add(Scenario(
    slug="py-impl-validate-email",
    title="Implement a Basic Email Validator",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement is_valid_email(s): return True only when s looks like a basic "
        "email — exactly one '@', a non-empty local part, and a domain that "
        "contains a dot with non-empty labels on both sides. No spaces allowed. "
        "This is intentionally a simple ruleset defined by the tests."),
    objectives=[
        "Require exactly one @ with non-empty local part",
        "Require a dotted domain with non-empty labels",
        "Reject spaces and malformed addresses",
    ],
    instructions=(
        "Implement is_valid_email(s) -> bool with these rules: exactly one '@'; "
        "local part non-empty; domain has at least one '.', with no empty label "
        "(no leading/trailing dot, no '..'); no whitespace anywhere.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def is_valid_email(s):\n"
        "    # TODO: validate per the rules in the brief/tests\n"
        "    pass\n"),
    reference=(
        "def is_valid_email(s):\n"
        "    if not isinstance(s, str) or any(c.isspace() for c in s):\n"
        "        return False\n"
        "    if s.count('@') != 1:\n"
        "        return False\n"
        "    local, domain = s.split('@')\n"
        "    if not local or not domain:\n"
        "        return False\n"
        "    if '.' not in domain:\n"
        "        return False\n"
        "    labels = domain.split('.')\n"
        "    if any(label == '' for label in labels):\n"
        "        return False\n"
        "    return True\n"),
    visible_tests=[
        Test("valid simple", "assert is_valid_email('a@b.com') is True"),
        Test("missing at", "assert is_valid_email('ab.com') is False"),
    ],
    hidden_tests=[
        Test("no dot in domain", "assert is_valid_email('a@b') is False"),
        Test("two ats", "assert is_valid_email('a@@b.com') is False"),
        Test("empty local", "assert is_valid_email('@b.com') is False"),
        Test("trailing dot domain", "assert is_valid_email('a@b.') is False"),
        Test("double dot", "assert is_valid_email('a@b..com') is False"),
        Test("has space", "assert is_valid_email('a b@c.com') is False"),
        Test("subdomain valid", "assert is_valid_email('me@mail.example.com') is True"),
    ],
    hints=[
        "Start by rejecting any whitespace and requiring exactly one '@'.",
        "Split into local and domain; both must be non-empty and the domain needs a dot.",
        "Split the domain on '.' and reject any empty label (catches leading/trailing/double dots).",
    ],
    solution_explanation=(
        "The simple ruleset is: one @, non-empty local, dotted domain with no "
        "empty labels, and no whitespace. Splitting on @ and '.' checks each rule."),
))

add(Scenario(
    slug="py-impl-stack-class",
    title="Implement a Stack Class",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement a Stack class with push(x), pop(), peek(), is_empty(), and "
        "__len__. pop/peek on an empty stack should raise IndexError. The stub is "
        "empty so the tests fail."),
    objectives=[
        "Back the stack with a list",
        "Implement LIFO push/pop/peek",
        "Raise IndexError on empty pop/peek and support len()",
    ],
    instructions=(
        "Implement class Stack with: push(x), pop() -> last item, peek() -> last "
        "item without removing, is_empty() -> bool, and len(stack). pop/peek on "
        "empty must raise IndexError.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "class Stack:\n"
        "    # TODO: implement push, pop, peek, is_empty, __len__\n"
        "    pass\n"),
    reference=(
        "class Stack:\n"
        "    def __init__(self):\n"
        "        self._items = []\n"
        "    def push(self, x):\n"
        "        self._items.append(x)\n"
        "    def pop(self):\n"
        "        if not self._items:\n"
        "            raise IndexError('pop from empty stack')\n"
        "        return self._items.pop()\n"
        "    def peek(self):\n"
        "        if not self._items:\n"
        "            raise IndexError('peek from empty stack')\n"
        "        return self._items[-1]\n"
        "    def is_empty(self):\n"
        "        return not self._items\n"
        "    def __len__(self):\n"
        "        return len(self._items)\n"),
    visible_tests=[
        Test("push and pop",
             "s = Stack()\ns.push(1)\ns.push(2)\nassert s.pop() == 2 and s.pop() == 1"),
        Test("starts empty", "s = Stack()\nassert s.is_empty() and len(s) == 0"),
    ],
    hidden_tests=[
        Test("peek does not remove",
             "s = Stack()\ns.push(7)\nassert s.peek() == 7 and len(s) == 1"),
        Test("len tracks size",
             "s = Stack()\nfor i in range(3):\n    s.push(i)\nassert len(s) == 3"),
        Test("pop empty raises",
             "s = Stack()\ntry:\n    s.pop()\n    assert False, 'expected IndexError'\nexcept IndexError:\n    pass"),
        Test("peek empty raises",
             "s = Stack()\ntry:\n    s.peek()\n    assert False\nexcept IndexError:\n    pass"),
        Test("LIFO order",
             "s = Stack()\nfor x in [1,2,3]:\n    s.push(x)\nassert [s.pop(), s.pop(), s.pop()] == [3,2,1]"),
    ],
    hints=[
        "Use a Python list as the backing store; the end of the list is the top.",
        "push -> append, pop -> list.pop(), peek -> items[-1].",
        "Guard pop/peek when empty and raise IndexError; define __len__ to return the size.",
    ],
    solution_explanation=(
        "A list models a stack: append/pop at the end give LIFO. Guarding the "
        "empty case raises IndexError, and __len__ exposes the size."),
))

add(Scenario(
    slug="py-impl-lru-cache-class",
    title="Implement an LRU Cache",
    language="python", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement an LRUCache(capacity) with get(key) and put(key, value). get "
        "returns the value or -1 if absent and marks the key most-recently-used. "
        "put inserts/updates and evicts the least-recently-used key when capacity "
        "is exceeded. The stub is empty so the tests fail."),
    objectives=[
        "Track recency of access for keys",
        "Evict the least-recently-used entry on overflow",
        "Make get/put update recency correctly",
    ],
    instructions=(
        "Implement class LRUCache(capacity) with get(key)->value or -1, and "
        "put(key, value). On overflow evict the least-recently-used key. Both get "
        "and put count as 'use'.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "class LRUCache:\n"
        "    def __init__(self, capacity):\n"
        "        # TODO\n"
        "        pass\n"
        "    def get(self, key):\n"
        "        # TODO\n"
        "        pass\n"
        "    def put(self, key, value):\n"
        "        # TODO\n"
        "        pass\n"),
    reference=(
        "from collections import OrderedDict\n"
        "\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity):\n"
        "        self.capacity = capacity\n"
        "        self._d = OrderedDict()\n"
        "    def get(self, key):\n"
        "        if key not in self._d:\n"
        "            return -1\n"
        "        self._d.move_to_end(key)\n"
        "        return self._d[key]\n"
        "    def put(self, key, value):\n"
        "        if key in self._d:\n"
        "            self._d.move_to_end(key)\n"
        "        self._d[key] = value\n"
        "        if len(self._d) > self.capacity:\n"
        "            self._d.popitem(last=False)\n"),
    visible_tests=[
        Test("basic get/put",
             "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nassert c.get(1) == 1"),
        Test("miss returns -1", "c = LRUCache(2)\nassert c.get(99) == -1"),
    ],
    hidden_tests=[
        Test("evicts least recently used",
             "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(3, 3)\n"
             "assert c.get(1) == -1 and c.get(2) == 2 and c.get(3) == 3"),
        Test("get refreshes recency",
             "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.get(1)\nc.put(3, 3)\n"
             "assert c.get(2) == -1 and c.get(1) == 1 and c.get(3) == 3"),
        Test("update existing keeps it fresh",
             "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(1, 10)\nc.put(3, 3)\n"
             "assert c.get(2) == -1 and c.get(1) == 10"),
        Test("capacity one",
             "c = LRUCache(1)\nc.put(1, 1)\nc.put(2, 2)\nassert c.get(1) == -1 and c.get(2) == 2"),
    ],
    hints=[
        "You need to know which key was used least recently — order matters.",
        "collections.OrderedDict supports move_to_end and popitem(last=False).",
        "On get/put, move the key to the end; after put, if over capacity pop the first item.",
    ],
    solution_explanation=(
        "An OrderedDict maintains insertion/use order. Moving a key to the end on "
        "access marks it most-recent; popitem(last=False) evicts the LRU entry."),
))

add(Scenario(
    slug="py-impl-merge-intervals",
    title="Implement Merge Intervals",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement merge_intervals(intervals): given a list of [start, end] pairs, "
        "return the list of merged, non-overlapping intervals sorted by start. "
        "Touching intervals ([1,2],[2,3]) merge. The stub is empty so tests fail."),
    objectives=[
        "Sort intervals by start",
        "Merge overlapping or touching intervals",
        "Return sorted, non-overlapping intervals",
    ],
    instructions=(
        "Implement merge_intervals(intervals) -> merged list. Intervals that "
        "overlap OR touch are merged.\n"
        "  merge_intervals([[1,3],[2,6],[8,10],[15,18]]) -> [[1,6],[8,10],[15,18]]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def merge_intervals(intervals):\n"
        "    # TODO: return merged, sorted, non-overlapping intervals\n"
        "    pass\n"),
    reference=(
        "def merge_intervals(intervals):\n"
        "    if not intervals:\n"
        "        return []\n"
        "    ordered = sorted(intervals, key=lambda iv: iv[0])\n"
        "    merged = [list(ordered[0])]\n"
        "    for start, end in ordered[1:]:\n"
        "        if start <= merged[-1][1]:\n"
        "            merged[-1][1] = max(merged[-1][1], end)\n"
        "        else:\n"
        "            merged.append([start, end])\n"
        "    return merged\n"),
    visible_tests=[
        Test("classic example",
             "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]"),
        Test("no overlap", "assert merge_intervals([[1,2],[3,4]]) == [[1,2],[3,4]]"),
    ],
    hidden_tests=[
        Test("touching merges", "assert merge_intervals([[1,4],[4,5]]) == [[1,5]]"),
        Test("unsorted input",
             "assert merge_intervals([[8,10],[1,3],[2,6]]) == [[1,6],[8,10]]"),
        Test("nested interval", "assert merge_intervals([[1,10],[2,3],[4,5]]) == [[1,10]]"),
        Test("empty", "assert merge_intervals([]) == []"),
        Test("single", "assert merge_intervals([[5,7]]) == [[5,7]]"),
    ],
    hints=[
        "Sort by start first so overlaps are adjacent.",
        "Keep a list of merged intervals; compare each new start to the last merged end.",
        "If start <= last_end, extend the end to max(last_end, end); else append a new interval.",
    ],
    solution_explanation=(
        "Sorting by start lets a single left-to-right pass merge any interval "
        "whose start is within the current merged end, extending it as needed."),
))

add(Scenario(
    slug="py-impl-anagram-groups",
    title="Implement Group Anagrams",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement group_anagrams(words): group words that are anagrams of each "
        "other. Return a list of groups; within each group preserve input order. "
        "The order of the groups themselves should follow first appearance. The "
        "stub is empty so tests fail."),
    objectives=[
        "Compute an order-independent key per word (sorted letters)",
        "Bucket words by that key",
        "Preserve first-appearance order of groups and members",
    ],
    instructions=(
        "Implement group_anagrams(words) -> list of groups (lists). Words that are "
        "anagrams go together. Group order = first appearance; member order = "
        "input order.\n"
        "  group_anagrams(['eat','tea','tan','ate','nat','bat']) -> "
        "[['eat','tea','ate'], ['tan','nat'], ['bat']]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def group_anagrams(words):\n"
        "    # TODO: group anagrams together\n"
        "    pass\n"),
    reference=(
        "def group_anagrams(words):\n"
        "    groups = {}\n"
        "    order = []\n"
        "    for w in words:\n"
        "        key = ''.join(sorted(w))\n"
        "        if key not in groups:\n"
        "            groups[key] = []\n"
        "            order.append(key)\n"
        "        groups[key].append(w)\n"
        "    return [groups[k] for k in order]\n"),
    visible_tests=[
        Test("classic example",
             "assert group_anagrams(['eat','tea','tan','ate','nat','bat']) == "
             "[['eat','tea','ate'], ['tan','nat'], ['bat']]"),
        Test("no anagrams",
             "assert group_anagrams(['abc','def']) == [['abc'], ['def']]"),
    ],
    hidden_tests=[
        Test("all anagrams",
             "assert group_anagrams(['abc','cab','bca']) == [['abc','cab','bca']]"),
        Test("empty list", "assert group_anagrams([]) == []"),
        Test("single word", "assert group_anagrams(['x']) == [['x']]"),
        Test("member order preserved",
             "assert group_anagrams(['ba','ab','ba']) == [['ba','ab','ba']]"),
    ],
    hints=[
        "Two words are anagrams iff their sorted letters are equal.",
        "Use the sorted-letters string as a dict key to bucket words.",
        "Track first-seen key order separately so the output group order is stable.",
    ],
    solution_explanation=(
        "Sorting each word's letters gives a canonical anagram key. Bucketing by "
        "that key, while remembering first-seen order, groups them deterministically."),
))

add(Scenario(
    slug="py-impl-roman-to-int",
    title="Implement Roman to Integer",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement from_roman(s): convert a valid Roman numeral string to its "
        "integer value, honoring subtractive notation (IV=4, IX=9, etc). The stub "
        "is empty so tests fail."),
    objectives=[
        "Map Roman symbols to values",
        "Subtract when a smaller symbol precedes a larger one",
        "Sum to the correct integer",
    ],
    instructions=(
        "Implement from_roman(s) -> int for a valid Roman numeral.\n"
        "  from_roman('IV') -> 4, from_roman('MCMXCIV') -> 1994\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def from_roman(s):\n"
        "    # TODO: convert a Roman numeral to an integer\n"
        "    pass\n"),
    reference=(
        "def from_roman(s):\n"
        "    vals = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n"
        "    total = 0\n"
        "    prev = 0\n"
        "    for ch in reversed(s):\n"
        "        v = vals[ch]\n"
        "        if v < prev:\n"
        "            total -= v\n"
        "        else:\n"
        "            total += v\n"
        "            prev = v\n"
        "    return total\n"),
    visible_tests=[
        Test("three", "assert from_roman('III') == 3"),
        Test("four", "assert from_roman('IV') == 4, from_roman('IV')"),
    ],
    hidden_tests=[
        Test("nine", "assert from_roman('IX') == 9"),
        Test("58", "assert from_roman('LVIII') == 58"),
        Test("1994", "assert from_roman('MCMXCIV') == 1994, from_roman('MCMXCIV')"),
        Test("3888", "assert from_roman('MMMDCCCLXXXVIII') == 3888"),
    ],
    hints=[
        "Map each symbol to a value: I=1, V=5, X=10, L=50, C=100, D=500, M=1000.",
        "A smaller value before a larger one (like IV) means subtract.",
        "Scan right-to-left: subtract when the current value is less than the last larger one.",
    ],
    solution_explanation=(
        "Scanning right to left and subtracting any symbol smaller than the "
        "running maximum cleanly handles subtractive notation."),
))

add(Scenario(
    slug="py-impl-valid-parentheses",
    title="Implement Valid Parentheses",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement is_balanced(s): return True if every bracket in s — (), [], {} "
        "— is correctly opened and closed in the right order, False otherwise. "
        "Other characters are ignored. The stub is empty so tests fail."),
    objectives=[
        "Use a stack to match opening brackets",
        "Verify each closer matches the most recent opener",
        "Ensure nothing is left unclosed",
    ],
    instructions=(
        "Implement is_balanced(s) -> bool for the brackets (), [], {} (ignore "
        "other chars).\n"
        "  is_balanced('([]{})') -> True, is_balanced('(]') -> False\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def is_balanced(s):\n"
        "    # TODO: return True iff brackets are balanced\n"
        "    pass\n"),
    reference=(
        "def is_balanced(s):\n"
        "    pairs = {')': '(', ']': '[', '}': '{'}\n"
        "    openers = set(pairs.values())\n"
        "    stack = []\n"
        "    for ch in s:\n"
        "        if ch in openers:\n"
        "            stack.append(ch)\n"
        "        elif ch in pairs:\n"
        "            if not stack or stack.pop() != pairs[ch]:\n"
        "                return False\n"
        "    return not stack\n"),
    visible_tests=[
        Test("balanced mixed", "assert is_balanced('([]{})') is True"),
        Test("mismatch", "assert is_balanced('(]') is False"),
    ],
    hidden_tests=[
        Test("empty is balanced", "assert is_balanced('') is True"),
        Test("unclosed", "assert is_balanced('(((') is False"),
        Test("extra close", "assert is_balanced('())') is False"),
        Test("ignores other chars", "assert is_balanced('a(b)c[d]') is True"),
        Test("wrong nesting", "assert is_balanced('([)]') is False"),
    ],
    hints=[
        "Push every opening bracket onto a stack.",
        "On a closing bracket, the top of the stack must be its matching opener.",
        "At the end the stack must be empty; an empty stack on a closer means invalid.",
    ],
    solution_explanation=(
        "A stack records open brackets; each closer must match the most recent "
        "opener (LIFO), and a non-empty stack at the end means something is unclosed."),
))

add(Scenario(
    slug="py-impl-temperature-stats",
    title="Implement Temperature Statistics",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement stats(nums) returning a dict {'min','max','mean'} for a "
        "non-empty list of numbers. mean is a float. The stub is empty so tests "
        "fail. (You decide behavior for empty -> the tests only use non-empty "
        "lists, but raising ValueError on empty is acceptable.)"),
    objectives=[
        "Compute min, max, and mean",
        "Return them in a dict with the exact keys",
        "Keep mean as a float",
    ],
    instructions=(
        "Implement stats(nums) -> {'min': .., 'max': .., 'mean': ..} for a "
        "non-empty numeric list. mean must be a float.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def stats(nums):\n"
        "    # TODO: return {'min':..,'max':..,'mean':..}\n"
        "    pass\n"),
    reference=(
        "def stats(nums):\n"
        "    return {\n"
        "        'min': min(nums),\n"
        "        'max': max(nums),\n"
        "        'mean': sum(nums) / len(nums),\n"
        "    }\n"),
    visible_tests=[
        Test("basic",
             "r = stats([1, 2, 3, 4])\nassert r['min'] == 1 and r['max'] == 4 and r['mean'] == 2.5"),
        Test("single value",
             "r = stats([5])\nassert r == {'min': 5, 'max': 5, 'mean': 5.0}"),
    ],
    hidden_tests=[
        Test("negatives",
             "r = stats([-3, 0, 3])\nassert r['min'] == -3 and r['max'] == 3 and r['mean'] == 0.0"),
        Test("floats mean",
             "r = stats([1, 2])\nassert isinstance(r['mean'], float) and r['mean'] == 1.5"),
        Test("has exactly the keys",
             "r = stats([7, 8])\nassert set(r.keys()) == {'min', 'max', 'mean'}"),
    ],
    hints=[
        "Python has built-in min() and max().",
        "mean is sum(nums) / len(nums) — true division gives a float.",
        "Return a dict with keys 'min', 'max', and 'mean'.",
    ],
    solution_explanation=(
        "min/max are built-ins; the mean is the sum over the count. Returning them "
        "in a dict with the required keys satisfies the contract."),
))

add(Scenario(
    slug="py-impl-caesar-cipher",
    title="Implement a Caesar Cipher",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement caesar(text, shift): shift each ASCII letter by `shift` "
        "positions, wrapping within its case, leaving non-letters unchanged. shift "
        "can be any integer (including negative or > 26). The stub is empty so "
        "tests fail."),
    objectives=[
        "Shift letters within their case with wraparound",
        "Leave non-letters unchanged",
        "Handle large/negative shifts via modulo",
    ],
    instructions=(
        "Implement caesar(text, shift) -> str. Letters shift within A-Z / a-z with "
        "wraparound; other characters pass through. Any integer shift is allowed.\n"
        "  caesar('abc', 1) -> 'bcd', caesar('XYZ', 3) -> 'ABC'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def caesar(text, shift):\n"
        "    # TODO: shift letters, wrap within case, leave others alone\n"
        "    pass\n"),
    reference=(
        "def caesar(text, shift):\n"
        "    out = []\n"
        "    for ch in text:\n"
        "        if 'a' <= ch <= 'z':\n"
        "            out.append(chr((ord(ch) - ord('a') + shift) % 26 + ord('a')))\n"
        "        elif 'A' <= ch <= 'Z':\n"
        "            out.append(chr((ord(ch) - ord('A') + shift) % 26 + ord('A')))\n"
        "        else:\n"
        "            out.append(ch)\n"
        "    return ''.join(out)\n"),
    visible_tests=[
        Test("shift by one", "assert caesar('abc', 1) == 'bcd'"),
        Test("wrap uppercase", "assert caesar('XYZ', 3) == 'ABC', caesar('XYZ', 3)"),
    ],
    hidden_tests=[
        Test("non-letters unchanged", "assert caesar('a-b!', 1) == 'b-c!'"),
        Test("negative shift", "assert caesar('bcd', -1) == 'abc'"),
        Test("shift over 26", "assert caesar('abc', 27) == 'bcd'"),
        Test("mixed case", "assert caesar('Hello, World!', 5) == 'Mjqqt, Btwqi!'"),
        Test("zero shift", "assert caesar('Zz', 0) == 'Zz'"),
    ],
    hints=[
        "Work on letters only; copy other characters as-is.",
        "Map a letter to 0..25, add the shift, then mod 26 to wrap.",
        "Use ord/chr with the case base ('a' or 'A') and (... + shift) % 26.",
    ],
    solution_explanation=(
        "Normalizing each letter to 0..25 within its case, adding the shift, and "
        "taking mod 26 handles wraparound for any integer shift; non-letters pass "
        "through unchanged."),
))

add(Scenario(
    slug="py-impl-bank-account-class",
    title="Implement a BankAccount with Overdraft Protection",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement a BankAccount class: starts at an opening balance (default 0), "
        "supports deposit(amount) and withdraw(amount). Negative or zero amounts "
        "raise ValueError. A withdrawal exceeding the balance raises an exception "
        "with the message 'Insufficient funds' and does NOT change the balance. "
        "balance is exposed as an attribute. The stub is empty so tests fail."),
    objectives=[
        "Track a balance and update it on deposit/withdraw",
        "Reject non-positive amounts with ValueError",
        "Block overdrafts with a clear error and no state change",
    ],
    instructions=(
        "Implement class BankAccount(opening=0) with .balance, deposit(amount), "
        "withdraw(amount). amount must be > 0 (else ValueError). Withdrawing more "
        "than the balance raises ValueError('Insufficient funds') and leaves "
        "balance unchanged.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "class BankAccount:\n"
        "    # TODO: balance, deposit, withdraw with validation + overdraft protection\n"
        "    pass\n"),
    reference=(
        "class BankAccount:\n"
        "    def __init__(self, opening=0):\n"
        "        self.balance = opening\n"
        "    def deposit(self, amount):\n"
        "        if amount <= 0:\n"
        "            raise ValueError('amount must be positive')\n"
        "        self.balance += amount\n"
        "        return self.balance\n"
        "    def withdraw(self, amount):\n"
        "        if amount <= 0:\n"
        "            raise ValueError('amount must be positive')\n"
        "        if amount > self.balance:\n"
        "            raise ValueError('Insufficient funds')\n"
        "        self.balance -= amount\n"
        "        return self.balance\n"),
    visible_tests=[
        Test("deposit then withdraw",
             "a = BankAccount()\na.deposit(100)\na.withdraw(30)\nassert a.balance == 70"),
        Test("opening balance",
             "a = BankAccount(50)\nassert a.balance == 50"),
    ],
    hidden_tests=[
        Test("overdraft blocked and balance unchanged",
             "a = BankAccount(20)\ntry:\n    a.withdraw(50)\n    assert False, 'should raise'\nexcept ValueError as e:\n    assert 'Insufficient funds' in str(e)\nassert a.balance == 20"),
        Test("negative deposit rejected",
             "a = BankAccount()\ntry:\n    a.deposit(-5)\n    assert False\nexcept ValueError:\n    pass\nassert a.balance == 0"),
        Test("zero withdraw rejected",
             "a = BankAccount(10)\ntry:\n    a.withdraw(0)\n    assert False\nexcept ValueError:\n    pass"),
        Test("exact balance withdrawal allowed",
             "a = BankAccount(40)\na.withdraw(40)\nassert a.balance == 0"),
    ],
    hints=[
        "Store balance in __init__ from the opening argument (default 0).",
        "Validate amount > 0 in both deposit and withdraw, raising ValueError otherwise.",
        "In withdraw, if amount > balance raise ValueError('Insufficient funds') before changing balance.",
    ],
    solution_explanation=(
        "Validation runs before any mutation, so a rejected operation leaves the "
        "balance untouched. The overdraft check raises with the required message."),
))

add(Scenario(
    slug="py-impl-matrix-transpose",
    title="Implement Matrix Transpose",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement transpose(matrix): return the transpose of a rectangular matrix "
        "(list of equal-length rows). Rows become columns. The stub is empty so "
        "tests fail."),
    objectives=[
        "Swap rows and columns",
        "Handle non-square matrices",
        "Return a new matrix without mutating the input",
    ],
    instructions=(
        "Implement transpose(matrix) -> transposed matrix.\n"
        "  transpose([[1,2,3],[4,5,6]]) -> [[1,4],[2,5],[3,6]]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def transpose(matrix):\n"
        "    # TODO: return the transpose\n"
        "    pass\n"),
    reference=(
        "def transpose(matrix):\n"
        "    if not matrix:\n"
        "        return []\n"
        "    return [list(col) for col in zip(*matrix)]\n"),
    visible_tests=[
        Test("rectangular", "assert transpose([[1,2,3],[4,5,6]]) == [[1,4],[2,5],[3,6]]"),
        Test("square", "assert transpose([[1,2],[3,4]]) == [[1,3],[2,4]]"),
    ],
    hidden_tests=[
        Test("single row", "assert transpose([[1,2,3]]) == [[1],[2],[3]]"),
        Test("single column", "assert transpose([[1],[2],[3]]) == [[1,2,3]]"),
        Test("empty matrix", "assert transpose([]) == []"),
        Test("does not mutate",
             "m = [[1,2],[3,4]]\ntranspose(m)\nassert m == [[1,2],[3,4]]"),
    ],
    hints=[
        "Element [i][j] of the input becomes [j][i] of the output.",
        "zip(*matrix) pairs up the i-th element of each row — that's the columns.",
        "Wrap each zipped tuple in list(): [list(col) for col in zip(*matrix)].",
    ],
    solution_explanation=(
        "zip(*matrix) yields one tuple per column, which is exactly the transposed "
        "rows; converting each to a list returns a fresh matrix."),
))

add(Scenario(
    slug="py-impl-password-strength",
    title="Implement a Password Strength Validator",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement is_strong_password(p): True only if p is at least 8 characters "
        "AND contains at least one lowercase letter, one uppercase letter, one "
        "digit, and one of the symbols !@#$%^&*. Otherwise False. The stub is "
        "empty so tests fail."),
    objectives=[
        "Enforce the minimum length",
        "Require lowercase, uppercase, digit, and symbol",
        "Return False if any rule is unmet",
    ],
    instructions=(
        "Implement is_strong_password(p) -> bool. Rules: len >= 8; >=1 lowercase; "
        ">=1 uppercase; >=1 digit; >=1 symbol from !@#$%^&*.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def is_strong_password(p):\n"
        "    # TODO: validate per the rules in the brief/tests\n"
        "    pass\n"),
    reference=(
        "def is_strong_password(p):\n"
        "    symbols = set('!@#$%^&*')\n"
        "    if len(p) < 8:\n"
        "        return False\n"
        "    has_lower = any(c.islower() for c in p)\n"
        "    has_upper = any(c.isupper() for c in p)\n"
        "    has_digit = any(c.isdigit() for c in p)\n"
        "    has_symbol = any(c in symbols for c in p)\n"
        "    return has_lower and has_upper and has_digit and has_symbol\n"),
    visible_tests=[
        Test("strong", "assert is_strong_password('Abcdef1!') is True"),
        Test("too short", "assert is_strong_password('Ab1!') is False"),
    ],
    hidden_tests=[
        Test("no uppercase", "assert is_strong_password('abcdef1!') is False"),
        Test("no lowercase", "assert is_strong_password('ABCDEF1!') is False"),
        Test("no digit", "assert is_strong_password('Abcdefg!') is False"),
        Test("no symbol", "assert is_strong_password('Abcdefg1') is False"),
        Test("long and complete", "assert is_strong_password('Sup3r$ecretPass') is True"),
    ],
    hints=[
        "Check the length first; short passwords fail immediately.",
        "Use any(c.islower() ...), any(c.isupper() ...), any(c.isdigit() ...).",
        "Check membership against the set of allowed symbols and require all four classes.",
    ],
    solution_explanation=(
        "Each rule is an independent any() check over the characters; the password "
        "is strong only when the length and all four character-class checks pass."),
))

add(Scenario(
    slug="py-impl-json-flatten-keys",
    title="Implement Nested Dict Flattening",
    language="python", kind="impl", difficulty="hard", scenario_type="do",
    description=(
        "Implement flatten_dict(d): flatten a nested dict into a single-level dict "
        "whose keys join the path with dots. Values that are dicts recurse; all "
        "other values (including lists) are leaves. The stub is empty so tests "
        "fail."),
    objectives=[
        "Recurse into nested dictionaries",
        "Join key paths with '.'",
        "Treat non-dict values as leaves",
    ],
    instructions=(
        "Implement flatten_dict(d) -> flat dict with dotted keys.\n"
        "  flatten_dict({'a': {'b': 1, 'c': {'d': 2}}, 'e': 3}) -> "
        "{'a.b': 1, 'a.c.d': 2, 'e': 3}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def flatten_dict(d):\n"
        "    # TODO: flatten nested dicts into dotted keys\n"
        "    pass\n"),
    reference=(
        "def flatten_dict(d, prefix=''):\n"
        "    out = {}\n"
        "    for key, value in d.items():\n"
        "        full = f'{prefix}{key}' if not prefix else f'{prefix}.{key}'\n"
        "        if isinstance(value, dict):\n"
        "            out.update(flatten_dict(value, full))\n"
        "        else:\n"
        "            out[full] = value\n"
        "    return out\n"),
    visible_tests=[
        Test("nested example",
             "assert flatten_dict({'a': {'b': 1, 'c': {'d': 2}}, 'e': 3}) == "
             "{'a.b': 1, 'a.c.d': 2, 'e': 3}"),
        Test("flat already",
             "assert flatten_dict({'x': 1, 'y': 2}) == {'x': 1, 'y': 2}"),
    ],
    hidden_tests=[
        Test("deep nesting",
             "assert flatten_dict({'a': {'b': {'c': {'d': 9}}}}) == {'a.b.c.d': 9}"),
        Test("list is a leaf",
             "assert flatten_dict({'a': {'b': [1, 2]}}) == {'a.b': [1, 2]}"),
        Test("empty dict", "assert flatten_dict({}) == {}"),
        Test("mixed leaves and nests",
             "assert flatten_dict({'k': 1, 'n': {'a': 2, 'b': {'c': 3}}}) == "
             "{'k': 1, 'n.a': 2, 'n.b.c': 3}"),
    ],
    hints=[
        "Carry a prefix string as you descend into nested dicts.",
        "Only recurse when the value is a dict; everything else is a leaf.",
        "Join the prefix and key with '.', and merge recursive results with dict.update.",
    ],
    solution_explanation=(
        "Recursing only on dict values and threading a dotted prefix builds the "
        "joined key paths; non-dict values (including lists) terminate as leaves."),
))

add(Scenario(
    slug="py-impl-fizz-sum-divisors",
    title="Implement sum_of_divisors",
    language="python", kind="impl", difficulty="easy", scenario_type="do",
    description=(
        "Implement sum_of_divisors(n) for a positive integer n: the sum of all "
        "positive divisors of n that are strictly less than n (its proper "
        "divisors). sum_of_divisors(6) == 1+2+3 == 6. The stub is empty so tests "
        "fail."),
    objectives=[
        "Find all proper divisors of n",
        "Exclude n itself",
        "Return their sum (1 for primes, 0 for 1)",
    ],
    instructions=(
        "Implement sum_of_divisors(n) -> sum of proper divisors (divisors < n).\n"
        "  sum_of_divisors(6) -> 6 (1+2+3), sum_of_divisors(12) -> 16\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def sum_of_divisors(n):\n"
        "    # TODO: sum the proper divisors of n\n"
        "    pass\n"),
    reference=(
        "def sum_of_divisors(n):\n"
        "    if n <= 1:\n"
        "        return 0\n"
        "    total = 1  # 1 divides every n > 1\n"
        "    i = 2\n"
        "    while i * i <= n:\n"
        "        if n % i == 0:\n"
        "            total += i\n"
        "            other = n // i\n"
        "            if other != i and other != n:\n"
        "                total += other\n"
        "        i += 1\n"
        "    return total\n"),
    visible_tests=[
        Test("perfect number", "assert sum_of_divisors(6) == 6, sum_of_divisors(6)"),
        Test("twelve", "assert sum_of_divisors(12) == 16, sum_of_divisors(12)"),
    ],
    hidden_tests=[
        Test("prime", "assert sum_of_divisors(7) == 1"),
        Test("one", "assert sum_of_divisors(1) == 0"),
        Test("perfect square", "assert sum_of_divisors(16) == 15, sum_of_divisors(16)"),
        Test("28 is perfect", "assert sum_of_divisors(28) == 28"),
    ],
    hints=[
        "1 is a proper divisor of every n > 1; n itself is excluded.",
        "Divisors come in pairs i and n//i — only scan i up to sqrt(n).",
        "Watch the perfect-square case (don't double-count i == n//i) and never add n.",
    ],
    solution_explanation=(
        "Scanning to sqrt(n) and adding both members of each divisor pair (without "
        "double-counting a square root, and excluding n) gives the proper-divisor sum."),
))

add(Scenario(
    slug="py-impl-counter-most-common",
    title="Implement most_common (top-k)",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "Implement most_common(items, k): return the k most frequent items as a "
        "list of (item, count) tuples, highest count first. Break ties by first "
        "appearance in `items`. The stub is empty so tests fail."),
    objectives=[
        "Count frequencies preserving first-seen order",
        "Sort by count descending, ties by first appearance",
        "Return the top k as (item, count) tuples",
    ],
    instructions=(
        "Implement most_common(items, k) -> list of (item, count) tuples for the k "
        "most frequent items, count descending, ties broken by first appearance.\n"
        "  most_common(['a','b','a','c','b','a'], 2) -> [('a', 3), ('b', 2)]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def most_common(items, k):\n"
        "    # TODO: return the top-k (item, count) tuples\n"
        "    pass\n"),
    reference=(
        "def most_common(items, k):\n"
        "    counts = {}\n"
        "    order = {}\n"
        "    for idx, it in enumerate(items):\n"
        "        if it not in counts:\n"
        "            counts[it] = 0\n"
        "            order[it] = idx\n"
        "        counts[it] += 1\n"
        "    ranked = sorted(counts, key=lambda it: (-counts[it], order[it]))\n"
        "    return [(it, counts[it]) for it in ranked[:k]]\n"),
    visible_tests=[
        Test("basic top 2",
             "assert most_common(['a','b','a','c','b','a'], 2) == [('a', 3), ('b', 2)]"),
        Test("k of 1",
             "assert most_common(['x','x','y'], 1) == [('x', 2)]"),
    ],
    hidden_tests=[
        Test("tie broken by first appearance",
             "assert most_common(['b','a','a','b'], 2) == [('b', 2), ('a', 2)]"),
        Test("k larger than distinct",
             "assert most_common(['a','b'], 5) == [('a', 1), ('b', 1)]"),
        Test("empty", "assert most_common([], 3) == []"),
        Test("all equal counts keep order",
             "assert most_common(['z','y','x'], 3) == [('z',1),('y',1),('x',1)]"),
    ],
    hints=[
        "Count occurrences and remember the first index where each item appeared.",
        "Sort items by (-count, first_index) so ties keep input order.",
        "Return the first k as (item, count) tuples.",
    ],
    solution_explanation=(
        "Counting with a first-seen index lets you sort by descending count and "
        "ascending first-appearance, giving a deterministic top-k."),
))

add(Scenario(
    slug="py-impl-linked-list-reverse",
    title="Implement Reverse a Linked List",
    language="python", kind="impl", difficulty="medium", scenario_type="do",
    description=(
        "A singly linked Node class (with .val and .next) is provided as a "
        "read-only helper. Implement reverse_list(head): reverse the list "
        "in-place and return the new head. The stub is empty so tests fail."),
    objectives=[
        "Walk the list re-pointing each .next backward",
        "Return the new head (old tail)",
        "Handle empty and single-node lists",
    ],
    instructions=(
        "Implement reverse_list(head) for the provided Node class; return the new "
        "head. The list helpers to_list(head) and from_list(values) are available "
        "for testing.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    extra_files=[(
        "linked.py",
        "class Node:\n"
        "    def __init__(self, val, next=None):\n"
        "        self.val = val\n"
        "        self.next = next\n"
        "\n"
        "def from_list(values):\n"
        "    head = None\n"
        "    for v in reversed(values):\n"
        "        head = Node(v, head)\n"
        "    return head\n"
        "\n"
        "def to_list(head):\n"
        "    out = []\n"
        "    while head is not None:\n"
        "        out.append(head.val)\n"
        "        head = head.next\n"
        "    return out\n",
        True,
    )],
    broken=(
        "def reverse_list(head):\n"
        "    # TODO: reverse the singly linked list and return the new head\n"
        "    pass\n"),
    reference=(
        "def reverse_list(head):\n"
        "    prev = None\n"
        "    cur = head\n"
        "    while cur is not None:\n"
        "        nxt = cur.next\n"
        "        cur.next = prev\n"
        "        prev = cur\n"
        "        cur = nxt\n"
        "    return prev\n"),
    visible_tests=[
        Test("reverses a list",
             "head = from_list([1, 2, 3, 4])\n"
             "assert to_list(reverse_list(head)) == [4, 3, 2, 1]"),
        Test("single node",
             "head = from_list([7])\nassert to_list(reverse_list(head)) == [7]"),
    ],
    hidden_tests=[
        Test("empty list", "assert reverse_list(None) is None"),
        Test("two nodes",
             "assert to_list(reverse_list(from_list([1, 2]))) == [2, 1]"),
        Test("longer list",
             "assert to_list(reverse_list(from_list([5,4,3,2,1]))) == [1,2,3,4,5]"),
        Test("new head is old tail",
             "head = from_list([1, 2, 3])\nnew_head = reverse_list(head)\nassert new_head.val == 3"),
    ],
    hints=[
        "Keep three pointers: prev, cur, and the saved next.",
        "For each node, point cur.next at prev, then advance prev and cur.",
        "Return prev at the end — it's the old tail / new head.",
    ],
    solution_explanation=(
        "Iteratively reversing the .next pointers with a prev/cur/next trio "
        "reverses the list in O(n) and returns the old tail as the new head."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: log-analysis + fix (read a traceback/log, fix the indicated bug)
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="py-logfix-keyerror-config",
    title="Log Analysis: Fix the KeyError from the Traceback",
    language="python", kind="logfix", difficulty="easy", scenario_type="fix",
    description=(
        "Production logged: `KeyError: 'timeout'` raised from get_setting() when a "
        "key is absent. The function should return a provided default instead of "
        "crashing on a missing key. Read the traceback in the comment and fix the "
        "lookup."),
    objectives=[
        "Read the traceback to identify the failing lookup",
        "Use a safe dict lookup with a default",
        "Return the default for missing keys without raising",
    ],
    instructions=(
        "Fix get_setting(config, key, default) so it returns config[key] when "
        "present, otherwise `default`. The log shows it currently raises KeyError "
        "on missing keys.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production traceback:\n"
        "#   File \"app.py\", line 12, in handle_request\n"
        "#     t = get_setting(cfg, 'timeout', 30)\n"
        "#   File \"settings.py\", line 4, in get_setting\n"
        "#     return config[key]\n"
        "# KeyError: 'timeout'\n"
        "\n"
        "def get_setting(config, key, default):\n"
        "    return config[key]   # raises KeyError when key is missing\n"),
    reference=(
        "def get_setting(config, key, default):\n"
        "    return config.get(key, default)\n"),
    visible_tests=[
        Test("present key", "assert get_setting({'timeout': 5}, 'timeout', 30) == 5"),
        Test("missing key uses default",
             "assert get_setting({}, 'timeout', 30) == 30"),
    ],
    hidden_tests=[
        Test("falsy stored value is returned",
             "assert get_setting({'retries': 0}, 'retries', 3) == 0"),
        Test("missing does not raise",
             "r = get_setting({'a': 1}, 'b', 'fallback')\nassert r == 'fallback'"),
        Test("None default", "assert get_setting({}, 'x', None) is None"),
    ],
    hints=[
        "The traceback points at `return config[key]` — bracket access raises on a missing key.",
        "dict.get(key, default) returns the default instead of raising.",
        "Return config.get(key, default).",
    ],
    solution_explanation=(
        "Subscript access raises KeyError for absent keys. dict.get(key, default) "
        "returns the fallback while still returning stored falsy values like 0."),
))

add(Scenario(
    slug="py-logfix-typeerror-none-len",
    title="Log Analysis: Fix the TypeError on len(None)",
    language="python", kind="logfix", difficulty="easy", scenario_type="fix",
    description=(
        "The log shows `TypeError: object of type 'NoneType' has no len()` from "
        "count_items() because the argument can be None. Treat None as an empty "
        "collection (count 0) without crashing."),
    objectives=[
        "Identify the None-length crash from the log",
        "Guard the None case",
        "Return 0 for None, the length otherwise",
    ],
    instructions=(
        "Fix count_items(items) so it returns len(items), but returns 0 when items "
        "is None. The log shows it crashes on None.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production log:\n"
        "#   TypeError: object of type 'NoneType' has no len()\n"
        "#     at count_items(items) -> return len(items)\n"
        "\n"
        "def count_items(items):\n"
        "    return len(items)   # crashes when items is None\n"),
    reference=(
        "def count_items(items):\n"
        "    if items is None:\n"
        "        return 0\n"
        "    return len(items)\n"),
    visible_tests=[
        Test("list length", "assert count_items([1, 2, 3]) == 3"),
        Test("none is zero", "assert count_items(None) == 0"),
    ],
    hidden_tests=[
        Test("empty list", "assert count_items([]) == 0"),
        Test("string length", "assert count_items('abc') == 3"),
        Test("dict length", "assert count_items({'a': 1}) == 1"),
        Test("none does not raise", "assert count_items(None) == 0"),
    ],
    hints=[
        "The log says len(None) is the problem.",
        "Check `if items is None` before calling len.",
        "Return 0 for None, otherwise len(items).",
    ],
    solution_explanation=(
        "len() requires a sized object. Guarding None and returning 0 prevents the "
        "TypeError while preserving normal length behavior."),
))

add(Scenario(
    slug="py-logfix-indexerror-last",
    title="Log Analysis: Fix the IndexError on Empty Input",
    language="python", kind="logfix", difficulty="easy", scenario_type="fix",
    description=(
        "The log shows `IndexError: list index out of range` from last_or_none() "
        "when the list is empty. It should return None for an empty list instead "
        "of indexing [-1]."),
    objectives=[
        "Spot the [-1] access that fails on empty lists",
        "Guard the empty case",
        "Return None when there is no last element",
    ],
    instructions=(
        "Fix last_or_none(items): return the last element, or None if the list is "
        "empty. The log shows an IndexError on empty input.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production log:\n"
        "#   IndexError: list index out of range\n"
        "#     at last_or_none(items) -> return items[-1]\n"
        "\n"
        "def last_or_none(items):\n"
        "    return items[-1]   # IndexError when items is empty\n"),
    reference=(
        "def last_or_none(items):\n"
        "    if not items:\n"
        "        return None\n"
        "    return items[-1]\n"),
    visible_tests=[
        Test("last element", "assert last_or_none([1, 2, 3]) == 3"),
        Test("empty is none", "assert last_or_none([]) is None"),
    ],
    hidden_tests=[
        Test("single element", "assert last_or_none([42]) == 42"),
        Test("strings", "assert last_or_none(['a', 'b']) == 'b'"),
        Test("empty does not raise", "assert last_or_none([]) is None"),
    ],
    hints=[
        "items[-1] on an empty list raises IndexError (per the log).",
        "Check `if not items` first.",
        "Return None when empty, otherwise items[-1].",
    ],
    solution_explanation=(
        "Indexing [-1] requires at least one element. An empty-check returning "
        "None avoids the IndexError."),
))

add(Scenario(
    slug="py-logfix-attributeerror-strip",
    title="Log Analysis: Fix the AttributeError on int.strip",
    language="python", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "The log shows `AttributeError: 'int' object has no attribute 'strip'` "
        "from normalize() because it calls .strip().lower() on every value, but "
        "some values are non-strings. Coerce to str first (or skip non-strings) so "
        "it never crashes, returning a lowercased, stripped string for every "
        "input."),
    objectives=[
        "Read the AttributeError and find the unsafe .strip call",
        "Coerce the value to a string before string operations",
        "Return a normalized string for any input type",
    ],
    instructions=(
        "Fix normalize(value): return str(value) lowercased and stripped of "
        "surrounding whitespace. It must work for strings AND non-strings (ints, "
        "etc). The log shows it crashes on an int.\n"
        "  normalize('  Hi ') -> 'hi', normalize(42) -> '42'\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production log:\n"
        "#   AttributeError: 'int' object has no attribute 'strip'\n"
        "#     at normalize(value) -> return value.strip().lower()\n"
        "\n"
        "def normalize(value):\n"
        "    return value.strip().lower()   # fails for non-strings\n"),
    reference=(
        "def normalize(value):\n"
        "    return str(value).strip().lower()\n"),
    visible_tests=[
        Test("string normalized", "assert normalize('  Hi ') == 'hi'"),
        Test("int coerced", "assert normalize(42) == '42'"),
    ],
    hidden_tests=[
        Test("already clean", "assert normalize('abc') == 'abc'"),
        Test("uppercase", "assert normalize('HELLO') == 'hello'"),
        Test("float", "assert normalize(3.5) == '3.5'"),
        Test("whitespace only", "assert normalize('   ') == ''"),
    ],
    hints=[
        "The log shows .strip() called on an int.",
        "Convert with str(value) before calling string methods.",
        "Return str(value).strip().lower().",
    ],
    solution_explanation=(
        "String methods only exist on strings. Wrapping the value in str() first "
        "makes the normalization total over any input type."),
))

add(Scenario(
    slug="py-logfix-recursion-depth",
    title="Log Analysis: Fix the RecursionError in factorial",
    language="python", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "The log shows `RecursionError: maximum recursion depth exceeded` from "
        "factorial() because its base case is wrong (it never stops at 0), so it "
        "recurses forever into negatives. Fix the base case so factorial(0) == 1 "
        "and recursion terminates."),
    objectives=[
        "Read the RecursionError and find the missing/wrong base case",
        "Stop recursion at n == 0 (or n <= 1)",
        "Return the correct factorial",
    ],
    instructions=(
        "Fix factorial(n) for n >= 0 so recursion terminates: factorial(0) == 1. "
        "The log shows infinite recursion.\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production log:\n"
        "#   RecursionError: maximum recursion depth exceeded\n"
        "#     factorial(n) keeps calling factorial(n - 1) past 0\n"
        "\n"
        "def factorial(n):\n"
        "    return n * factorial(n - 1)   # no base case -> infinite recursion\n"),
    reference=(
        "def factorial(n):\n"
        "    if n <= 1:\n"
        "        return 1\n"
        "    return n * factorial(n - 1)\n"),
    visible_tests=[
        Test("factorial 0", "assert factorial(0) == 1"),
        Test("factorial 5", "assert factorial(5) == 120"),
    ],
    hidden_tests=[
        Test("factorial 1", "assert factorial(1) == 1"),
        Test("factorial 10", "assert factorial(10) == 3628800"),
        Test("factorial 3", "assert factorial(3) == 6"),
    ],
    hints=[
        "The log says recursion never stops — there is no base case.",
        "factorial(0) and factorial(1) are both 1.",
        "Add `if n <= 1: return 1` before recursing.",
    ],
    solution_explanation=(
        "Without a base case the recursion descends past 0 forever. Returning 1 "
        "for n <= 1 terminates it with the correct value."),
))

add(Scenario(
    slug="py-logfix-valueerror-int-parse",
    title="Log Analysis: Fix the Crash Parsing CSV Numbers",
    language="python", kind="logfix", difficulty="medium", scenario_type="fix",
    description=(
        "A batch job crashed with `ValueError: invalid literal for int() with base "
        "10: ''` in sum_csv_row(). The row may contain empty fields and "
        "surrounding spaces. Parse only the integer fields, skipping blanks, and "
        "return their sum. Read the log and fix the parsing."),
    objectives=[
        "Read the ValueError and identify the bad int() call",
        "Skip empty/whitespace fields",
        "Sum the remaining integers robustly",
    ],
    instructions=(
        "Fix sum_csv_row(row) where row is a list of strings. Strip each field; "
        "skip empty fields; sum the integer values of the rest. The log shows it "
        "crashes on an empty field.\n"
        "  sum_csv_row(['1', ' 2 ', '', '3']) -> 6\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "# Production log:\n"
        "#   ValueError: invalid literal for int() with base 10: ''\n"
        "#     at sum_csv_row -> total += int(field)\n"
        "\n"
        "def sum_csv_row(row):\n"
        "    total = 0\n"
        "    for field in row:\n"
        "        total += int(field)   # blank fields raise ValueError\n"
        "    return total\n"),
    reference=(
        "def sum_csv_row(row):\n"
        "    total = 0\n"
        "    for field in row:\n"
        "        field = field.strip()\n"
        "        if not field:\n"
        "            continue\n"
        "        total += int(field)\n"
        "    return total\n"),
    visible_tests=[
        Test("with blanks and spaces",
             "assert sum_csv_row(['1', ' 2 ', '', '3']) == 6, sum_csv_row(['1', ' 2 ', '', '3'])"),
        Test("all numbers", "assert sum_csv_row(['10', '20']) == 30"),
    ],
    hidden_tests=[
        Test("only blanks", "assert sum_csv_row(['', '   ', '']) == 0"),
        Test("negative values", "assert sum_csv_row(['-5', '5']) == 0"),
        Test("single", "assert sum_csv_row([' 7 ']) == 7"),
        Test("empty row", "assert sum_csv_row([]) == 0"),
    ],
    hints=[
        "The log shows int('') failing — empty fields aren't numbers.",
        "Strip whitespace and skip fields that become empty.",
        "Continue past blank fields, then int(field) the rest.",
    ],
    solution_explanation=(
        "Empty/whitespace fields can't be parsed. Stripping and skipping blanks "
        "before int() makes the sum robust to messy CSV rows."),
))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY: code-review / refactor (correct-but-bad -> tests pin desired behavior;
# starter VIOLATES a behavioral contract the tests enforce)
# ─────────────────────────────────────────────────────────────────────────────

add(Scenario(
    slug="py-review-pure-no-mutate",
    title="Refactor: Make double_all Pure (No Mutation)",
    language="python", kind="review", difficulty="medium", scenario_type="fix",
    description=(
        "double_all(nums) returns a list with every value doubled, but it mutates "
        "the caller's list in place — a side effect that breaks callers who reuse "
        "the original. Refactor it to be pure: return a NEW list and leave the "
        "input unchanged. The hidden test pins the no-mutation contract."),
    objectives=[
        "Recognize the in-place mutation side effect",
        "Build and return a new list",
        "Leave the caller's list unchanged",
    ],
    instructions=(
        "Refactor double_all(nums) so it returns a new list of doubled values and "
        "does NOT modify the input list.\n"
        "  double_all([1,2,3]) -> [2,4,6]; the original stays [1,2,3]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def double_all(nums):\n"
        "    for i in range(len(nums)):\n"
        "        nums[i] *= 2      # mutates the caller's list\n"
        "    return nums\n"),
    reference=(
        "def double_all(nums):\n"
        "    return [n * 2 for n in nums]\n"),
    visible_tests=[
        Test("doubles values", "assert double_all([1, 2, 3]) == [2, 4, 6]"),
        Test("empty", "assert double_all([]) == []"),
    ],
    hidden_tests=[
        Test("does not mutate input",
             "src = [1, 2, 3]\ndouble_all(src)\nassert src == [1, 2, 3], src"),
        Test("returns a new object",
             "src = [4, 5]\nout = double_all(src)\nassert out is not src"),
        Test("negatives and zero", "assert double_all([-2, 0, 3]) == [-4, 0, 6]"),
    ],
    hints=[
        "After calling double_all(src), the caller's src is also doubled — that's the bug.",
        "Don't write back into nums; create a fresh list instead.",
        "Return [n * 2 for n in nums].",
    ],
    solution_explanation=(
        "Mutating nums in place leaks a side effect to callers. A list "
        "comprehension returns a new list and leaves the argument untouched."),
))

add(Scenario(
    slug="py-review-extract-guard-clause",
    title="Refactor: Fix the Discount Edge Cases",
    language="python", kind="review", difficulty="medium", scenario_type="fix",
    description=(
        "apply_discount(price, percent) applies a percentage discount, but the "
        "logic accepts invalid percentages (negative or > 100) and can return "
        "negative prices. Refactor with guard clauses: percent must be in [0, "
        "100] (else ValueError), and the returned price is never negative. The "
        "tests pin these contracts."),
    objectives=[
        "Validate the percent range with a guard clause",
        "Raise ValueError for out-of-range percentages",
        "Never return a negative price",
    ],
    instructions=(
        "Refactor apply_discount(price, percent): percent must be between 0 and "
        "100 inclusive (else raise ValueError). Return price reduced by that "
        "percent, as a float.\n"
        "  apply_discount(100, 25) -> 75.0\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def apply_discount(price, percent):\n"
        "    return price - price * percent / 100   # no validation; allows bad percent\n"),
    reference=(
        "def apply_discount(price, percent):\n"
        "    if percent < 0 or percent > 100:\n"
        "        raise ValueError('percent must be between 0 and 100')\n"
        "    return price * (1 - percent / 100)\n"),
    visible_tests=[
        Test("quarter off", "assert apply_discount(100, 25) == 75.0"),
        Test("no discount", "assert apply_discount(50, 0) == 50.0"),
    ],
    hidden_tests=[
        Test("full discount", "assert apply_discount(80, 100) == 0.0"),
        Test("negative percent rejected",
             "try:\n    apply_discount(100, -10)\n    assert False, 'should raise'\nexcept ValueError:\n    pass"),
        Test("over 100 percent rejected",
             "try:\n    apply_discount(100, 150)\n    assert False\nexcept ValueError:\n    pass"),
        Test("returns float", "assert isinstance(apply_discount(10, 10), float)"),
    ],
    hints=[
        "apply_discount(100, 150) currently returns -50 — an invalid percentage isn't rejected.",
        "Add a guard clause: raise ValueError when percent is outside [0, 100].",
        "Then return price * (1 - percent/100).",
    ],
    solution_explanation=(
        "A guard clause rejecting out-of-range percentages up front prevents "
        "nonsensical negative prices and makes the contract explicit."),
))

add(Scenario(
    slug="py-review-replace-loop-with-comprehension",
    title="Refactor: Correct and Simplify squares_of_evens",
    language="python", kind="review", difficulty="easy", scenario_type="fix",
    description=(
        "squares_of_evens(nums) is meant to return the squares of only the EVEN "
        "numbers, but the verbose loop has a bug: it squares every number and "
        "filters nothing. Refactor it (a comprehension is cleanest) so it returns "
        "the squares of the even values only, in order."),
    objectives=[
        "Notice odd numbers are wrongly included",
        "Filter to even numbers before squaring",
        "Return the squares in input order",
    ],
    instructions=(
        "Fix squares_of_evens(nums): return [n*n for the even n], preserving "
        "order.\n"
        "  squares_of_evens([1,2,3,4]) -> [4, 16]\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def squares_of_evens(nums):\n"
        "    out = []\n"
        "    for n in nums:\n"
        "        out.append(n * n)   # bug: never filters to evens\n"
        "    return out\n"),
    reference=(
        "def squares_of_evens(nums):\n"
        "    return [n * n for n in nums if n % 2 == 0]\n"),
    visible_tests=[
        Test("basic", "assert squares_of_evens([1, 2, 3, 4]) == [4, 16]"),
        Test("no evens", "assert squares_of_evens([1, 3, 5]) == []"),
    ],
    hidden_tests=[
        Test("all evens", "assert squares_of_evens([2, 4, 6]) == [4, 16, 36]"),
        Test("includes zero", "assert squares_of_evens([0, 1, 2]) == [0, 4]"),
        Test("negatives", "assert squares_of_evens([-2, -3, -4]) == [4, 16]"),
        Test("empty", "assert squares_of_evens([]) == []"),
    ],
    hints=[
        "squares_of_evens([1,2,3]) returns [1,4,9] — odds shouldn't be there.",
        "Square a number only when it's even (n % 2 == 0).",
        "Use a comprehension: [n*n for n in nums if n % 2 == 0].",
    ],
    solution_explanation=(
        "The loop squared everything with no filter. A guarded comprehension keeps "
        "only even numbers and is also clearer."),
))

add(Scenario(
    slug="py-review-default-dict-count",
    title="Refactor: Simplify and Fix char_counts",
    language="python", kind="review", difficulty="easy", scenario_type="fix",
    description=(
        "char_counts(s) should return a dict of character -> count, but the "
        "hand-rolled version forgets to initialize new keys, raising KeyError on "
        "the first occurrence of each character. Refactor it to count safely "
        "(collections.Counter or dict.get) and return the frequency map."),
    objectives=[
        "Reproduce the KeyError on the first character",
        "Initialize counts safely",
        "Return correct character frequencies",
    ],
    instructions=(
        "Fix char_counts(s): return {char: count}.\n"
        "  char_counts('aab') -> {'a': 2, 'b': 1}\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def char_counts(s):\n"
        "    counts = {}\n"
        "    for ch in s:\n"
        "        counts[ch] += 1   # KeyError: ch not initialized\n"
        "    return counts\n"),
    reference=(
        "def char_counts(s):\n"
        "    counts = {}\n"
        "    for ch in s:\n"
        "        counts[ch] = counts.get(ch, 0) + 1\n"
        "    return counts\n"),
    visible_tests=[
        Test("basic", "assert char_counts('aab') == {'a': 2, 'b': 1}"),
        Test("single char", "assert char_counts('z') == {'z': 1}"),
    ],
    hidden_tests=[
        Test("empty string", "assert char_counts('') == {}"),
        Test("spaces counted", "assert char_counts('a a') == {'a': 2, ' ': 1}"),
        Test("all same", "assert char_counts('xxxx') == {'x': 4}"),
        Test("mixed", "assert char_counts('abcabc') == {'a': 2, 'b': 2, 'c': 2}"),
    ],
    hints=[
        "char_counts('a') raises KeyError because counts['a'] doesn't exist yet.",
        "Initialize the key before incrementing, or use counts.get(ch, 0).",
        "counts[ch] = counts.get(ch, 0) + 1 (or use collections.Counter).",
    ],
    solution_explanation=(
        "Incrementing an absent key raises KeyError. Using counts.get(ch, 0) + 1 "
        "(or Counter) initializes on first sight."),
))

add(Scenario(
    slug="py-review-early-return-find-first",
    title="Refactor: Fix find_first to Return the First Match",
    language="python", kind="review", difficulty="easy", scenario_type="fix",
    description=(
        "find_first(items, predicate) should return the FIRST item for which "
        "predicate is true (or None), but it keeps looping and returns the LAST "
        "match instead. Refactor it to return early on the first match."),
    objectives=[
        "See it returns the last match, not the first",
        "Return as soon as the predicate is satisfied",
        "Return None when nothing matches",
    ],
    instructions=(
        "Fix find_first(items, predicate): return the first item where "
        "predicate(item) is true, else None.\n"
        "  find_first([1,2,3,4], lambda x: x > 2) -> 3\n"
        "Click Run to try it, then Check Solution to grade against all tests."),
    entrypoint="solution.py",
    broken=(
        "def find_first(items, predicate):\n"
        "    found = None\n"
        "    for it in items:\n"
        "        if predicate(it):\n"
        "            found = it      # keeps overwriting -> returns LAST match\n"
        "    return found\n"),
    reference=(
        "def find_first(items, predicate):\n"
        "    for it in items:\n"
        "        if predicate(it):\n"
        "            return it\n"
        "    return None\n"),
    visible_tests=[
        Test("first over two",
             "assert find_first([1, 2, 3, 4], lambda x: x > 2) == 3"),
        Test("no match",
             "assert find_first([1, 2], lambda x: x > 9) is None"),
    ],
    hidden_tests=[
        Test("returns first not last",
             "assert find_first([5, 6, 7], lambda x: x > 4) == 5"),
        Test("first element matches",
             "assert find_first(['a', 'b'], lambda s: s == 'a') == 'a'"),
        Test("empty", "assert find_first([], lambda x: True) is None"),
        Test("all match returns first", "assert find_first([2, 4, 6], lambda x: x % 2 == 0) == 2"),
    ],
    hints=[
        "find_first([5,6,7], x>4) returns 7, but the first match is 5.",
        "Assigning to `found` and continuing keeps the last match.",
        "Return immediately inside the if; return None after the loop.",
    ],
    solution_explanation=(
        "Returning on the first satisfying element (instead of recording and "
        "continuing) yields the first match and short-circuits the scan."),
))
