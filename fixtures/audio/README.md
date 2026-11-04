# fixtures/audio — scripted ASR test clips (1B1)

Scripted Spanish dictations only (no real patient data), mono 16-bit 16 kHz WAV, ≤ 10 s each.
Used by `scripts/asr_probe.py` and the opt-in live test `api/tests/test_asr_live.py`
(the first `*.wav` here, or `MUSE_LIVE_WAV`).

Make one on macOS:

```bash
say -v Paulina -o /tmp/c.aiff "Paciente de 68 años, vértigo continuo hace 12 horas, sin diplopía."
```

```bash
afconvert -f WAVE -d LEI16@16000 -c 1 /tmp/c.aiff fixtures/audio/caso_b_01.wav
```
