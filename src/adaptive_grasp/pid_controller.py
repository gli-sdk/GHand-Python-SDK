from dataclasses import dataclass
from typing import Optional



@dataclass(frozen=True)
class PidParams:
    K_p: float
    K_i: float
    K_d: float
    I_min: float
    I_max: float


class PidController:
    """Stateful PID controller with integral clamping.

    The derivative term is ignored on the first compute call because there is
    no previous error to compare against.
    """

    def __init__(self, params: PidParams):
        self.params = params
        self.integral: float = 0.0
        self._previous_error: Optional[float] = None

    def reset(self) -> None:
        self.integral = 0.0
        self._previous_error = None

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0:
            raise ValueError("dt must be > 0")

        self.integral = self._clamp(
            self.integral + error * dt,
            self.params.I_min,
            self.params.I_max,
        )
        derivative = self._compute_derivative(error, dt)
        self._previous_error = error
        return (
            self.params.K_p * error
            + self.params.K_i * self.integral
            + self.params.K_d * derivative
        )

    def _compute_derivative(self, error: float, dt: float) -> float:
        if self._previous_error is None:
            return 0.0
        return (error - self._previous_error) / dt

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(value, upper))


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