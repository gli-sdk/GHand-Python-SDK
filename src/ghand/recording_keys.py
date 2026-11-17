# SPDX-License-Identifier: Apache-2.0
"""Local terminal shortcuts for the passive recorder; no global keyboard hooks."""
from __future__ import annotations

import codecs
import os
import select
import signal
import sys
import threading

KEY_HELP = ('两键采集：空载约1秒自动缓存 → 全参与指稳定轻接触 → s 开始轻压 → n 结束并保存成功\n'
            'f 结束并保存失败 | q 退出 | 2/3/4/5 下一条选指 | o 改物体 | p 改姿态 | ? 帮助\n'
            '可选细分：c 接触 | l 加载 | h 保持 | u 卸载 | r 释放 | 0 空载 | v 滑动 | b 滚动 | d 丢弃\n'
            '文字设置按回车，Esc取消；仅操作记录，不控制手。--protocol detailed 可用原逐阶段流程。')
SHORTCUTS = dict(s='s',c='phase contact',l='phase loading',h='phase hold',
    u='phase unloading',r='phase release',n='w success',f='w failure',d='d',q='q',
    v='phase slip',b='phase rolling',**{'0':'phase free','?':'help'})
SHORTCUTS.update({str(n):f'preset {n}' for n in (2,3,4,5)})


class KeyDecoder:
    """Incremental parser. Text-edit mode consumes shortcuts until Enter/Escape."""
    def __init__(self,write=None):
        self.edit=None;self.escape='';self.paste=False;self.write=write or (lambda _:None)

    def feed(self,text):
        commands=[]
        for ch in text:
            if self.escape:
                self.escape+=ch
                if self.escape in ('\x1b[','\x1bO'):continue
                if self.escape.startswith(('\x1b[','\x1bO')):
                    if not ('@'<=ch<='~'):continue
                    if self.escape=='\x1b[200~':self.paste=True
                    elif self.escape=='\x1b[201~':self.paste=False
                    self.escape='';continue
                self.escape=''
                # A lone Escape cancels editing, but must not eat the next key.
            if ch=='\x1b':
                self.escape=ch
                if self.edit is not None:self.edit=None;self.write('\n已取消文字输入。\n')
                continue
            if self.paste:continue
            if self.edit is not None:
                if ch in '\r\n':
                    if self.edit.strip():commands.append(self.edit.strip())
                    self.edit=None;self.write('\n')
                elif ch in ('\x7f','\b'):
                    self.edit=self.edit[:-1];self.write('\r\x1b[2K命令> '+self.edit)
                elif ch.isprintable():self.edit+=ch;self.write(ch)
                continue
            key=ch.lower()
            if key in ('o','p',':'):
                self.edit={'o':'object ','p':'pose ',':':''}[key]
                self.write('\n命令> '+self.edit)
            elif key in SHORTCUTS:commands.append(SHORTCUTS[key])
        return commands


class TerminalCommands:
    """Restore terminal settings on normal exit, exceptions, Ctrl+C and TERM."""
    def __init__(self,events,mode='auto',*,stream=None,output=sys.stdout):
        self.events=events;self.requested=mode;self.stream=stream or sys.stdin
        self.output=output;self.stop=threading.Event();self.saved=None;self.old_term=None
        self.thread=None

    def _write(self,text):
        if self.output is not None:
            self.output.write(text);self.output.flush()

    def __enter__(self):
        self.fd=self.stream.fileno()
        self.mode=('keys' if self.stream.isatty() and os.name=='posix' else 'line') if self.requested=='auto' else self.requested
        if self.mode=='keys' and (not self.stream.isatty() or os.name!='posix'):
            raise ValueError('单键模式需要 Linux/macOS 交互终端；非终端请用 --input-mode line')
        try:
            if self.mode=='keys':
                import termios
                import tty
                self.saved=termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd,termios.TCSANOW)
                self._write('\x1b[?2004h')  # Ignore bracketed paste instead of executing pasted keys.
            if threading.current_thread() is threading.main_thread():
                self.old_term=signal.getsignal(signal.SIGTERM)
                signal.signal(signal.SIGTERM,self._interrupt)
            self.thread=threading.Thread(target=self._read,daemon=True)
            self.thread.start()
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    @staticmethod
    def _interrupt(*_):
        raise KeyboardInterrupt

    def _read(self):
        decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
        keys=KeyDecoder(self._write);line=''
        try:
            while not self.stop.is_set():
                if not select.select([self.fd],[],[],.1)[0]:continue
                chunk=os.read(self.fd,4096)
                if not chunk:self.events.put('q');return
                text=decoder.decode(chunk)
                if self.mode=='keys':commands=keys.feed(text)
                else:
                    line+=text;parts=line.split('\n');line=parts.pop()
                    commands=[part.strip() for part in parts]
                for command in commands:
                    self.events.put(command)
                    if command=='q':return
        except (OSError,ValueError):
            if not self.stop.is_set():self.events.put('q')

    def __exit__(self,*_):
        self.stop.set()
        if self.thread is not None:self.thread.join(timeout=.5)
        try:
            if self.saved is not None:
                import termios
                termios.tcsetattr(self.fd,termios.TCSANOW,self.saved)
                self.saved=None
                self._write('\x1b[?2004l')
        finally:
            if self.old_term is not None:
                signal.signal(signal.SIGTERM,self.old_term)
                self.old_term=None
