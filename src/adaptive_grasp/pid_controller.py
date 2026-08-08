from typing import Optional


class LowPassFilter:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.filtered_value: Optional[float]=None
    def reset(self) -> None:
        self.filtered_value = None

    def compute(self, current_value: float) -> float:
        if self.filtered_value is None:
            self.filtered_value = current_value
            return self.filtered_value
        self.filtered_value = self.alpha * current_value + (1 - self.alpha) * self.filtered_value
        return self.filtered_value
