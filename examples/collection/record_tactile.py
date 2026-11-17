#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Passive, tactile-only collection from an existing hand teleoperation owner.

No SDK device is opened; localhost UDP receive only. See docs/TACTILE_ONLY_COLLECTION.md.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import queue
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from ghand.recording import (CaptureSession, DEFAULT_GEOMETRY, FINGERS,
                             decode_packet, prepare_vq, sha256)
from ghand.recording_keys import KEY_HELP, TerminalCommands
from ghand.recording_probe import ProbeBuffer


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='operation', required=True)
    for name in ('record', 'replay'):
        c = sub.add_parser(name, help='接收本机遥测' if name=='record' else '离线 JSONL 回放，不连接设备')
        c.add_argument('--root', type=Path, required=True)
        c.add_argument('--object', dest='object_id', required=True, help='物体实体/家族编号，用于划分，不输入网络')
        c.add_argument('--pose', default='pinch')
        c.add_argument('--fingers', nargs='+', choices=FINGERS, default=['THUMB','FF','MF'])
        c.add_argument('--geometry', type=Path, default=DEFAULT_GEOMETRY)
        c.add_argument('--max-age', type=float, default=.15, help='本机接收时距 SDK 读完成的最大年龄，秒')
        c.add_argument('--max-samples', type=int, default=20000)
        if name == 'record':
            c.add_argument('--port', type=int, default=5558)
            c.add_argument('--protocol', choices=('probe','detailed'), default='probe',
                           help='probe: 自动缓存空载/接触，s开始轻压、n保存；detailed: s从空载开始记录')
            c.add_argument('--input-mode', choices=('auto','keys','line'), default='auto',
                           help='默认交互终端使用单键；line 保留命令加回车方式')
        else:
            c.add_argument('--input', type=Path, required=True, help='每行 {"packet": 遥测对象, "received_at": 原接收单调时间}')
    c = sub.add_parser('prepare', help='离线转换为 T-Rex 纯触觉 VQ-VAE 数据')
    c.add_argument('--source', type=Path, required=True)
    c.add_argument('--output', type=Path, required=True)
    c.add_argument('--window', type=int, default=16)
    c.add_argument('--hz', type=float, default=30.)
    c.add_argument('--max-age', type=float, default=.05)
    c.add_argument('--val-ratio', type=float, default=.2)
    c.add_argument('--seed', type=int, default=42)
    return p


def _save(session, **kwargs):
    path = session.save(**kwargs)
    print(f'已保存：{path}', flush=True)
    info = json.loads(path.with_suffix('.json').read_text())
    print(f"总帧={info['frames']} 有效帧={info['valid_frames']} 丢包={info['missing_packets']} 重复={info['duplicates']}", flush=True)
    return path


def _replay(args, session):
    session.start(object_id=args.object_id, pose_id=args.pose, active_fingers=args.fingers)
    session.info.update(collection_mode='offline_jsonl_replay', source_sha256=sha256(args.input))
    try:
        with args.input.open(encoding='utf-8') as source:
            for line in source:
                if not line.strip():
                    continue
                record = json.loads(line)
                session.add(record['packet'], float(record['received_at']),
                            phase=record.get('phase','unmarked'), max_age_s=args.max_age)
        _save(session, result='offline_replay')
    except BaseException:
        if session.active and session.count:
            _save(session, interrupted=True, result='replay_error')
        raise


def _record(args, session):
    events = queue.Queue()
    pre_roll = ProbeBuffer()
    # Bind without SO_REUSE*: fail clearly if the full recorder already owns this port.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, TerminalCommands(events, args.input_mode) as keyboard:
        try:
            sock.bind(('127.0.0.1', args.port))
        except OSError as exc:
            raise RuntimeError(f'无法监听 127.0.0.1:{args.port}：{exc}；请退出占用同一遥测端口的旧采集器，或使用独立端口') from exc
        sock.settimeout(.1)
        print(f'监听本机 UDP 127.0.0.1:{args.port}，等待现有手套遥操反馈；不连接设备、不发送控制指令。', flush=True)
        print(KEY_HELP if keyboard.mode=='keys' else '命令模式（按回车）：s 开始轻压 / n 保存成功 / w failure 保存失败 / object 名称 / preset 3 / q。', flush=True)
        print('当前协议：'+args.protocol+('；s从空载开始，加载前按l，结束按n。' if args.protocol=='detailed' else '；先保持真手空载约1秒，等待缓存就绪后再接触。'), flush=True)
        phase = 'free'; latest = None; last_status = time.monotonic()
        try:
            while True:
                while not events.empty():
                    command = events.get_nowait(); parts = command.split()
                    if not parts:
                        continue
                    op = parts[0]
                    try:
                        if op == 'q':
                            return
                        if op == 's':
                            if session.active:
                                raise ValueError('当前记录未结束，请按 n 或 f 保存')
                            if latest is None or time.monotonic()-latest[0]>.5 or not latest[1]['sample_valid']:
                                raise ValueError('没有新鲜有效的五指触觉/F6；检查遥操反馈和最近一条质量提示')
                            history = pre_roll.snapshot() if args.protocol=='probe' else []
                            if len(history)>=session.max_samples:
                                raise ValueError('缓存已超过单条帧上限，请增加 --max-samples')
                            session.start(object_id=args.object_id, pose_id=args.pose, active_fingers=args.fingers)
                            try:
                                for packet, received, prior_phase in history:
                                    session.add(packet, received, phase=prior_phase, max_age_s=args.max_age)
                            except (ValueError, RuntimeError):
                                session.discard();pre_roll.reset();raise
                            session.info.update(collection_protocol=args.protocol,
                                pre_roll_frames=len(history),probe_start_monotonic=time.monotonic(),
                                pre_roll_free_force_threshold_n=pre_roll.free_force_n if history else None)
                            pre_roll.reset()
                            session.info['collection_mode'] = 'localhost_udp_teleoperation'
                            phase = 'loading' if args.protocol=='probe' else 'free'
                            print(f'开始记录：物体={args.object_id} 姿态={args.pose} 手指={args.fingers}', flush=True)
                        elif op in ('w','n'):
                            _save(session, result='success' if op=='n' else (' '.join(parts[1:]) or 'unspecified'))
                            pre_roll.reset()
                        elif op == 'd':
                            session.discard(); pre_roll.reset(); print('已丢弃当前未保存记录。', flush=True)
                        elif op == 'help':
                            print(KEY_HELP, flush=True)
                        elif op == 'preset' and len(parts)==2 and parts[1] in ('2','3','4','5'):
                            if session.active:
                                raise ValueError('请先保存或丢弃当前记录，再切换选指组合')
                            pre_roll.reset()
                            n = int(parts[1])
                            args.fingers = list(FINGERS[:n])
                            args.pose = {2:'two_finger',3:'three_finger',4:'four_finger',5:'five_finger'}[n]
                            print(f'下一条：{args.object_id} / {args.pose} / {args.fingers}（仅记录配置，不控制手）', flush=True)
                        elif op == 'phase' and len(parts)==2:
                            phase = parts[1]; print(f'阶段={phase}', flush=True)
                        elif op in ('object','pose','fingers') and len(parts)>1:
                            if session.active:
                                raise ValueError('请先保存或丢弃当前记录，再修改实验配置')
                            if op == 'object': args.object_id = ' '.join(parts[1:])
                            elif op == 'pose': args.pose = ' '.join(parts[1:])
                            else:
                                if not set(parts[1:]) <= set(FINGERS) or len(set(parts[1:]))!=len(parts[1:]):
                                    raise ValueError(f'手指须为唯一的 {FINGERS}')
                                args.fingers = parts[1:]
                            pre_roll.reset()
                            print(f'下一条：{args.object_id} / {args.pose} / {args.fingers}', flush=True)
                        else:
                            print('未知命令；使用 s / n / w / d / phase / object / pose / fingers / q。', flush=True)
                    except (ValueError, RuntimeError) as exc:
                        print(f'操作未执行：{exc}', file=sys.stderr, flush=True)
                try:
                    raw, _ = sock.recvfrom(65535)
                except socket.timeout:
                    raw = None
                if raw is not None:
                    received = time.monotonic()
                    try:
                        packet = json.loads(raw)
                        row = decode_packet(packet, received, geometry_sha256=session.geometry_hash, max_age_s=args.max_age)
                        latest = (received, row)
                        if session.active:
                            session.add(packet, received, phase=phase, max_age_s=args.max_age)
                        elif args.protocol=='probe':
                            was_ready=pre_roll.ready
                            pre_roll.observe(packet,row,received)
                            if pre_roll.ready and not was_ready:
                                print('空载缓存就绪；全部参与指稳定轻接触后按 s 开始轻压，结束按 n。',flush=True)
                    except (ValueError, KeyError, TypeError, OverflowError, RuntimeError) as exc:
                        event = dict(received_at=received, reason=str(exc), datagram_hex=raw.hex())
                        with (session.root/'rejected_packets.jsonl').open('a', encoding='utf-8') as f:
                            f.write(json.dumps(event,ensure_ascii=False)+'\n')
                        print(f'遥测异常：{exc}', file=sys.stderr, flush=True)
                        latest = None
                        pre_roll.reset()
                        if session.active:
                            session.info['rejected_packets'] += 1
                            if session.count:
                                _save(session, interrupted=True, result='telemetry_error')
                            else:
                                session.discard()
                now = time.monotonic()
                if now-last_status >= 3:
                    last_status = now
                    if latest is None or now-latest[0]>.5:
                        status = '遥测已超时/尚未收到；检查发送端 --telemetry-host 127.0.0.1'
                    else:
                        status = '触觉/F6有效' if latest[1]['sample_valid'] else latest[1]['quality_issues']
                    if not session.active and args.protocol=='probe':
                        status += '；'+('空载历史已缓存' if pre_roll.ready else '等待空载约1秒')
                    print(f"{'记录中' if session.active else '待机'} 帧={session.count} 阶段={phase}；{status}",flush=True)
        finally:
            # Preserve interrupted data for inspection, excluded from default training export.
            if session.active and session.count:
                _save(session, interrupted=True, result='quit_or_interrupt')


def main(argv=None):
    p = parser(); args = p.parse_args(argv)
    if args.max_age <= 0 or not math.isfinite(args.max_age):
        p.error('--max-age 必须是正的有限数')
    if args.operation in ('record','replay') and args.max_samples < 1:
        p.error('--max-samples 必须大于0')
    if args.operation == 'record' and not 1 <= args.port <= 65535:
        p.error('--port 必须在1–65535范围内')
    try:
        if args.operation == 'prepare':
            m = prepare_vq(args.source,args.output,window=args.window,hz=args.hz,
                max_age_s=args.max_age,val_ratio=args.val_ratio,seed=args.seed)
            print(json.dumps({'output':str(args.output),'episodes':len(m['episodes']),
                'windows':sum(e['windows'] for e in m['episodes']),
                'skipped':m['skipped_episode_ids']},ensure_ascii=False,indent=2))
        else:
            session = CaptureSession(args.root,geometry=args.geometry,max_samples=args.max_samples)
            if args.operation == 'record': _record(args,session)
            else: _replay(args,session)
    except KeyboardInterrupt:
        print('已停止记录；遥操控制进程独立运行，请在原控制界面停止动作。',file=sys.stderr)
        return 130
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f'采集/转换失败：{exc}',file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
