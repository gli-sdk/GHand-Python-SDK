# Hold Planner Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自适应保持阶段拆成共享的参考力规划、位置保持规划和力矩保持规划，让位置模式和力矩模式使用同一套 `F_ref` 更新逻辑。

**Architecture:** `ForceReferencePlanner` 只负责 `F_ref_total`、滑动增力、稳定衰减、材质库限幅和每指 `force_ref` 分配。`TorqueHoldPlanner` 只负责将每指 `force_ref - force_actual` 转成力矩。`PositionHoldPlanner` 只负责将每指 `force_ref - force_actual` 转成关节角度目标。

**Tech Stack:** Python, dataclasses, pytest, existing `PidController`, `AdaptiveGraspConfig`, `ObjectProfile`, `TactileAnalysis`, `ContactSnapshot`.

---

### Task 1: Add ForceReferencePlanner

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/force_reference_planner.py`
- Create: `tests/adaptive_grasp/test_force_reference_planner.py`

- [x] Write failing tests for contact ratio allocation, initial `F_ref_total`, slip rise, confirmed boost, stable decay, and profile bounds.
- [x] Run `python -m pytest tests\adaptive_grasp\test_force_reference_planner.py -q` and verify RED.
- [x] Implement `ForceReferencePlanner` with a `compute(analysis, dt)` method returning `ForceReferenceDecision`.
- [x] Run the same tests and verify GREEN.

### Task 2: Make TorqueHoldPlanner consume force refs

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/torque_hold_planner.py`
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py`
- Modify: `tests/adaptive_grasp/test_torque_hold_planner.py`
- Modify: `tests/adaptive_grasp/test_adaptive_grasp_manager.py`

- [x] Update tests so `TorqueHoldPlanner` receives a `ForceReferencePlanner` or `ForceReferenceDecision` instead of owning contact-ratio and `F_ref_total` logic.
- [x] Run focused torque tests and verify RED.
- [x] Move reference-force logic out of `TorqueHoldPlanner`.
- [x] Run focused torque tests and verify GREEN.

### Task 3: Extract PositionHoldPlanner

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/position_hold_planner.py`
- Modify: `src/xiaoyao/adaptive_grasp/force_planner.py`
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py`
- Modify: `tests/adaptive_grasp/test_force_planner.py`
- Modify: `tests/adaptive_grasp/test_adaptive_hold_loop.py`

- [x] Write failing tests that position mode uses shared `force_refs` rather than `F_init / finger_count`.
- [x] Implement `PositionHoldPlanner` by moving position-specific PID and target-angle generation out of `ForcePlanner`.
- [x] Keep `ForcePlanner` as a compatibility wrapper if needed.
- [x] Run focused position tests and verify GREEN.

### Task 4: Integrate hold loop and verify

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py`
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py`
- Modify: `src/xiaoyao/adaptive_grasp/__init__.py`

- [x] Ensure one shared `ForceReferencePlanner` is created from the contact snapshot when adaptive hold starts.
- [x] In each hold step, compute force references once, then dispatch to position or torque planner.
- [x] Run `python -m pytest tests\adaptive_grasp\test_force_reference_planner.py tests\adaptive_grasp\test_torque_hold_planner.py tests\adaptive_grasp\test_force_planner.py tests\adaptive_grasp\test_adaptive_hold_loop.py tests\adaptive_grasp\test_adaptive_grasp_manager.py -q`.
- [x] Document any remaining compatibility risks before merging.
