import pytest
from pathlib import Path

import adaptive_grasp.pid_controller as pid_module
from adaptive_grasp.pid_controller import PidController, PidParams


PID_CONTROLLER_SOURCE = (
    Path(__file__).parents[2] / "src" / "adaptive_grasp" / "pid_controller.py"
)


def test_pid_controller_exports_from_adaptive_grasp_package():
    from adaptive_grasp import PidController as ExportedPidController
    from adaptive_grasp import PidParams as ExportedPidParams

    assert ExportedPidController is PidController
    assert ExportedPidParams is PidParams


def test_pid_controller_uses_project_clip_helper():
    source = PID_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert pid_module.PidController.compute.__globals__["clip"] is pid_module.clip
    assert "def _clamp" not in source


def test_pid_controller_computes_p_i_d_terms():
    controller = PidController(
        PidParams(K_p=2.0, K_i=0.5, K_d=0.1, I_min=-10.0, I_max=10.0)
    )

    first = controller.compute(error=1.0, dt=0.1)
    second = controller.compute(error=0.5, dt=0.1)

    assert first == pytest.approx(2.05)
    assert second == pytest.approx(0.575)


def test_pid_controller_ignores_derivative_on_first_compute():
    controller = PidController(
        PidParams(K_p=0.0, K_i=0.0, K_d=1.0, I_min=-10.0, I_max=10.0)
    )

    first = controller.compute(error=100.0, dt=0.01)
    second = controller.compute(error=99.0, dt=0.01)

    assert first == pytest.approx(0.0)
    assert second == pytest.approx(-100.0)


@pytest.mark.parametrize("dt", [0.0, -0.01])
def test_pid_controller_rejects_non_positive_dt(dt):
    controller = PidController(
        PidParams(K_p=1.0, K_i=1.0, K_d=1.0, I_min=-10.0, I_max=10.0)
    )

    with pytest.raises(ValueError, match="dt must be > 0"):
        controller.compute(error=1.0, dt=dt)


def test_pid_controller_clamps_integral():
    controller = PidController(
        PidParams(K_p=0.0, K_i=1.0, K_d=0.0, I_min=-0.2, I_max=0.2)
    )

    output = controller.compute(error=10.0, dt=1.0)

    assert output == pytest.approx(0.2)
    assert controller.integral == pytest.approx(0.2)


def test_pid_controller_reset_clears_state():
    controller = PidController(
        PidParams(K_p=0.0, K_i=1.0, K_d=1.0, I_min=-10.0, I_max=10.0)
    )
    controller.compute(error=1.0, dt=0.1)

    controller.reset()
    output = controller.compute(error=1.0, dt=0.1)

    assert controller.integral == pytest.approx(0.1)
    assert output == pytest.approx(0.1)
