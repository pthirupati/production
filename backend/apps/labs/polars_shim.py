"""Minimal polars-compatible API for sandboxed coding labs (no polars wheel required).

Injected into the Python grading harness when ``language``/``runtime`` is ``polars``.
Enough for select / filter / with_columns / collect against small tabular data.
"""

POLARS_SHIM_SOURCE = r'''
class _Col:
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return ("eq", self.name, other)
    def __gt__(self, other):
        return ("gt", self.name, other)
    def __lt__(self, other):
        return ("lt", self.name, other)
    def alias(self, name):
        return ("alias", self.name, name)

def col(name):
    return _Col(name)

def lit(value):
    return ("lit", value)

class DataFrame:
    def __init__(self, data=None):
        if data is None:
            self._cols = {}
            self._n = 0
        elif isinstance(data, dict):
            self._cols = {k: list(v) for k, v in data.items()}
            self._n = len(next(iter(self._cols.values()), []))
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            self._cols = {k: [row.get(k) for row in data] for k in keys}
            self._n = len(data)
        else:
            raise TypeError("unsupported DataFrame constructor")
    def select(self, *exprs):
        out = {}
        for e in exprs:
            if isinstance(e, str):
                out[e] = list(self._cols[e])
            elif isinstance(e, _Col):
                out[e.name] = list(self._cols[e.name])
            elif isinstance(e, tuple) and e[0] == "alias":
                out[e[2]] = list(self._cols[e[1]])
            elif isinstance(e, tuple) and e[0] == "lit":
                out["literal"] = [e[1]] * self._n
            else:
                raise TypeError(f"unsupported select expr {e!r}")
        return DataFrame(out)
    def filter(self, pred):
        if not isinstance(pred, tuple) or len(pred) != 3:
            raise TypeError("filter expects col op value")
        op, name, value = pred
        colv = self._cols[name]
        keep = []
        for i, v in enumerate(colv):
            if op == "eq" and v == value: keep.append(i)
            elif op == "gt" and v > value: keep.append(i)
            elif op == "lt" and v < value: keep.append(i)
        out = {k: [vals[i] for i in keep] for k, vals in self._cols.items()}
        return DataFrame(out)
    def with_columns(self, *exprs):
        df = DataFrame(dict(self._cols))
        for e in exprs:
            if isinstance(e, tuple) and e[0] == "alias":
                df._cols[e[2]] = list(self._cols[e[1]])
            elif isinstance(e, tuple) and e[0] == "lit":
                df._cols["literal"] = [e[1]] * self._n
            elif isinstance(e, _Col):
                df._cols[e.name] = list(self._cols[e.name])
            else:
                raise TypeError(f"unsupported with_columns expr {e!r}")
        df._n = self._n
        return df
    def collect(self):
        return self
    def to_dicts(self):
        keys = list(self._cols.keys())
        return [{k: self._cols[k][i] for k in keys} for i in range(self._n)]
    def __len__(self):
        return self._n
    @property
    def columns(self):
        return list(self._cols.keys())
    def shape(self):
        return (self._n, len(self._cols))

class LazyFrame(DataFrame):
    def collect(self):
        return DataFrame(dict(self._cols))

class _PL:
    DataFrame = DataFrame
    LazyFrame = LazyFrame
    col = staticmethod(col)
    lit = staticmethod(lit)

pl = _PL()
'''
