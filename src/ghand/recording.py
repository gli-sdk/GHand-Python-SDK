# SPDX-License-Identifier: Apache-2.0
"""Passive same-host telemetry recording and tactile-only T-Rex preparation.

No device/client is constructed and no motion, zeroing or mode command is sent.
PyArrow is an optional dependency; install ghand_python_sdk[recording].
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

import numpy as np

FINGERS = ['THUMB', 'FF', 'MF', 'RF', 'LF']
COUNTS = [38, 31, 31, 31, 31]
AXES = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz']
SCHEMA = 'ghand.tactile_capture.v1'
DEFAULT_GEOMETRY = Path(__file__).parent/'config/ghand5_tactile_geometry.json'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError('需要 PyArrow：python -m pip install "ghand_python_sdk[recording]"；或使用已安装 pyarrow 的 lerobot 环境') from exc
    return pa, pq


def _finite_array(value, shape):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'expected finite array {shape}')
    return a


def _uint(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid unsigned integer')
    return value


def decode_packet(packet, received_at, *, geometry_sha256, max_age_s=.15):
    """Archive source values. Invalid tactile/F6 stays null or masked, never zero."""
    if not isinstance(packet, dict) or packet.get('schema') != 'rmghand.telemetry.v3':
        raise ValueError('需要 rmghand.telemetry.v3 遥测；请使用当前手部遥操发送端')
    seq = _uint(packet.get('sequence'), 2**63-1)
    acquired, sent = float(packet['acquired_monotonic']), float(packet['sent_monotonic'])
    duration = float(packet['read_duration_ms'])
    if not all(math.isfinite(v) for v in (acquired, sent, received_at)) or acquired > sent:
        raise ValueError('invalid host monotonic timestamps')
    if not math.isfinite(duration) or duration < 0:
        raise ValueError('invalid SDK read duration')
    issues = []
    if received_at < sent or received_at-acquired > max_age_s:
        issues.append('stale_or_clock_mismatch')
    row = dict(sequence=seq, timestamp=acquired, sent_timestamp=sent,
        received_timestamp=float(received_at), sequence_gap=0, phase='unmarked',
        read_duration_ms=duration, distributed_force=None,
        taxel_valid_mask=[[j < n for j in range(38)] for n in COUNTS],
        sensor_valid_mask=[False]*5, raw_state=None, error=None,
        resultant_force=None, f6=[None]*5, wrench_valid_mask=[False]*5,
        moment_reference_point_m=[None]*5, joint_ids=[], joint_angle_deg=[],
        joint_velocity_pct=[], joint_current_pct=[],
        target_deg_json=None if 'target_deg' not in packet else _json(packet['target_deg']),
        commands_json=None if 'commands' not in packet else _json(packet['commands']),
        command_timestamp=packet.get('command_timestamp'),
        source_packet_json=_json(packet))
    for joint in packet.get('feedback', []):
        row['joint_ids'].append(str(joint['id']))
        row['joint_angle_deg'].append(float(joint['angle_deg']))
        # The compatibility bridge exposes current SDK percentages under old names.
        native = 'native_control_mode' in joint
        row['joint_velocity_pct'].append(float(joint['speed']) if native else None)
        row['joint_current_pct'].append(float(joint['torque']) if native else None)
        if joint.get('native_error', 0):
            issues.append('joint_fault')
        if 'error' in joint and str(joint['error']) not in ('0', 'NORMAL', 'NONE'):
            issues.append('joint_reported_error')
    if len(set(row['joint_ids'])) != len(row['joint_ids']):
        raise ValueError('duplicate joint IDs')
    if not np.isfinite(row['joint_angle_deg']).all():
        raise ValueError('nonfinite joint feedback')
    hand = packet.get('hand', {})
    if any(hand.get(k, 0) for k in ('error_fault', 'error_critical', 'error_warn')):
        issues.append('hand_warning_or_fault')
    if 'error' in hand and str(hand['error']) not in ('0', 'NORMAL', 'NONE'):
        issues.append('hand_reported_error')
    tactile = packet.get('tactile')
    if not isinstance(tactile, dict) or 'tactile_error' in packet:
        issues.append('missing_tactile')
    else:
        try:
            row['raw_state'] = _uint(tactile['raw_state'], 255)
            row['error'] = _uint(tactile['error'], 255)
            valid = tactile['sensor_state']
            if not isinstance(valid, list) or len(valid) != 5 or any(type(v) is not bool for v in valid):
                raise ValueError('invalid sensor mask')
            row['sensor_valid_mask'] = valid
            if not all(valid) or row['raw_state'] & 31 != 31 or row['error']:
                issues.append('tactile_unhealthy')
            raw = _finite_array(tactile['distributed_force'], (486,)).reshape(162, 3)
            # Padding is structural only and explicitly marked false by the mask.
            padded = np.zeros((5, 38, 3)); offset = 0
            for i, count in enumerate(COUNTS):
                padded[i, :count] = raw[offset:offset+count]; offset += count
            row['distributed_force'] = padded.tolist()
            row['resultant_force'] = _finite_array(tactile['resultant_force'], (15,)).reshape(5, 3).tolist()
            wrench = tactile['wrench']
            expected = dict(schema='ghand.tactile_wrench.v1', finger_order=FINGERS,
                axes=AXES, frame='per_sensor_cad', force_unit='N', moment_unit='N m')
            if any(wrench.get(k) != v for k, v in expected.items()):
                raise ValueError('wrench convention mismatch')
            source = wrench.get('source', {})
            if source.get('geometry_sha256') != geometry_sha256:
                raise ValueError('geometry checksum differs from archived geometry')
            calculator_hash = source.get('calculator_sha256', '')
            if len(calculator_hash) != 64 or any(c not in '0123456789abcdef' for c in calculator_hash):
                raise ValueError('missing calculator provenance')
            wvalid = wrench['valid']
            if len(wvalid) != 5 or any(type(v) is not bool for v in wvalid):
                raise ValueError('invalid wrench mask')
            for i, available in enumerate(wvalid):
                if available:
                    row['f6'][i] = _finite_array(wrench['f6'][i], (6,)).tolist()
                    row['moment_reference_point_m'][i] = _finite_array(wrench['reference_point_m'][i], (3,)).tolist()
                    row['wrench_valid_mask'][i] = True
                elif wrench['f6'][i] is not None or wrench['reference_point_m'][i] is not None:
                    raise ValueError('unavailable wrench rows must be null')
            if not all(wvalid):
                issues.append('incomplete_wrench')
        except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            issues.append(f'invalid_tactile_or_wrench:{exc}')
    row['sample_valid'] = not issues
    row['quality_issues'] = ';'.join(issues)
    return row


def _schema():
    pa, _ = _arrow()
    vector = lambda dtype, n: pa.list_(dtype, n)
    f3 = vector(pa.float64(), 3)
    # Parquet readers differ on nested null fixed-size lists. Use nullable
    # variable lists for unavailable measurements; decode_packet validates sizes.
    nullable_floats = pa.list_(pa.float64())
    return pa.schema([
        ('sequence', pa.int64()), ('timestamp', pa.float64()),
        ('sent_timestamp', pa.float64()), ('received_timestamp', pa.float64()),
        ('sequence_gap', pa.int64()), ('phase', pa.string()), ('read_duration_ms', pa.float64()),
        ('distributed_force', pa.list_(pa.list_(nullable_floats))),
        ('taxel_valid_mask', vector(vector(pa.bool_(), 38), 5)),
        ('sensor_valid_mask', vector(pa.bool_(), 5)), ('raw_state', pa.uint8()), ('error', pa.uint8()),
        ('resultant_force', pa.list_(nullable_floats)), ('f6', pa.list_(nullable_floats)),
        ('wrench_valid_mask', vector(pa.bool_(), 5)), ('moment_reference_point_m', pa.list_(nullable_floats)),
        ('joint_ids', pa.list_(pa.string())), ('joint_angle_deg', pa.list_(pa.float64())),
        ('joint_velocity_pct', pa.list_(pa.float64())), ('joint_current_pct', pa.list_(pa.float64())),
        ('target_deg_json', pa.string()), ('commands_json', pa.string()), ('command_timestamp', pa.float64()),
        ('sample_valid', pa.bool_()), ('quality_issues', pa.string()), ('source_packet_json', pa.string()),
    ], metadata={b'schema': SCHEMA.encode(), b'timestamp_semantics':
        b'same_host_sdk_read_completion_monotonic_not_sensor_hardware_time'})


def _atomic_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False, encoding='utf-8') as f:
        temporary = Path(f.name)
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        f.flush(); os.fsync(f.fileno())
    try:
        os.link(temporary, path)  # Atomic publication, fails instead of overwriting.
    finally:
        temporary.unlink(missing_ok=True)


class CaptureSession:
    """One writer owns its dataset root; episodes publish with no-replace semantics."""
    def __init__(self, root, *, geometry=DEFAULT_GEOMETRY, max_samples=20000):
        _arrow()
        self.root = Path(root)
        self.max_samples = max_samples
        self.geometry_hash = sha256(geometry)
        for d in ('meta', 'episodes'):
            (self.root/d).mkdir(parents=True, exist_ok=True)
        snapshot = self.root/'meta/geometry.json'
        if snapshot.exists():
            if json.loads(snapshot.read_text()) != json.loads(Path(geometry).read_text()):
                raise ValueError('dataset geometry changed; use a new dataset root')
        else:
            _atomic_json(snapshot, json.loads(Path(geometry).read_text()))
            # JSON whitespace is part of source provenance; preserve exact source bytes.
            # Store the original source separately to keep its fingerprint auditable.
        source = self.root/'meta/geometry_source.json'
        if not source.exists():
            with source.open('xb') as f: f.write(Path(geometry).read_bytes())
        elif sha256(source) != self.geometry_hash:
            raise ValueError('dataset geometry source changed')
        # Semantic snapshot and exact-byte source serve different purposes.
        if json.loads(snapshot.read_text()) != json.loads(Path(geometry).read_text()):
            raise ValueError('geometry content changed')
        meta = self.root/'meta/dataset.json'
        if not meta.exists():
            _atomic_json(meta, dict(schema=SCHEMA, finger_order=FINGERS, taxel_counts=COUNTS,
                geometry_sha256=self.geometry_hash, force_unit='N', moment_unit='N m',
                frame='per_sensor_cad', angle_unit='degree', speed_current_unit='percent_if_native_sdk_fields_present',
                timestamp_semantics='same-host monotonic SDK read completion; not sensor hardware clock',
                calibration={'status':'not_independently_verified', 'zeroing_history':'unknown_no_extra_bias_subtraction'},
                ownership='passive UDP only; no device, arm or camera IO',
                commands='targets only unless producer explicitly supplies commands and command_timestamp'))
        self.active = False
        self.rows = []

    @property
    def count(self):
        return len(self.rows)

    def start(self, *, object_id, pose_id, active_fingers):
        if self.active:
            raise RuntimeError('save or discard the current episode first')
        if not object_id or not pose_id or not active_fingers or len(set(active_fingers)) != len(active_fingers) or not set(active_fingers) <= set(FINGERS):
            raise ValueError('object/pose IDs and unique active fingers are required')
        self.info = dict(schema=SCHEMA, episode_id=uuid.uuid4().hex, object_id=object_id,
            pose_id=pose_id, active_fingers=list(active_fingers), started_unix=time.time(),
            geometry_sha256=self.geometry_hash, duplicates=0, missing_packets=0, rejected_packets=0)
        self.rows = []; self.last_sequence = None; self.last_time = None
        self.identity = None; self.wrench_contract = None; self.active = True

    def add(self, packet, received_at, *, phase='unmarked', max_age_s=.15):
        if not self.active:
            return False
        if self.count >= self.max_samples:
            raise RuntimeError('episode sample limit reached; save before recording more')
        row = decode_packet(packet, received_at, geometry_sha256=self.geometry_hash, max_age_s=max_age_s)
        identity = _json(packet.get('device', {}))
        if self.identity is not None and identity != self.identity:
            raise ValueError('device identity changed; start a new dataset/episode')
        seq = row['sequence']
        if self.last_sequence is not None:
            if seq == self.last_sequence:
                self.info['duplicates'] += 1
                return False
            if seq < self.last_sequence or row['timestamp'] <= self.last_time:
                raise ValueError('telemetry sequence/time reset or reordered; save and restart episode')
            row['sequence_gap'] = seq-self.last_sequence-1
        if row['sample_valid']:
            wrench = packet['tactile']['wrench']
            contract = {k:wrench[k] for k in ('finger_order','axes','frame','force_unit','moment_unit','reference_point_m','source')}
            if self.wrench_contract is not None and contract != self.wrench_contract:
                raise ValueError('wrench source/reference changed; start a new episode')
            self.wrench_contract = contract
        self.identity = identity
        self.last_sequence = seq; self.last_time = row['timestamp']
        self.info['missing_packets'] += row['sequence_gap']
        row['phase'] = str(phase); self.rows.append(row)
        return True

    def save(self, *, result='unspecified', interrupted=False):
        if not self.active or not self.rows:
            raise ValueError('cannot save an empty episode')
        pa, pq = _arrow()
        name = f"episode_{self.info['episode_id']}"
        dest = self.root/'episodes'/f'{name}.parquet'
        temporary = dest.with_suffix('.parquet.pending')
        metadata = {**self.info, 'device':json.loads(self.identity), 'wrench_contract':self.wrench_contract,
            'frames':self.count, 'valid_frames':sum(r['sample_valid'] for r in self.rows),
            'result':result, 'interrupted':interrupted, 'parquet':dest.name,
            'observed_interval_median_s':float(np.median(np.diff([r['timestamp'] for r in self.rows]))) if self.count>1 else None}
        try:
            pq.write_table(pa.Table.from_pylist(self.rows, schema=_schema()), temporary, compression='zstd')
            metadata['sha256'] = sha256(temporary)
            os.link(temporary, dest)
            _atomic_json(dest.with_suffix('.json'), metadata)  # JSON is the completed-episode commit marker.
        finally:
            temporary.unlink(missing_ok=True)
        self.active = False; self.rows = []
        return dest

    def discard(self):
        self.active = False; self.rows = []


def prepare_vq(source, output, *, window=16, hz=30., max_age_s=.05, val_ratio=.2, seed=42):
    """Build real T-Rex GHandF6Dataset files; no fabricated arm/camera fields.

    Split by object ID before windows/stats. Only five-finger valid contiguous
    windows enter training. The raw source remains intact and unnormalized.
    """
    _, pq = _arrow()
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if source == output or source in output.parents or window < 2 or not math.isfinite(hz) or hz <= 0 or not 0 < val_ratio < 1 or max_age_s <= 0:
        raise ValueError('invalid output/split/window settings')
    episodes = []
    for meta_path in sorted((source/'episodes').glob('episode_*.json')):
        meta = json.loads(meta_path.read_text())
        path = meta_path.with_suffix('.parquet')
        if meta.get('schema') != SCHEMA or sha256(path) != meta['sha256']:
            raise ValueError('raw episode schema/checksum mismatch')
        if meta.get('interrupted') or meta.get('rejected_packets'):
            continue
        episodes.append((meta, path))
    objects = sorted({m['object_id'] for m, _ in episodes})
    if len(objects) < 2:
        raise ValueError('至少需要两个物体编号及完整 episode，才能按物体划分训练/验证')
    shuffled = np.random.default_rng(seed).permutation(objects)
    val_objects = set(shuffled[:min(len(objects)-1,max(1,round(len(objects)*val_ratio)))])
    contract = dict(schema='trex.ghand_tactile_pretrain.v1', purpose='tactile_representation_pretraining_only',
        finger_order=FINGERS, taxel_counts=COUNTS, f6_order=AXES, frame='per_sensor_cad',
        force_unit='N', moment_unit='N m', vqvae_window=window, frame_hz=hz,
        timing='causal_zero_order_hold_from_host_read_completion_not_device_time',
        geometry_sha256=json.loads((source/'meta/dataset.json').read_text())['geometry_sha256'],
        calibration=json.loads((source/'meta/dataset.json').read_text())['calibration'],
        normalization='train_only_per_finger_channel_q01_q99')
    manifest = dict(schema=contract['schema'], contract=contract, source=str(source),
        split_method='object_id_grouped', seed=seed, episodes=[])
    training = []; skipped = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ghand-vq-', dir=output.parent) as temp:
        stage = Path(temp)/'prepared'; (stage/'episodes').mkdir(parents=True)
        common_wrench = None
        for index, (meta, path) in enumerate(episodes):
            rows = pq.read_table(path).to_pylist()
            if len(rows) < window:
                skipped.append(meta['episode_id']); continue
            ts = np.array([r['timestamp'] for r in rows], dtype=float)
            if np.any(np.diff(ts) <= 0):
                raise ValueError('non-increasing raw episode timestamps')
            grid = ts[0]+np.arange(int(np.floor((ts[-1]-ts[0])*hz))+1)/hz
            at = np.searchsorted(ts, grid+1e-10, side='right')-1
            valid = np.array([r['sample_valid'] for r in rows], bool)
            valid_grid = valid[at] & (grid-ts[at] <= max_age_s) & (grid-ts[at] >= -1e-9)
            # Crossing a missing packet or invalid row invalidates a whole window.
            breaks = np.cumsum([int(r['sequence_gap']>0 or not r['sample_valid']) for r in rows])
            starts = []
            for start in range(max(0,len(grid)-window+1)):
                end = start+window-1
                if valid_grid[start:end+1].all() and breaks[at[start]] == breaks[at[end]]:
                    starts.append(start)
            if not starts:
                skipped.append(meta['episode_id']); continue
            wc = meta['wrench_contract']
            semantic = {k:wc[k] for k in ('finger_order','axes','frame','force_unit','moment_unit','reference_point_m')}
            semantic['geometry_sha256'] = wc['source']['geometry_sha256']
            if common_wrench is not None and common_wrench != semantic:
                raise ValueError('cannot mix different wrench geometry/reference conventions')
            common_wrench = semantic
            # Invalid grid rows are NaN and never selected by window_starts.
            f6 = np.full((len(grid),5,6), np.nan, dtype=np.float32)
            for j in np.flatnonzero(valid_grid):
                f6[j] = rows[at[j]]['f6']
            finite_rows = np.isfinite(f6).all(axis=(1,2))
            if not finite_rows[valid_grid].all():
                raise ValueError('F6 overflows float32')
            split = 'val' if meta['object_id'] in val_objects else 'train'
            rel = f'episodes/episode_{index:06d}.npz'
            np.savez_compressed(stage/rel, f6=f6, timestamp=grid, source_timestamp=ts[at],
                frame_index=at, valid=valid_grid, window_starts=np.asarray(starts,dtype=np.int64))
            manifest['episodes'].append(dict(id=index, object_id=meta['object_id'],
                raw_episode_id=meta['episode_id'], raw_sha256=meta['sha256'],
                split=split, npz=rel, sha256=sha256(stage/rel), windows=len(starts), frames=len(grid)))
            if split == 'train':
                used = np.zeros(len(grid),bool)
                for start in starts: used[start:start+window] = True
                training.append(f6[used].reshape(-1,30))
        if not training or not any(e['split']=='val' for e in manifest['episodes']):
            raise ValueError('训练或验证没有完整连续窗口；请增加完整记录，检查丢帧/触觉/F6有效状态')
        train = np.concatenate(training)
        lo, hi = np.quantile(train,[.01,.99],axis=0)
        stats = dict(tacf6_min=lo.tolist(), tacf6_max=hi.tolist(), tacf6_mask=(hi-lo>1e-8).tolist(),
            fit_split='train', fit_frames=len(train))
        _atomic_json(stage/'f6_stats.json',stats)
        manifest['stats_sha256'] = sha256(stage/'f6_stats.json')
        manifest['skipped_episode_ids'] = skipped
        manifest['contract']['wrench_contract'] = common_wrench
        _atomic_json(stage/'tactile_pretrain_manifest.json',manifest)
        if output.exists():
            raise FileExistsError(output)
        stage.rename(output)
    return manifest
