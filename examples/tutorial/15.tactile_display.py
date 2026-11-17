# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Tutorial 15: connect a device and launch the tactile display.

Python GUI dependencies are installed with ghand_python_sdk.
Linux system dependencies are listed in README.md (Linux GUI dependencies).
Edit the connection settings in main() for your device.

GHand5 polling/subscriptions include computed per-finger CAD moments. The window
shows Mx/My/Mz (N m), the reference O (mm), and a Moment history tab. Defaults:
O is each sensor's own CAD origin; F_CAD = R.T @ F_taxel_local. Invalid or unknown
tactile health leaves moments unavailable. No joint torque is measured here.
"""

import signal
import sys

from ghand import CommType, GHand, ProductType


from PySide6.QtWidgets import QApplication

from ghand.tactile_display.display import TactileDisplay
from ghand.tactile_display.runtime import check_gui_dependencies


def main() -> int:
    try:
        check_gui_dependencies()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    app = QApplication([sys.argv[0]])
    with GHand(ProductType.GHand5, CommType.ETHERCAT) as hand:
        # Optional reference shift, in meters in each sensor's CAD frame:
        # hand.configure_tactile_moments(reference_point_m=(0., 0., 0.005))
        if not hand.open("auto"):
            print("Device connection failed", file=sys.stderr)
            return 1
        window = TactileDisplay(hand)
        signal.signal(signal.SIGINT, lambda *_: window.close())
        window.show()
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
