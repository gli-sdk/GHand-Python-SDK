# Adaptive Grasp Guide

`adaptive_grasp` is the high-level adaptive grasping module in the GHand Python SDK. It handles hand opening, pre-grasp motion, closing until contact, adaptive holding, automatic release, and tactile-data-based slip and safety monitoring.

## Requirements

- Python `>= 3.10`
- GHand hardware with tactile sensors connected
- This repository and its runtime dependencies installed

Recommended virtual environment setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Quick Demo

Demo entry point:

```text
examples/extension/02.adaptive_grasp_demo.py
```

Before running the demo, usually only these two values in [demo_config.py](src/adaptive_grasp/demo_config.py) need to be changed:

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```

Run:

```powershell
.\.venv\Scripts\python.exe examples\extension\02.adaptive_grasp_demo.py
```

The demo creates `GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)`, connects the device, opens tactile sensing, and then creates an `AdaptiveGrasper` to run the grasp. Pressing `Ctrl+C` calls `emergency_release()` for a quick hand opening.

### Demo Scenes

`GRASP_OBJECT` is the scene name in `DEMO_SCENES`. It is not necessarily the same as the object profile name.

| Scene | Object profile | Pre-grasp preset | Hold mode |
| --- | --- | --- | --- |
| `paper_cup` | `paper_cup` | `paper_cup_grasp` | `POSITION` |
| `balloon` | `balloon` | `balloon_pinch` | `POSITION` |
| `glass_cup` | `glass` | `three_finger_grasp` | `STIFF_POSITION` |
| `plastic_cup` | `plastic_cup` | `paper_cup_grasp` | `POSITION` |
| `mineral_water_bottle_500ml` | `mineral_water_bottle_500ml` | `minreal_water_grasp` | `POSITION` |
| `plastic_object` | `plastic` | `two_finger_pinch` | `POSITION` |
| `orange` | `fruit` | `four_finger_grasp` | `POSITION` |
| `cylinder_piece` | `cylinder_piece` | `cylinder_piece_grasp` | `STIFF_POSITION` |

`build_demo_runtime_config()` validates the scene name and hold duration. `HOLD_TIME_S` must be greater than `0`; values less than or equal to `1` second produce a warning. Visualization is disabled by default and can be enabled with `build_demo_runtime_config(enable_visualization=True)`. The interrupted-release wait time comes from `DemoRuntimeConfig.interrupt_release_wait_s`, whose default value is `3.0` seconds.

## Minimal Example

The example below is reduced from the current demo flow. It keeps the same call order for connection, tactile initialization, grasping, waiting for completion, interrupted release, and resource cleanup.

```python
import time

from adaptive_grasp import AdaptiveGrasper
from adaptive_grasp.demo_config import build_demo_runtime_config
from ghand import CommType, GHand, ProductType

hand = GHand(
    product_type=ProductType.GHand5,
    comm_type=CommType.ETHERCAT,
)
runtime_config = build_demo_runtime_config()
grasper = None

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

    print(f"Final state: {grasper.wait_for_completion().value}")
except KeyboardInterrupt:
    if grasper is not None:
        grasper.emergency_release(
            wait_s=runtime_config.interrupt_release_wait_s,
        )
finally:
    hand.tactile_close()
    hand.close()
```

After `grasp_core()` succeeds, it starts the background adaptive hold thread. When the hold duration reaches `release_hold_time_s`, the background thread automatically performs release. `wait_for_completion()` only waits for the hold and release workflow to finish; it does not actively trigger release.

## Direct Configuration

When not using the demo defaults, construct `AdaptiveGraspConfig` and `HoldCommandMode` directly:

```python
from adaptive_grasp import (
    AdaptiveGraspConfig,
    AdaptiveGrasper,
    HoldCommandMode,
)

config = AdaptiveGraspConfig(
    default_object="paper_cup",
    pre_grasp_preset="paper_cup_grasp",
    hold_command_mode=HoldCommandMode.POSITION,
    release_hold_time_s=20.0,
    enable_visualization=False,
)
grasper = AdaptiveGrasper(hand=hand, config=config)
```

`hold_command_mode` must be an enum value. The currently supported values are:

```python
HoldCommandMode.POSITION
HoldCommandMode.STIFF_POSITION
```

String input is not supported, and there is no externally exposed `TORQUE` hold mode.

### Configuration Rules

- All joint angles are in **degrees**, including `pre_grasp_pose`, `position_hold_*_deg`, and `stiff_position_*_deg`.
- `pre_grasp_preset` is required. If `pre_grasp_pose` is not provided explicitly, it is generated from the preset.
- `pre_grasp_pose` must not contain passive DIP joints: `THUMB_IP`, `FF_DIP`, `MF_DIP`, `RF_DIP`, `LF_DIP`.
- When `active_fingers` is empty, the current implementation derives it from `PRESET_ACTIVE_FINGERS` for the selected preset. You may also explicitly pass `set[TactileSensorId]` to override it.
- `default_object` must exist in `ObjectProfileRegistry`.

Common configuration fields:

| Field | Meaning |
| --- | --- |
| `open_speed` / `open_torque` | Position-command speed and torque/current limit during the opening phase |
| `pre_grasp_speed` / `pre_grasp_torque` | Position-command speed and torque/current limit during the pre-grasp phase |
| `phase_timeout` | Timeout for the closing-until-contact phase |
| `closing_total_contact_threshold_n` | Total normal-force threshold required to end the closing phase |
| `finger_touch_threshold_n` | Per-finger tactile contact threshold |
| `control_period_s` | Adaptive hold control period |
| `release_hold_time_s` | Hold duration before automatic release |
| `release_open_speed` / `release_open_torque` | Release opening command parameters |
| `enable_visualization` | Whether to enable internal tactile diagnostic visualization |

For complete defaults and validation ranges, see [config.py](src/adaptive_grasp/config.py).

## Hold Modes

### `HoldCommandMode.POSITION`

This is the default mode. The module computes position corrections from tactile normal force, slip risk, and object safe-force bounds for each active finger, then sends position-mode commands.

Common parameters:

- `enable_position_hold_force_control`
- `position_hold_max_step_deg`
- `position_hold_contact_angle_guard_margin_deg`
- `position_hold_force_limit_slowdown_ratio`
- `position_hold_slip_risk_deadband`
- `position_hold_slip_risk_full`

This mode requires a valid `ObjectProfile` and uses its `position_hold_speed`, `position_hold_torque`, `safe_force_min`, and `safe_force_max`.

### `HoldCommandMode.STIFF_POSITION`

This mode is intended for stiff objects. When the total tactile normal force is below the target, active joints increment by a fixed step relative to the contact snapshot. The increment stops when the target force is reached or when a sudden contact-force drop is detected.

Common parameters:

- `stiff_position_hold_speed`
- `stiff_position_hold_torque`
- `stiff_position_step_deg`
- `stiff_position_max_delta_deg`
- `stiff_position_force_drop_ratio`

Target-force priority:

1. `grasp_core(hold_target_force_n=...)`
2. `ObjectProfile.stiff_position_hold_target_force`
3. `ObjectProfile.safe_force_min`

For stiff position hold, speed and torque first use `ObjectProfile.stiff_position_hold_speed` and `ObjectProfile.stiff_position_hold_torque`. If the object profile does not provide them, the planner falls back to `AdaptiveGraspConfig.stiff_position_hold_speed=90` and `AdaptiveGraspConfig.stiff_position_hold_torque=90`.

## Object Profiles and Pre-Grasp Presets

Default object profiles are defined in [object_profile.py](src/adaptive_grasp/object_profile.py) as `DEFAULT_OBJECT_PROFILES`. Each `ObjectProfile` contains:

- `safe_force_min` / `safe_force_max`: safe range for the sum of normal force across all active fingers
- `friction_coeff`: friction coefficient used by tactile slip analysis
- `is_fragile`: fragile-object flag
- `phase_closing_torque`: torque/current limit for the closing-until-contact phase
- `position_hold_speed` / `position_hold_torque`: normal position hold parameters
- `stiff_position_hold_speed` / `stiff_position_hold_torque` / `stiff_position_hold_target_force`: optional overrides for stiff position hold

Pre-grasp presets are defined in [grasp_presets.py](src/adaptive_grasp/grasp_presets.py):

- `PRE_GRASP_PRESET_DEGREES`: pre-grasp joint angles, in degrees
- `PRESET_ACTIVE_FINGERS`: fingers used by each preset for contact, tactile analysis, and hold control

When adding a new demo scene, keep the mappings complete:

```text
DEMO_SCENES scene name
  -> DemoScene.default_object
  -> ObjectProfile.name

DEMO_SCENES scene name
  -> DemoScene.pre_grasp_preset
  -> PRE_GRASP_PRESET_DEGREES and PRESET_ACTIVE_FINGERS key
```

If your application constructs `AdaptiveGraspConfig` directly, you do not need to modify `DEMO_SCENES`; however, `default_object`, `pre_grasp_preset`, and the active-finger mapping must still be valid.

## Common API

### `AdaptiveGrasper`

- `grasp_core(object_profile=None, *, hold_target_force_n=None) -> bool`: runs opening, pre-grasp, and closing until contact; starts background hold after success.
- `wait_for_completion(poll_period_s=0.1) -> GraspState`: waits for hold and release to finish.
- `release() -> bool`: stops holding and opens the hand using normal release parameters.
- `emergency_release(wait_s=2.0) -> bool`: opens the hand immediately without waiting for the control thread; intended for interruption handling.
- `release_and_wait_for_visualizer_close() -> bool`: releases and waits for the visualization window to close.
- `shutdown() -> None`: stops control, sensors, visualization, and transport without actively opening the hand.
- `get_state() -> GraspState`: returns the current state.

Read-only diagnostic properties:

- `last_tactile_analysis`
- `last_safety_report`
- `last_force_decisions`
- `last_tactile_data_age_s`
- `last_control_cycle_s`
- `last_control_cycle_jitter_s`
- `last_contact_snapshot`

### States

```text
idle
open
pre_grasp
closing_to_contact
adaptive_hold
release
completed
error
stopped
```

## Key Source Files

```text
examples/extension/02.adaptive_grasp_demo.py
src/adaptive_grasp/demo_config.py
src/adaptive_grasp/config.py
src/adaptive_grasp/adaptive_grasp_manager.py
src/adaptive_grasp/grasp_sequence.py
src/adaptive_grasp/adaptive_hold_loop.py
src/adaptive_grasp/hold_planner_factory.py
src/adaptive_grasp/grasp_presets.py
src/adaptive_grasp/object_profile.py
```
