# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""Adaptive grasp module version information.

This module provides adaptive grasp execution, hold planning, tactile analysis,
and safety monitoring for the adaptive grasp package.
"""

ADAPTIVE_GRASP_VERSION_MAJOR = 2
ADAPTIVE_GRASP_VERSION_MINOR = 0
ADAPTIVE_GRASP_VERSION_REVISION = 0

GIT_COMMIT_HASH = "36eaa766cc5d77c1af292dd757790a88d0dfd7ae"
MODULE_SUMMARY = (
    "Adaptive grasp module with grasp execution, hold control, tactile analysis, and safety monitoring."
    "The stage of adaptive holding provides two modes: position hold and torque hold."
)

__version__ = "{}.{}.{}".format(
    ADAPTIVE_GRASP_VERSION_MAJOR,
    ADAPTIVE_GRASP_VERSION_MINOR,
    ADAPTIVE_GRASP_VERSION_REVISION,
)
