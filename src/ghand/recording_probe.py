# SPDX-License-Identifier: Apache-2.0
"""Bounded pre-trigger history for two-key probing; never commands hardware."""
from collections import deque
import json
import numpy as np


class ProbeBuffer:
    def __init__(self,free_seconds=1.,max_seconds=15.,free_force_n=.15,max_packets=2000):
        self.free_seconds=free_seconds;self.max_seconds=max_seconds
        self.free_force_n=free_force_n;self.max_packets=max_packets
        self.reset()

    def reset(self):
        self.history=deque();self.ready=False;self.contacted=False
        self.previous=None;self.contract=None

    def observe(self,packet,row,received):
        if not row['sample_valid']:
            self.reset();return
        seq=row['sequence'];ts=row['timestamp']
        signature=json.dumps([packet.get('device'),packet['tactile'].get('wrench') and
            {k:v for k,v in packet['tactile']['wrench'].items() if k not in ('f6','valid')}],sort_keys=True)
        if self.previous is not None:
            old_seq,old_ts=self.previous
            if seq!=old_seq+1 or not 0<ts-old_ts<=.06 or signature!=self.contract:self.reset()
        self.previous=(seq,ts);self.contract=signature
        # Conservative low-load check; the operator must actually unload the hand.
        force=np.asarray(row['distributed_force'],float)
        unloaded=bool(np.max(np.linalg.norm(force,axis=2).sum(axis=1))<=self.free_force_n)
        if unloaded and self.contacted:
            self.history.clear();self.ready=False;self.contacted=False
        if not self.ready:
            if not unloaded:
                self.history.clear();return
            self.history.append((packet,received,'free'))
            self.ready=ts-self.history[0][0]['acquired_monotonic']>=self.free_seconds
        elif unloaded:
            self.history.append((packet,received,'free'))
        else:
            self.contacted=True
            self.history.append((packet,received,'contact'))
        if unloaded:
            while len(self.history)>2 and ts-self.history[1][0]['acquired_monotonic']>=self.free_seconds:
                self.history.popleft()
        if self.history and (ts-self.history[0][0]['acquired_monotonic']>self.max_seconds or len(self.history)>self.max_packets):
            self.reset()

    def snapshot(self):
        if not self.ready:
            raise ValueError('空载历史未就绪：先完全离开物体保持约1秒，再接触；不要带载启动或中途清零')
        return list(self.history)
