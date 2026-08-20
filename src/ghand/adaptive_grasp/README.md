# Adaptive Grasp User Guide

`ghand.adaptive_grasp` is the built-in adaptive grasp module of the GHand Python SDK. It runs a pipeline of **open fingers → pre-grasp pose → close to tactile contact → adaptive hold → release**, performing slip-risk analysis, grasp-force reference updates, and hold control based on tactile data.

## Requirements

- Python >= 3.10
- A project virtual environment with GHand Python SDK installed
- GHand hardware with accessible tactile sensors

Recommended installation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Install development and test tools with the `dev` extra:

```powershell
python -m pip install -e ".[dev]"
```

## Demo Overview

Demo file:

```text
examples/extension/02.adaptive_grasp_demo.py
```

Before running, you usually only need to edit:

```text
src/ghand/adaptive_grasp/demo_config.py
```

Common configuration:

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```

Parameter description:

- `GRASP_OBJECT`: Demo scene name; must be an existing key in `DEMO_SCENES`.
- `HOLD_TIME_S`: Auto-release time after entering adaptive hold, in seconds; must be greater than 0.
- `_INTERRUPT_RELEASE_WAIT_S`: Wait time after an interrupted fast release; must be greater than 0.

Quick run:

```powershell
.\.venv\Scripts\python.exe examples\extension\02.adaptive_grasp_demo.py
```

The demo performs the following steps:

1. Creates `GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)`.
2. Calls `hand.open("auto")` to connect to the dexterous hand.
3. Calls `hand.tactile_open()` to enable tactile sensors.
4. Builds `AdaptiveGraspConfig` from `demo_config.py`.
5. Calls `AdaptiveGrasper.grasp_core()` to enter grasp and adaptive hold.
6. Automatically releases after `HOLD_TIME_S`.
7. Closes tactile and communication in `finally`.

Pressing `Ctrl+C` during execution triggers `emergency_release(wait_s=runtime_config.interrupt_release_wait_s)` for a fast release.

## Minimal API Example

```python
import time

from ghand import CommType, GHand, ProductType
from ghand.adaptive_grasp import AdaptiveGrasper
from ghand.adaptive_grasp.demo_config import build_demo_runtime_config

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
grasper = None
runtime_config = build_demo_runtime_config("paper_cup", 60.0)

try:
    if not hand.open("auto"):
        raise RuntimeError("Connection failed")

    if not hand.tactile_open():
        raise RuntimeError("Failed to open tactile sensors")

    time.sleep(0.5)

    grasper = AdaptiveGrasper(
        hand=hand,
        config=runtime_config.adaptive_config,
    )

    if not grasper.grasp_core():
        raise RuntimeError(f"Grasp failed at state={grasper.get_state().value}")

    final_state = grasper.wait_for_completion()
    print(f"Final state: {final_state.value}")
except KeyboardInterrupt:
    if grasper is not None:
        grasper.emergency_release(wait_s=runtime_config.interrupt_release_wait_s)
finally:
    hand.tactile_close()
    hand.close()
```

Common methods:

- `grasp_core()`: Open fingers, pre-grasp, close to contact, and start the adaptive-hold thread.
- `wait_for_completion()`: Wait for the adaptive-hold and auto-release process to finish.
- `get_state()`: Read the current grasp state.
- `release()`: Actively stop holding and open the hand using normal release parameters.
- `emergency_release(wait_s=...)`: Fast release for interruption scenarios.
- `shutdown()`: Stop control threads, sensor subscriptions, and communication ports without actively opening the hand.

State enumeration is defined in `GraspState`:

```text
idle, open, pre_grasp, closing_to_contact, adaptive_hold,
release, completed, error, stopped
```

## Parameter Tuning

You can construct `AdaptiveGraspConfig` directly. Common parameters include:

| Parameter | Description |
| --- | --- |
| `default_object` | Default object configuration |
| `pre_grasp_preset` | Pre-grasp pose |
| `release_hold_time_s` | Adaptive hold time |
| `enable_position_hold_force_control` | Whether to enable force-control correction during position hold |
| `control_period_s` | Adaptive-hold control period |

`interrupt_release_wait_s` belongs to the demo runtime configuration, not `AdaptiveGraspConfig`; it only affects the wait time after a fast release triggered by `Ctrl+C`.

## Custom Objects and Pre-grasp Poses

To customize a grasp object, configure the following:

1. `PRE_GRASP_PRESET_DEGREES` in `src/ghand/adaptive_grasp/grasp_presets.py`.
2. `PRESET_ACTIVE_FINGERS` in `src/ghand/adaptive_grasp/grasp_presets.py`.
3. `DEFAULT_OBJECT_PROFILES` in `src/ghand/adaptive_grasp/object_profile.py`.
4. `DEMO_SCENES` in `src/ghand/adaptive_grasp/demo_config.py`.
5. `GRASP_OBJECT` in `src/ghand/adaptive_grasp/demo_config.py`.

## Key Files

```text
examples/extension/02.adaptive_grasp_demo.py
src/ghand/adaptive_grasp/demo_config.py
src/ghand/adaptive_grasp/config.py
src/ghand/adaptive_grasp/adaptive_grasp_manager.py
src/ghand/adaptive_grasp/grasp_sequence.py
src/ghand/adaptive_grasp/adaptive_hold_loop.py
src/ghand/adaptive_grasp/hold_planner_factory.py
src/ghand/adaptive_grasp/grasp_presets.py
src/ghand/adaptive_grasp/object_profile.py
```
