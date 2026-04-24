def clip(value: float, lower: float, upper: float) -> float:
    """Clip value to [lower, upper], swapping bounds if inverted."""
    if upper < lower:
        upper = lower
    return max(lower, min(upper, value))
