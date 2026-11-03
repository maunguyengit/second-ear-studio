# FFmpeg binary provenance

PyAV's bundled dynamic libraries report FFmpeg **9.0.2** and **LGPL version 3 or
later** at runtime. The exact library version/configuration strings are preserved
in `docs/ffmpeg-config.json`. FFmpeg's own license overview and LGPL/GPL texts are
included beside this file; these do not replace licenses of additional linked
codec libraries.

Matching upstream source:
https://github.com/FFmpeg/FFmpeg/tree/n9.0.2

Source archive:
https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n9.0.2.tar.gz

PyAV source and wheel build tooling:
https://github.com/PyAV-Org/PyAV/tree/v19.0.2
https://github.com/PyAV-Org/pyav-ffmpeg

The app dynamically links the PyAV wheel's FFmpeg libraries; it does not require
or modify the user's system FFmpeg. Preserve these notices and source information
when redistributing the binary, allow replacement/relinking of covered libraries,
and review the exact upstream wheel/build dependencies when changing versions.
No Apple Developer ID/hardened runtime restriction prevents replacing libraries
in this local ad-hoc-signed app; changed bundles need their own local signature.
