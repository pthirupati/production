"""Session 81: sklearn shim + residual polish fixtures."""

from django.test import SimpleTestCase

from apps.labs.code_exec import _build_python_harness, grade_submission, resolve_runtime


class SklearnShimTests(SimpleTestCase):
    def test_resolve_and_grade_with_shim(self):
        self.assertEqual(resolve_runtime({"language": "sklearn"}), "python")
        self.assertEqual(resolve_runtime({"language": "scikit-learn"}), "python")
        harness = _build_python_harness(
            "clf = LogisticRegression()\n"
            "clf.fit([[0],[1],[0],[1]], [0,1,0,1])\n",
            [{"name": "t", "code": "assert clf.predict([[1]])[0] == 1", "hidden": False}],
            inject_sklearn=True,
        )
        self.assertIn("class LogisticRegression", harness)
        result = grade_submission(
            "python",
            "X = [[0,0],[1,1],[0,1],[1,0]]\n"
            "y = [0,1,0,1]\n"
            "Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1)\n"
            "clf = LogisticRegression()\n"
            "clf.fit(Xtr, ytr)\n"
            "preds = clf.predict(Xte)\n"
            "acc = accuracy_score(yte, preds)\n",
            [
                {"name": "split", "code": "assert len(Xte) >= 1", "hidden": False},
                {"name": "acc", "code": "assert acc >= 0.0", "hidden": False},
            ],
            authoring_language="sklearn",
        )
        self.assertTrue(result.all_passed, result.error or result)
