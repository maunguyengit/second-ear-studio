# Architecture and recovery contract

`second-ear` starts a FastAPI/Uvicorn server on `127.0.0.1:8767` and opens the local
editor. The bundled desktop executable contains Python, libraries, UI assets and
the small English model. A library lock prevents two app processes from using the
same data folder. Opening it again reopens the existing editor.

SQLite/WAL stores session state and versioned edits. Each recording has a UUID
folder containing its original input, normalized mono 16 kHz WAV and diagnostics.
Media bytes never form a path chosen by the uploader. File names are display
metadata only; API IDs must parse as UUIDs.

One queue thread serializes work. Each recording runs in a separate Python/frozen
worker process, which decodes the real audio with PyAV, computes an amplitude
waveform, loads the selected local CTranslate2 model and writes actual segments
and word probabilities. Worker writes are fenced by the attempt revision/status so an obsolete worker cannot overwrite a cancelled or retried job. A parent-process watcher also exits an orphaned worker. A process boundary makes cancellation concrete: terminate
and, if necessary, kill the running worker. Partial work remains marked incomplete,
not exportable as a completed transcript. Retry removes partial segments before
reprocessing. A completed recording's original source text stays available even
when its editable text changes.

## State

`queued → running → completed | failed | cancelled`

Queued sessions survive restart. A session left `running` by a crash becomes
`failed` with a retry instruction at next startup. Application quit cancels its
active child and preserves queued work. An export requires `completed`. A failure
never falls back to hardcoded or sample text. The built-in sample is an explicit
real audio import through exactly the same engine.

SQLite edits use `BEGIN IMMEDIATE` and an expected session revision. A batch of
changes either commits entirely with a new revision or rolls back. The editor
retains an unsaved draft after a conflict. It does not pretend concurrent browser
windows have collaborative editing. Export triggers an explicit save first.

## Review signals and timestamps

A passage is flagged when a model word probability is below 0.65 or its average
log probability is below -0.8. These thresholds are heuristics for prioritizing
listening, not calibrated error probabilities and not a guarantee that all errors
are flagged. Human-reviewed flags are user decisions. The engine is not original
research; no recognition-quality improvement over upstream is claimed.

Edited segments keep original segment boundaries. JSON omits original word
alignment for a changed segment and explains why. SRT/VTT are segment-level
captions, not word-by-word karaoke timing. The waveform is computed from the real
PCM amplitude envelope and is not seeded/decorative sample data.

## Input, storage and security

Uploads are bounded at request and saved-file boundaries. Decoding reads only the
audio stream and stops beyond two hours; samples are resampled to mono int16,
then converted to float32 for recognition. This is bounded but not streaming
recognition: a two-hour file can still use substantial memory. Use shorter files
on memory-constrained machines. Originals plus normalized WAV consume local disk.
The app is not an untrusted internet media-processing sandbox.

State-changing routes require the app's custom header; foreign browser Origin
headers are rejected, and no cross-origin CORS permission is provided. Host names
are restricted to localhost/loopback. CSP, no-sniff and no-referrer headers are
set. Untrusted text uses textContent, textarea values and JSON, never HTML
interpolation. These measures protect a single-user loopback app; they are not
multiuser authentication. Do not expose it through a public reverse proxy.

Hugging Face downloads happen only on an explicit model setup action and use the
system trust store. Inference sets offline mode, disables Hugging Face telemetry,
and disables ONNX Runtime telemetry events. No cloud transcription or app analytics
is implemented. Third-party binary libraries and upstream updates still require
normal dependency review; this is not an independently audited privacy guarantee.

## Release operation

The source/wheel needs Python and a first model download. The Mac bundle includes
the initial model and runtime. Optional larger models download separately.
Back up the whole library with the app stopped. To restore, use that folder with
`--data-dir`. Quit through Settings or Ctrl+C. If startup says the port is occupied,
close the other service or use `--port`; do not bind externally.
