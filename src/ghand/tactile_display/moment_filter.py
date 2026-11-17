# SPDX-License-Identifier: Apache-2.0
"""Bounded three-point impulse rejection for display copies only.

A candidate is displayed only after the next history sample arrives. Its
original timestamp is retained. This is delayed display, not a zero-latency
causal filter for control or training. Raw history is never modified.
"""
import math

import numpy as np


def despike_moment_history(history, *, max_jump_nm=1e-5, max_gap_s=.1):
    """Replace small isolated excursions whose two neighbours nearly agree.

    Each axis is independent. Preserve steps, sustained changes, large pulses,
    invalid values and gaps. The first sample has no left context and is kept.
    Hold back the last finite sample until confirmation; an invalid last sample
    is retained immediately so stale/error breaks remain visible.
    """
    if not math.isfinite(max_jump_nm) or max_jump_nm < 0:
        raise ValueError('max_jump_nm must be finite and nonnegative')
    if not math.isfinite(max_gap_s) or max_gap_s <= 0:
        raise ValueError('max_gap_s must be finite and positive')
    if not history or max_jump_nm == 0:
        return history
    times = np.asarray([t for t, _ in history], dtype=float)
    fingers = tuple(dict.fromkeys(f for _, values in history for f in values))
    raw = np.asarray([[values.get(f, (math.nan,) * 3) for f in fingers]
                      for _, values in history], dtype=float)
    filtered = raw.copy()
    if len(history) >= 3:
        a, b, c = raw[:-2], raw[1:-1], raw[2:]
        intervals = np.diff(times)
        continuous = ((intervals[:-1] > 0) & (intervals[1:] > 0)
                      & (intervals[:-1] <= max_gap_s) & (intervals[1:] <= max_gap_s))
        finite = np.isfinite(a) & np.isfinite(b) & np.isfinite(c)
        baseline = (a + c) * .5
        deviation = np.abs(b - baseline)
        extreme = ((b > a) & (b > c)) | ((b < a) & (b < c))
        small = np.maximum(np.abs(b-a), np.abs(b-c)) <= max_jump_nm
        returned = np.abs(c-a) <= .25 * deviation
        replace = finite & continuous[:, None, None] & extreme & small & returned
        filtered[1:-1] = np.where(replace, baseline, b)
    stop = len(history)
    if (stop > 1 and 0 < times[-1]-times[-2] <= max_gap_s
            and (np.isfinite(raw[-1]) & np.isfinite(raw[-2])).any()):
        stop -= 1
    return tuple((history[i][0], {f: tuple(filtered[i, j]) for j, f in enumerate(fingers)})
                 for i in range(stop))
