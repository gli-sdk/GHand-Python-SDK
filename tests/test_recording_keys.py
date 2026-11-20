"""PTY tests: real terminal input, no device or teleop process."""
import os
import queue
import termios
import time

import pytest


def test_shortcuts_and_editing_do_not_require_enter():
    from ghand.recording_keys import KeyDecoder
    decoder=KeyDecoder()
    assert decoder.feed('sclhurnf23')==['s','phase contact','phase loading','phase hold',
        'phase unloading','phase release','w success','w failure','preset 2','preset 3']
    assert decoder.feed('o海绵_01')==[]
    assert decoder.feed('\x7f2\r')==['object 海绵_02']
    assert decoder.feed(':fingers THUMB FF\n')==['fingers THUMB FF']
    assert decoder.feed('o放弃\x1b')==[]
    assert decoder.feed('s')==['s']


def test_escape_keys_and_paste_do_not_invoke_actions():
    from ghand.recording_keys import KeyDecoder
    decoder=KeyDecoder()
    assert decoder.feed('\x1b[A\x1b[B\x1b[3~\x1bOP')==[]
    assert decoder.feed('\x1b[200~swdqphase loading\n')==[]
    assert decoder.feed('\x1b[201~')==[]
    assert decoder.feed('l')==['phase loading']


def test_pty_immediate_key_and_terminal_restored_on_error():
    from ghand.recording_keys import TerminalCommands
    master,slave=os.openpty()
    stream=os.fdopen(os.dup(slave),'r',encoding='utf-8')
    events=queue.Queue();before=termios.tcgetattr(slave)
    try:
        with pytest.raises(RuntimeError):
            with TerminalCommands(events,stream=stream,output=None) as reader:
                assert reader.mode=='keys'
                os.write(master,b's')
                assert events.get(timeout=1)=='s'
                # Typing an object name does not stop the main acquisition thread.
                os.write(master,'o海绵'.encode())
                time.sleep(.04)
                assert events.empty()
                os.write(master,b'\r')
                assert events.get(timeout=1)=='object 海绵'
                raise RuntimeError('simulated recorder error')
        assert termios.tcgetattr(slave)==before
        assert not reader.thread.is_alive()
    finally:
        stream.close();os.close(master);os.close(slave)


def test_line_mode_and_signal_handler_restoration():
    import signal
    from ghand.recording_keys import TerminalCommands
    read_fd,write_fd=os.pipe();events=queue.Queue()
    before=signal.getsignal(signal.SIGTERM)
    with os.fdopen(read_fd,'r') as stream:
        with TerminalCommands(events,stream=stream,output=None) as reader:
            assert reader.mode=='line'
            os.write(write_fd,b'phase loading\nq\n')
            assert events.get(timeout=1)=='phase loading'
            assert events.get(timeout=1)=='q'
    os.close(write_fd)
    assert signal.getsignal(signal.SIGTERM)==before


@pytest.mark.parametrize('protocol',['detailed','probe'])
def test_real_recorder_keys_with_synthetic_udp(tmp_path,protocol):
    import importlib.util
    import json
    from pathlib import Path
    import socket
    import subprocess
    import sys
    import threading
    import pyarrow.parquet as pq

    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('capture_fixture',root/'tests/test_tactile_recording.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    master,slave=os.openpty();before=termios.tcgetattr(slave)
    stop=threading.Event();contact=threading.Event()
    def send():
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            seq=0
            while not stop.is_set():
                now=time.monotonic();p=fixture.packet(seq=seq,base=now-.01-seq/80,force=.1 if protocol=='detailed' or contact.is_set() else 0.)
                sock.sendto(json.dumps(p).encode(),('127.0.0.1',port));seq+=1;stop.wait(.0125)
    thread=threading.Thread(target=send,daemon=True);thread.start()
    log=(tmp_path/'recorder.log').open('w+')
    proc=subprocess.Popen([sys.executable,str(root/'examples/collection/record_tactile.py'),
        'record','--root',str(tmp_path/'raw'),'--object','foam','--fingers','THUMB','FF',
        '--port',str(port),'--protocol',protocol],stdin=slave,stdout=log,stderr=log)
    def wait_for(text):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            log.flush();content=(tmp_path/'recorder.log').read_text()
            if text in content:return
            if proc.poll() is not None:raise AssertionError(content)
            time.sleep(.02)
        raise AssertionError((tmp_path/'recorder.log').read_text())
    try:
        wait_for('监听本机 UDP');time.sleep(.15)
        if protocol=='probe':
            wait_for('空载缓存就绪');contact.set();time.sleep(.35)
        os.write(master,b's');wait_for('开始记录')
        if protocol=='detailed':
            for key,phase in [('c','contact'),('l','loading'),('h','hold'),('u','unloading'),('r','release')]:
                os.write(master,key.encode());wait_for('阶段='+phase);time.sleep(.06)
        else:
            time.sleep(.35)
        os.write(master,b'n');wait_for('已保存')
        os.write(master,b'3');wait_for('three_finger')
        os.write(master,b'q');assert proc.wait(timeout=5)==0
        info=json.loads(next((tmp_path/'raw/episodes').glob('*.json')).read_text())
        if protocol=='probe':
            assert info['pre_roll_frames']>80
            assert info['collection_protocol']=='probe'
        assert info['result']=='success' and info['active_fingers']==['THUMB','FF']
        table=pq.read_table(tmp_path/'raw/episodes'/info['parquet']).to_pylist()
        expected={'free','contact','loading'} if protocol=='probe' else {'contact','loading','hold','unloading','release'}
        assert expected <= {row['phase'] for row in table}
        assert termios.tcgetattr(slave)==before
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
        stop.set();thread.join(timeout=1);log.close();os.close(master);os.close(slave)
