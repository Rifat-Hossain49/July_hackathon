"""Module entry point for ``python -m app.simulator``.

Delegates to ``main.run()``. Exists so the slice is invokable both as a
package and as a module.
"""

from __future__ import annotations

import sys

from .main import run


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run(sys.argv[1:]))
