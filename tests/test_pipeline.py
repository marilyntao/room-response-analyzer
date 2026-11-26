import numpy as np
import pytest

from sweepqa.analysis import analyze, AnalysisConfig
from sweepqa.devices import SimulatedIO
from sweepqa.measure import capture, load_wav, save_wav
from sweepqa.spec import evaluate, load_spec
from sweepqa.cli import main

SPEC = "specs/simulated_demo.toml"
FS = 48000


@pytest.fixture(scope="module")
def measured():
    spec = load_spec(SPEC)
    io = SimulatedIO(FS)
    sw, amp, rec, noise = capture(io, spec)
    return spec, sw, amp, rec, noise, analyze(rec, noise, sw, amp, lead_in_s=0.5)


def at(an, f, arr):
    return float(np.interp(np.log(f), np.log(an.freq), arr))


def tone_thd(io, f, amp, k=9):
    """Independent reference: THD of a steady tone through the same device (no noise)."""
    io.noise_rms = 0.0
    n = FS * 2
    x = amp * np.sin(2 * np.pi * f * np.arange(n) / FS)
    y = io.play_record(x)[FS // 2:]
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    fr = np.fft.rfftfreq(len(y), 1 / FS)
    pk = lambda ff: spec[np.argmin(np.abs(fr - ff))]
    return np.sqrt(sum(pk(h * f) ** 2 for h in range(2, k + 1))) / pk(f)


def test_delay_recovered(measured):
    *_, an = measured
    assert an.delay_ms == pytest.approx(9.5, abs=0.1)


def test_gain_matches_device(measured):
    *_, an = measured
    # Reference: fundamental of a 1 kHz tone at the same level through the same device (tanh compresses it).
    spec, sw, amp, *_ = measured
    io = SimulatedIO(FS); io.noise_rms = 0.0
    x = amp * np.sin(2 * np.pi * 1000 * np.arange(FS * 2) / FS)
    y = io.play_record(x)[FS // 2:]
    k = np.fft.rfft(y * np.hanning(len(y)))
    ref_db = 20 * np.log10(np.abs(k[np.argmax(np.abs(k))]) / np.abs(np.fft.rfft(x[FS // 2:] * np.hanning(len(y)))).max())
    assert at(an, 1000, an.gain_db) == pytest.approx(ref_db, abs=0.3)


def test_highpass_corner(measured):
    *_, an = measured
    # 2nd-order Butterworth: -3 dB at 40 Hz relative to passband
    rel = an.gain_db - at(an, 1000, an.gain_db)
    assert at(an, 40, rel) == pytest.approx(-3.0, abs=0.7)


@pytest.mark.parametrize("f", [250, 1000, 4000])
def test_thd_matches_tone_method(measured, f):
    spec, sw, amp, rec, noise, an = measured
    ref = 100 * tone_thd(SimulatedIO(FS), f, amp)
    got = at(an, f, an.thd_pct)
    assert got == pytest.approx(ref, rel=0.15), (got, ref)


def test_snr_matches_noise_level(measured):
    *_, an = measured
    assert an.noise_dbfs == pytest.approx(20 * np.log10(3e-5 * np.sqrt(19980 / 24000)), abs=0.5)
    assert an.snr_db == pytest.approx(an.signal_dbfs - an.noise_dbfs)


def test_spec_pass_and_fail(measured):
    spec, *_, an = measured
    assert all(c.passed for c in evaluate(an, spec))
    spec["limits"]["thd"]["bands"][0]["max_percent"] = 0.1       # too tight for this distorting device
    spec["limits"]["snr"]["min_db"] = 90
    failed = {c.name for c in evaluate(an, spec) if not c.passed}
    assert failed == {"THD 100-5000 Hz", "SNR (in-band)"}


def test_band_outside_range_fails(measured):
    spec, *_, an = measured
    spec["limits"]["thd"]["bands"] = [{"f_lo": 30000, "f_hi": 40000, "max_percent": 1}]
    assert [c.passed for c in evaluate(an, spec) if c.name.startswith("THD")] == [False]


def test_misaligned_recording_raises(measured):
    spec, sw, amp, rec, noise, _ = measured
    with pytest.raises(ValueError):
        analyze(rec[::-1].copy()[: sw.n // 2], noise, sw, amp)   # nonsense input must not silently pass


def test_offline_roundtrip_and_exit_code(tmp_path):
    spec = load_spec(SPEC)
    sw, amp, rec, noise = capture(SimulatedIO(FS), spec)
    save_wav(tmp_path / "s.wav", rec, FS)
    save_wav(tmp_path / "n.wav", noise, FS)
    assert load_wav(tmp_path / "s.wav")[1] == FS
    out = tmp_path / "out"
    assert main(["analyze", SPEC, "--sweep", str(tmp_path / "s.wav"), "--noise", str(tmp_path / "n.wav"),
                 "--out", str(out)]) == 0
    assert (out / "result.json").exists() and (out / "response.png").exists() and (out / "response.csv").exists()


def test_cli_nonzero_exit_on_fail(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text(open(SPEC).read().replace("min_db = 50", "min_db = 120"))
    assert main(["run", str(bad), "--simulate", "--out", str(tmp_path / "o")]) == 1
