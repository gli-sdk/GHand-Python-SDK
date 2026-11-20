"""Two-key collection history tests; no hardware."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('capture_fixture',Path(__file__).with_name('test_tactile_recording.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def observe(buffer,seq,force=0.,**changes):
    packet=fixture.packet(seq=seq,force=force)
    packet.update(changes)
    row=fixture.decode_packet(packet,100+seq/80+.01,geometry_sha256=fixture.GEOHASH)
    buffer.observe(packet,row,100+seq/80+.01)


def test_probe_has_real_free_history_then_contact():
    from ghand.recording_probe import ProbeBuffer
    buf=ProbeBuffer()
    for seq in range(90):observe(buf,seq)
    assert buf.ready
    for seq in range(90,120):observe(buf,seq,.02)
    history=buf.snapshot()
    assert history[0][2]=='free' and history[-1][2]=='contact'
    assert history[0][0]['sequence']<90
    assert [item[0]['sequence'] for item in history]==list(range(history[0][0]['sequence'],120))
    assert buf.ready
    buf.reset();assert not buf.ready
    for seq in range(120,140):observe(buf,seq,.02)
    with pytest.raises(ValueError,match='空载'):buf.snapshot()


def test_gap_device_change_and_expiration_drop_baseline():
    from ghand.recording_probe import ProbeBuffer
    for change in ('gap','device','expired'):
        buf=ProbeBuffer(max_seconds=2.)
        for seq in range(90):observe(buf,seq)
        assert buf.ready
        if change=='gap':observe(buf,95,.02)
        elif change=='device':observe(buf,90,.02,device={'serial_number':999,'hand_side':'left'})
        else:
            for seq in range(90,270):observe(buf,seq,.02)
        assert not buf.ready


def test_n_is_success_and_w_no_longer_a_shortcut():
    from ghand.recording_keys import KeyDecoder
    assert KeyDecoder().feed('nNw')==['w success','w success']
