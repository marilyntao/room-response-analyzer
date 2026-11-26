sweepqa

Plays an exponential (log) sine sweep, records it with sounddevice, then computes frequency response, THD and SNR and checks them against limits in a TOML spec. Exit code is 0 on PASS, 1 on FAIL, so it can run in a script or CI. Optionally plays the sweep through a parametric EQ (--eq) so a before/after pair can be measured with the same tool.

pip install -e .[dev]
python -m sweepqa list-devices
python -m sweepqa probe SPEC                                   # which input channel hears which output
python -m sweepqa run SPEC --out results/NAME                  # hardware
python -m sweepqa run SPEC --delay 10 --out results/NAME       # wait 10 s so you can leave the room
python -m sweepqa run SPEC --delay 10 --eq eq_design.csv --out results/NAME_after
python -m sweepqa run specs/simulated_demo.toml --simulate     # no hardware
python -m sweepqa analyze SPEC --sweep sweep_recording.wav --noise noise_recording.wav
python rt60_analysis.py results/ESA_A results/ESA_B --plots A  # RT60 / EDT / C80 from saved recordings
pytest
Workflow used in the project
Set up the interface (see "Hardware notes"). Run list-devices, put the device index in [device], and run probe to find which input channel your mic is on.
Loopback (specs/loopback_interface.toml): cable an output to an input. This shows the interface itself meets the limits, so later failures are the loudspeaker or room.
Level check: one run into results/test_level. Aim for a peak near -12 dBFS and SNR of at least 35-40 dB, with no clipping. Then leave speaker level, mic gain and interface settings alone for the whole session.
"Before" runs at every mic position, with a repeat at the reference position to check repeatability.
Design the EQ from the reference position (cuts only; see "EQ design"), then "after" runs at the same positions with --eq.
Compare before and after at every position, not just at the design position.

Set input, output (names or indexes from list-devices) and out_ch / in_ch (1-based) under [device]. A device index of 0 is valid; it is not the same as "unset".

What it does
Capture (measure.py): pre_s of silence, sweep, tail_s of tail, then a separate noise capture with silence played (noise_s). Both recordings are saved as WAV so you can re-analyse later without the hardware.
EQ playback (eq.py): --eq FILE.csv (columns f0_hz,gain_db,q) applies RBJ peaking biquads to the played sweep. The analysis still uses the original inverse filter, so the result shows the EQ's effect in the room.
Frequency response: Farina deconvolution gives the impulse response; its spectrum is smoothed (smoothing_octave, power average). Judged relative to ref_hz (uncalibrated mic) or absolute (loopback).
THD: the nonlinear products of a log sweep land in time before the linear impulse response. The k-th harmonic's response is cut out, and THD(f) = sqrt(sum_k |Hk(k f)|^2) / |H1(f)|. Harmonics up to max_harmonic are included (harmonics_used in the CSV). Frequencies with no usable harmonic are left blank (NaN), not reported as 0 %.
SNR: in-band (f1 to f2) RMS of the recorded sweep over its active part, divided by the in-band RMS of the noise capture, in dB.
Sanity checks: peak level (clipping) and latency.
Outputs per run (--out): result.json, response.csv (freq, gain, THD, harmonics used), response.png, sweep_recording.wav, noise_recording.wav.
Limits to know about
Without a calibrated microphone, levels are relative. SNR is a ratio, so it is still valid.
THD is only trustworthy where the harmonics were actually played. A sweep from f1 to f2 excites nothing above f2, so the k-th harmonic of a frequency f is real only if k·f ≤ f2. For the second harmonic that means THD is valid up to f2/2. Above that the curve falls to a meaningless floor (we saw ~0.001 %). Set the THD bands accordingly, or sweep higher.
THD is inflated at response nulls. At a deep room null the fundamental is cancelled at the mic but its harmonics are not, so THD rises sharply exactly where the response dips. Read THD next to the response curve before blaming the loudspeaker.
THD also includes the noise in each harmonic segment, so it has a floor set by SNR.
THD is measured at one drive level only (level_dbfs). Datasheet THD figures are given at a stated SPL; a limit taken from one is only valid if your level is no higher.
The "low corner" check can fail for the wrong reason. It looks for where the response crosses the corner level, so a narrow dip well above the real rolloff can trigger it. Check the curve, and consider a smoothed curve for that check.
The ref_hz reference is a single point. A narrow peak or dip at ref_hz shifts the whole relative curve (we saw the 300 Hz reference move by ~5 dB between runs). Compare before/after differences directly, or use a band average as the reference.
Latency depends on the interface and driver (about 10 ms with one interface and about 265 ms with another here). Compare delays only on the same hardware.
A pre-silence and tail long enough for the harmonic responses to fit before the peak are needed (the defaults are fine for sweeps of a few seconds or more).
Re-placing the mic changes the result. In a room, a few centimetres can move a deep null, so before/after differences at deep nulls can come from the mic position, not the EQ. Mark the positions and keep the mic height the same.
Hardware notes
Tested on macOS with a Focusrite Scarlett 18i20 and a TASCAM US-16x08 (channel numbers and routing differ, so run probe).
macOS needs Microphone permission for the terminal / Python.
Turn off any interface DSP on the input channel (low-cut, EQ, compressor, reverb send) before measuring. On the US-16x08 these are in the TASCAM Settings Panel.
Interface input channels for loopback or internal routing can look like a mic channel; confirm with probe.
EQ design (outside the tool)

The tool only plays and measures the EQ. The design was done in MATLAB from the reference-position response (design_eq_esa.m, design_75hz.m, peq_response.m): find peaks above a running-median baseline, take the -3 dB width (Q = f0 / bandwidth, capped near 5), cut by about 0.8 × the peak height, and predict the result at every other position before measuring. Cuts only: EQ cannot fill a null. Everything below about 30 Hz is ignored (below the loudspeaker's range). A filter designed at one position often does less, or nothing, at positions where that mode is weak (for example the room centre).

RT60 / EDT / C80

rt60_analysis.py rebuilds the impulse response from the saved sweep_recording.wav of each "before" run, filters it into octave bands, and computes T20, T30, EDT and C80 with Schroeder backward integration and noise compensation. Do not use the EQ'd runs for this. Treat the 125 Hz band as modal (it is below the room's Schroeder frequency), and note that a 20-2000 Hz sweep only partly covers the 2 kHz band.

Tests

pytest runs the pipeline against a simulated device, including sweep deconvolution, THD, SNR, spec checks and the EQ. SoundDeviceIO has been used on real interfaces (see Hardware notes), but it is not covered by the automated tests.

