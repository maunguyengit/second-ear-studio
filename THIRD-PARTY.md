# Third-party components

Original Second Ear code is MIT licensed. This does not replace upstream licenses.

- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper): MIT; actual speech
  inference implementation used by the app. Its bundled assets include Silero VAD;
  preserve the upstream package's license/attribution in binary redistribution.
- [OpenAI Whisper](https://github.com/openai/whisper): MIT code/model licensing.
  The bundled English weights are the CTranslate2 conversion in
  [Systran/faster-whisper-tiny.en](https://huggingface.co/Systran/faster-whisper-tiny.en).
  The recorded revision and file hashes are in `docs/bundled-model.json`.
- [CTranslate2](https://github.com/OpenNMT/CTranslate2): MIT.
- [PyAV](https://github.com/PyAV-Org/PyAV): BSD-3-Clause. Its binary distribution
  links FFmpeg libraries with their own LGPL/GPL configuration and component
  notices. The exact bundled wheel's license files are included in the desktop
  distribution's `Third-party licenses` folder; review those before republishing
  a modified binary. This release does not label its whole binary MIT-only.
- FastAPI (MIT), Starlette (BSD-3-Clause), Uvicorn (BSD-3-Clause), Pydantic (MIT),
  NumPy (BSD-3-Clause), ONNX Runtime (MIT), Hugging Face Hub/tokenizers (Apache-2.0),
  and truststore (MIT) retain their included upstream notices. Transitive binary
  dependencies may carry additional notices.
- The optional/demo real-speech excerpt is `samples/jfk.wav` from
  [whisper.cpp](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav),
  distributed in that MIT-licensed project. It is an excerpt of President John F.
  Kennedy's 1961 inaugural address. It is not a synthetic voice or a new recording
  made for this product. Preserve the source attribution; this product does not
  claim ownership of the speech/recording.

The desktop release is assembled with PyInstaller under its bootloader exception.
See the included distribution license notices. No third-party application's UI,
branding or application source was copied. Model quality and behavior remain
those of the selected upstream model and configuration.
