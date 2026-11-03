# Verification of 0.1.0

Verified November 2, 2026 (America/Los_Angeles), on an Apple M4 Mac running macOS
26.6.2. Development Python: 3.13.3. This describes observed checks, not claims of
product adoption, breakthrough research or general speech-recognition accuracy.

## Automated checks

**16 tests pass locally**, including a real local model inference test rather than
only a stub. Checks cover upload validation/cleanup, origin/host restrictions,
transactional batch edits, stale-window conflicts, usable exports, audio ranges,
restart persistence, cancel/retry/delete on disposable data, malformed-media
failure and worker-attempt fencing. A cancelled/old worker cannot append text or
mark a newer attempt complete.

The real-engine test uses the attributed human JFK speech excerpt bundled in the
package. Its expected words are checked after actual recognition; expected text is
never substituted as output. Unit fixtures used for isolated database/API tests
are labeled test fixtures and are not the inference evidence.

## Built Mac application

The final `Second Ear.app` was launched against an empty test library with the
development virtual environment and PYTHONPATH removed and PATH restricted to
system locations. It reported the bundled English model ready without a download
or a model directory in that library. Actual inference yielded text, word times,
review hints, a real amplitude waveform and playable WAV output.

The final standalone verification recorded **11 seconds of human speech** and
**0.531 seconds inside the worker's measured processing interval** on this host.
This is a single short integration observation, not a repeatable latency promise,
an end-to-end install/launch measurement, or evidence of a quality/speed advantage
over the upstream model. See [the raw report](standalone-verification.json) for
model revision, output and context.

Saved text/review changes were exported to TXT, SRT, VTT and JSON. Stale saves were
rejected, real audio served a byte-range request, the app was fully shut down and
restarted, and its saved title/text/revision remained. The English model's file
hashes and pinned source revision are in [bundled-model.json](bundled-model.json).

Native builds also processed real speech encoded as MP3, M4A/AAC, FLAC, OGG/Opus,
WebM/Opus and MP4/AAC. The final native worker additionally processed an MP4 with
an actual MPEG-4 video stream and AAC speech. Video frames in this codec fixture
were generated; the speech was the real human excerpt. Details:
[codec-results.json](codec-results.json). No system FFmpeg executable is needed.

A separate first-time download through the app's actual model-download function
succeeded into a new library, with system certificate validation and no API key.
Only the English Quick model's real inference/setup was exercised; larger models
and multilingual recognition quality were not benchmarked.

## Interface checks

The actual browser editor was used to import the real sample, edit and save a
passage/title, play source audio by timestamp, mark a passage reviewed, and
**download an SRT file**. Pending review edits were saved before export. The
result is [example-real.srt](example-real.srt), not a screenshot-only demonstration.
The final app was reopened after shutdown and its saved edits remained visible.

Welcome/editor layouts were checked at **320, 375, 414 and 768 CSS pixels**. The
recorded document widths did not exceed their viewports. The narrow layout's
Settings control, installed-model status and Quit action were verified after
fixing an initially hidden Settings control. Evidence:
[responsive-checks.json](responsive-checks.json), [welcome](welcome.png), and
[real transcript editor](editor-real-transcript.png).

## Distribution status and limits

The bundle has an embedded runtime/model, product icon and version metadata.
`codesign --verify --deep --strict` passes for its **ad-hoc** signature. It has no
Apple Developer ID or notarization. Downloaded copies may be blocked until the
user allows this unnotarized app through macOS's normal security controls. This
session does not bypass those controls or claim App Store readiness.

A built Python wheel and source distribution accompany the Mac artifact. CI is
configured for macOS/Ubuntu with Python 3.11/3.13. All four real CI jobs passed: Ubuntu/macOS × Python 3.11/3.13, covering the 15 non-inference tests, build, built-wheel installation and CLI smoke check. The real inference test remains a separate locally executed check. See [the observed run](ci-result.json), tested at source commit `39e48ca9ec20c67b77d45d4e1e5e5abf87a5d04a`.
The desktop bundle was not tested on Intel Macs, other macOS releases, Windows or
Linux. Its ZIP was separately extracted, its ad-hoc signature verified, and the extracted executable launched successfully. The DMG checksum was verified with hdiutil. The Python CLI explicitly does not claim Windows support.

Physical microphone recording/permission behavior was implemented but not tested
against a user's live microphone; no permission was silently granted and no
ambient user audio was recorded. Full two-hour/250 MB stress tests, broad codec
coverage beyond the fixtures, statistical calibration, recognition-quality
benchmarks and independent security/privacy audits were not performed. Silence,
noise, accents and specialist terms can still produce wrong or missing text.
Uncertainty flags are heuristics, not accuracy guarantees. Review outputs before
publishing them.
