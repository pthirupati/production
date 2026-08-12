"""Minimal pandas-compatible API for datascience notebook cells (no pandas wheel required).

Used by ``datascience_v2_facades`` when a notebook cell looks like pandas code.
"""

PANDAS_SHIM_SOURCE = r'''
class Series:
    def __init__(self, data, name=None):
        self._data = list(data)
        self.name = name
    def __len__(self):
        return len(self._data)
    def __iter__(self):
        return iter(self._data)
    def mean(self):
        nums = [float(x) for x in self._data if x is not None and str(x) != ""]
        return sum(nums) / len(nums) if nums else None
    def value_counts(self):
        counts = {}
        for v in self._data:
            k = str(v)
            counts[k] = counts.get(k, 0) + 1
        return DataFrame({"value": list(counts.keys()), "count": list(counts.values())})


class DataFrame:
    def __init__(self, data=None):
        if data is None:
            self._cols = {}
        elif isinstance(data, dict):
            self._cols = {k: list(v) for k, v in data.items()}
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            self._cols = {k: [row.get(k) for row in data] for k in keys}
        else:
            raise TypeError("unsupported DataFrame constructor")
        self._n = len(next(iter(self._cols.values()), [])) if self._cols else 0

    @property
    def columns(self):
        return list(self._cols.keys())

    @property
    def shape(self):
        return (self._n, len(self._cols))

    def __len__(self):
        return self._n

    def __getitem__(self, key):
        if isinstance(key, str):
            return Series(self._cols[key], name=key)
        if isinstance(key, list):
            return DataFrame({k: self._cols[k] for k in key if k in self._cols})
        raise TypeError("unsupported indexing")

    def head(self, n=5):
        out = {k: v[:n] for k, v in self._cols.items()}
        return DataFrame(out)

    def tail(self, n=5):
        out = {k: v[-n:] for k, v in self._cols.items()}
        return DataFrame(out)

    def describe(self):
        lines = []
        for c, vals in self._cols.items():
            nums = []
            for x in vals:
                try:
                    nums.append(float(x))
                except (TypeError, ValueError):
                    pass
            if nums:
                lines.append("%s: mean=%.3g n=%d" % (c, sum(nums) / len(nums), len(nums)))
        return "\n".join(lines) if lines else "No numeric columns"

    def to_dicts(self):
        return [{k: self._cols[k][i] for k in self._cols} for i in range(self._n)]

    def iloc(self, idx):
        if isinstance(idx, int):
            return {k: self._cols[k][idx] for k in self._cols}
        return self


class _PD:
    DataFrame = DataFrame
    Series = Series

pd = _PD()
'''
