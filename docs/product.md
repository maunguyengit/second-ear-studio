# Second Ear: product contract and research

Research date: November 2, 2026, America/Los_Angeles.

## The job

A student, interviewer, researcher or creator has a real recording and needs a
checked transcript or usable caption file. They should open the app, drop a file,
transcribe, listen at the right point, correct text and export. It should not ask
for an API key, account or cloud upload. The Mac package includes the first model.

This is an independently implemented, focused transcription editor. It is not a
new speech model, a claim of scientific breakthrough, or a claim that existing
apps lack editing/subtitles. Its portfolio value is the complete usable workflow,
local processing, honest review signals, persistence/recovery and a verified
standalone release. Real user retention and product-market fit are unvalidated.

## What was checked before building

| Product / source | Observed demand or capability | What this does and does not establish |
|---|---|---|
| [Handy on GitHub](https://github.com/cjpais/Handy) | Public repository showed approximately 37.1k stars; offline, extensible speech-to-text app | Demonstrates public interest in local speech tools; stars are neither users nor revenue. |
| [Buzz on GitHub](https://github.com/chidiwilliams/buzz) | Approximately 22.4k stars; offline transcription/translation | A mature alternative already exists. This release does not claim to outperform it. |
| [Vibe on GitHub](https://github.com/thewh1teagle/vibe) and [official site](https://thewh1teagle.github.io/vibe/) | Approximately 8.0k stars; file/live transcription, editing and subtitle output | Editing/export are established workflows, not invented differentiation. |
| [Handy on Product Hunt](https://www.producthunt.com/products/handy-4) | Open-source dictation listing; user commentary mentions access/customization and subscription friction | Qualitative motivation for ownership/convenience, not a representative user study. |
| [Product Hunt's November 2 leaderboard](https://www.producthunt.com/leaderboard/daily/2026/11/2) | Visible local/private AI and productivity launches; dictation listed among trending categories | A dated launch/discovery signal; no claim this new app is trending. |
| [Faster Whisper upstream](https://github.com/SYSTRAN/faster-whisper) | Maintained CTranslate2 speech engine with CPU int8 and word timestamps | Use a real established engine rather than fake recognition or train an unnecessary model. |

The GitHub Trending page was also opened but did not return a usable repository
list in the research extraction. No “trending today” ranking is claimed for the
three repositories above. Their star counts are a dated, approximate observation.

## Why this scope

Concentrate on finishing the recording-to-checked-output loop: readable editor,
real audio/source navigation, an uncertainty review queue with an honest caveat,
durable saved sessions, safe edits, and caption files usable by another app. A
small offline Mac release is feasible without paid cloud infrastructure. The
user requested convenience; bundling Python/runtime/model matters more here than
adding another model selector or a marketing landing page.

## Acceptance criteria

1. The built Mac executable starts without Python on PATH; the initial model is
   available from the application bundle. The editor loads from localhost.
2. A real human speech file goes through the same upload and worker path as user
   recordings and yields actual model text, timestamps and a nonzero waveform.
3. Text edits and reviewed flags persist across an application/server restart.
   A stale browser revision cannot silently overwrite a newer save.
4. Clicking a timestamp seeks the real audio. The browser player supports range
   requests and selectable playback speeds.
5. TXT/SRT/VTT/JSON exports reflect saved edits; rewritten text is not assigned
   false original word alignment. Empty edited passages are omitted from cues.
6. Invalid media, missing models, an empty/oversize upload and interrupted jobs
   produce actionable states. Cancel/retry operate on actual worker state.
7. The app binds to loopback only and rejects foreign browser origins for state
   changes. Transcripts/filenames are rendered as text; no untrusted HTML executes.
8. The source package has meaningful tests, a clean built wheel, reproducible
   dependency snapshot, CI and explicit supported-platform/packaging limitations.

## Explicit v1 boundaries

Single user; macOS Apple Silicon package, macOS/Linux Python source path.
250 MB/file, two hours/recording. CPU int8 inference. File and microphone inputs,
transcription, source playback, text editing, review flags and four export formats.
No speaker diarization, translation, live streaming captions, operating-system
wide dictation, cloud synchronization, auto-generated summaries, social sharing,
public accounts or team administration. Browser microphone permission is always
a user action. The browser tab is the editor; this is not a native Cocoa editor.

No public upload service is deployed: the product is distributed as a local app.
Code signing/notarization with an Apple Developer identity is a separate public
release step unavailable in this session. The generated local Mac build is
unsigned/ad-hoc signed, and its exact verification status is in verification.md.
