# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Tutorial 15: connect a device and launch the tactile display.

GUI dependencies are installed with ghand_python_sdk.
Edit the connection settings in main() for your device.
"""

import signal
import sys

from ghand import CommType, GHand, ProductType


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
