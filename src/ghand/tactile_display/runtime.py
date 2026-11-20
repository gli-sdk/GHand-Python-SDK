# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Check Linux GUI dependencies before Qt can abort the process."""

import ctypes
import os
from pathlib import Path
import sys


def check_gui_dependencies() -> None:
    """Raise RuntimeError when the Linux X11 plugin cannot load.

    Call before creating QApplication. Explicit non-xcb backends and native
    Wayland sessions are left to Qt.
    """
    if not sys.platform.startswith("linux"):
        return
    platform = os.environ.get("QT_QPA_PLATFORM", "").split(":", 1)[0]
    if platform and platform != "xcb":
        return
    if not platform and os.environ.get("WAYLAND_DISPLAY"):
        return

    from PySide6.QtCore import QLibraryInfo

    plugin = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms" / "libqxcb.so"
    try:
        ctypes.CDLL(str(plugin))
    except OSError as exc:
        raise RuntimeError(
            "Linux Qt xcb 插件加载失败 / Could not load the Linux Qt xcb plugin.\n"
            f"{exc}\n"
            "Ubuntu/Debian 请安装系统依赖 / Install system dependencies:\n"
            "  sudo apt update\n"
            "  sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 "
            "libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1\n"
            "其他发行版请安装对应软件包；pip 不会安装这些系统库。\n"
            "On other distributions, install the equivalent system packages."
        ) from exc
