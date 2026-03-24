from __future__ import annotations

import sys

from devvault_desktop.engine_subprocess import main as engine_subprocess_main
from devvault_desktop.qt_app import main as qt_main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--engine-subprocess":
        raise SystemExit(engine_subprocess_main(sys.argv[2:]))
    raise SystemExit(qt_main())
