"""Minimal sklearn-compatible API for sandboxed coding labs (no sklearn wheel required).

Injected into the Python grading harness when authoring language is ``sklearn``.
Enough for train_test_split + LogisticRegression fit/predict/score on small arrays.
"""

SKLEARN_SHIM_SOURCE = r'''
def train_test_split(X, y, test_size=0.25, random_state=None):
    X = list(X)
    y = list(y)
    if len(X) != len(y):
        raise ValueError("X and y must have the same length")
    n = len(X)
    n_test = max(1, int(round(n * float(test_size)))) if n > 1 else 1
    n_test = min(n_test, n - 1) if n > 1 else n
    idx = list(range(n))
    if random_state is not None:
        seed = int(random_state) & 0xFFFFFFFF
        for i in range(n - 1, 0, -1):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            j = seed % (i + 1)
            idx[i], idx[j] = idx[j], idx[i]
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]
    return (
        [X[i] for i in train_idx],
        [X[i] for i in test_idx],
        [y[i] for i in train_idx],
        [y[i] for i in test_idx],
    )


class LogisticRegression:
    def __init__(self, max_iter=100, random_state=None):
        self.max_iter = max_iter
        self.random_state = random_state
        self.classes_ = []
        self._proto = {}

    def fit(self, X, y):
        X = list(X)
        y = list(y)
        self.classes_ = sorted(set(y), key=lambda v: str(v))
        self._proto = {}
        for cls in self.classes_:
            rows = [X[i] for i, label in enumerate(y) if label == cls]
            if not rows:
                self._proto[cls] = None
                continue
            sample = rows[0]
            if hasattr(sample, "__len__") and not isinstance(sample, (str, bytes)):
                dim = len(sample)
                acc = [0.0] * dim
                for r in rows:
                    for j, v in enumerate(r):
                        acc[j] += float(v)
                self._proto[cls] = [a / len(rows) for a in acc]
            else:
                self._proto[cls] = sum(float(r) for r in rows) / len(rows)
        return self

    def _dist(self, a, b):
        if not hasattr(a, "__len__") or isinstance(a, (str, bytes)):
            return abs(float(a) - float(b))
        return sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) ** 0.5

    def predict(self, X):
        out = []
        for row in X:
            best, best_d = None, None
            for cls, proto in self._proto.items():
                if proto is None:
                    continue
                d = self._dist(row, proto)
                if best_d is None or d < best_d:
                    best, best_d = cls, d
            out.append(best if best is not None else (self.classes_[0] if self.classes_ else None))
        return out

    def score(self, X, y):
        preds = self.predict(X)
        if not preds:
            return 0.0
        return sum(1 for a, b in zip(preds, y) if a == b) / len(preds)


def accuracy_score(y_true, y_pred):
    y_true = list(y_true)
    y_pred = list(y_pred)
    if not y_true:
        return 0.0
    return sum(1 for a, b in zip(y_true, y_pred) if a == b) / len(y_true)


class SMOTE:
    """Nearest-centroid style oversampler — balances class counts by cloning minority rows."""

    def __init__(self, sampling_strategy="auto", k_neighbors=5, random_state=None):
        self.sampling_strategy = sampling_strategy
        self.k_neighbors = k_neighbors
        self.random_state = random_state

    def fit_resample(self, X, y):
        X = list(X)
        y = list(y)
        if len(X) != len(y):
            raise ValueError("X and y must have the same length")
        by_cls = {}
        for row, label in zip(X, y):
            by_cls.setdefault(label, []).append(row)
        if not by_cls:
            return X, y
        target = max(len(v) for v in by_cls.values())
        out_X, out_y = list(X), list(y)
        seed = int(self.random_state or 0) & 0xFFFFFFFF
        for label, rows in by_cls.items():
            while len([1 for yy in out_y if yy == label]) < target:
                seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
                pick = rows[seed % len(rows)]
                # light jitter for numeric vectors
                if hasattr(pick, "__len__") and not isinstance(pick, (str, bytes)):
                    clone = []
                    for v in pick:
                        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
                        try:
                            clone.append(float(v) + ((seed % 100) - 50) / 1000.0)
                        except (TypeError, ValueError):
                            clone.append(v)
                    out_X.append(clone)
                else:
                    out_X.append(pick)
                out_y.append(label)
        return out_X, out_y


class _ModelSelection:
    train_test_split = staticmethod(train_test_split)


class _LinearModel:
    LogisticRegression = LogisticRegression


class _Metrics:
    accuracy_score = staticmethod(accuracy_score)


class _OverSampling:
    SMOTE = SMOTE


class _Imblearn:
    over_sampling = _OverSampling()


class _Sklearn:
    model_selection = _ModelSelection()
    linear_model = _LinearModel()
    metrics = _Metrics()

sklearn = _Sklearn()
imblearn = _Imblearn()
'''
