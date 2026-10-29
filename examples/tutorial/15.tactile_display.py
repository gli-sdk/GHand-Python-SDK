# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Tutorial 15: connect a device and launch the tactile display.

Install GUI dependencies with pip install "ghand_python_sdk[tactile-display]".
Edit the connection settings in main() for your device.
"""

import signal
import sys

from ghand import CommType, GHand, ProductType


if __name__ == "__main__":
    try:
        import PySide6
        import pyqtgraph
    except ModuleNotFoundError as exc:
        if exc.name not in {"PySide6", "pyqtgraph"}:
            raise
        print('Missing optional dependencies for tactile display. Run: python -m pip install "ghand_python_sdk[tactile-display]"',
              file=sys.stderr)
        raise SystemExit(1)

from PySide6.QtWidgets import QApplication

from ghand.tactile_display.display import TactileDisplay


def main() -> int:
    app = QApplication([sys.argv[0]])
    with GHand(ProductType.GHand5, CommType.ETHERCAT) as hand:
        if not hand.open("auto"):
            print("Device connection failed", file=sys.stderr)
            return 1
        window = TactileDisplay(hand)
        signal.signal(signal.SIGINT, lambda *_: window.close())
        window.show()
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
