"""PROTOTYPE, throw away. Render a preset tree through Apple's AU hosting.

The recipe from "Prove the whole loop on a few simple sounds", unchanged:
no warmup, 1 s of silence, everything rebuilt for each render, main thread.
"""
import struct

import AVFoundation as AV
import numpy as np
import serum2_preset_loader as s
from Foundation import NSData, NSDate, NSMutableDictionary, NSRunLoop

SR, BLOCK = 44100.0, 512
HELD, TAIL = 2.0, 1.0
NOTES = {"bass": 36, "synth": 48, "lead": 60}  # heard note: MIDI 48 is C3


def fc(c):
    return struct.unpack(">I", c.encode())[0]


def render_tree(tree, note, velocity=100, path="prototype.SerumPreset"):
    box = {}
    AV.AVAudioUnit.instantiateWithComponentDescription_options_completionHandler_(
        (fc("aumu"), fc("Xf2X"), fc("XFER"), 0, 0), 0, lambda u, e: box.update(unit=u)
    )
    while "unit" not in box:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.001))
    unit = box["unit"]
    au = unit.AUAudioUnit()

    engine = AV.AVAudioEngine.alloc().init()
    fmt = AV.AVAudioFormat.alloc().initStandardFormatWithSampleRate_channels_(SR, 2)
    engine.enableManualRenderingMode_format_maximumFrameCount_error_(
        AV.AVAudioEngineManualRenderingModeOffline, fmt, BLOCK, None
    )
    engine.attachNode_(unit)
    engine.connect_to_format_(unit, engine.mainMixerNode(), fmt)
    engine.startAndReturnError_(None)
    buf = AV.AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(fmt, BLOCK)

    def play(seconds):
        out, left = [], int(seconds * SR)
        while left > 0:
            n = min(BLOCK, left)
            engine.renderOffline_toBuffer_error_(n, buf, None)
            ch = buf.floatChannelData()
            out.append(np.stack([np.frombuffer(ch[c].as_buffer(n), dtype=np.float32).copy() for c in (0, 1)]))
            left -= n
        return np.concatenate(out, axis=1)

    if tree is not None:  # None plays Serum as it opens, with nothing loaded
        proc, ctrl = s.build_processor_state(tree), s.build_controller_state(tree, path)
        state = NSMutableDictionary.dictionaryWithDictionary_(au.fullState())
        state["Processor State"] = NSData.dataWithBytes_length_(proc, len(proc))
        state["Controller State"] = NSData.dataWithBytes_length_(ctrl, len(ctrl))
        state.removeObjectForKey_("data")
        au.setFullState_(state)
    play(1.0)  # 1 s of silence first

    unit.startNote_withVelocity_onChannel_(note, velocity, 0)
    held = play(HELD)
    unit.stopNote_onChannel_(note, 0)
    tail = play(TAIL)
    engine.stop()
    return np.concatenate([held, tail], axis=1)


def render_file(path, note, velocity=100):
    _, tree = s.decode_preset_file(path)
    return render_tree(tree, note, velocity, path)
