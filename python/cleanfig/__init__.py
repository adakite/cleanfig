from __future__ import annotations

import os

__version__ = "1.4.0"


if os.environ.get("CLEANFIG_FORCE_FALLBACK") == "1":
    from ._fallback import Figure, Panel, PlotHandle, figure

    BACKEND = "python-fallback"
else:
    try:
        from ._cleanfig import Figure, Panel, PlotHandle, figure

        BACKEND = "rust"
    except ImportError:
        from ._fallback import Figure, Panel, PlotHandle, figure

        BACKEND = "python-fallback"


__all__ = ["__version__", "BACKEND", "Figure", "Panel", "PlotHandle", "figure"]
