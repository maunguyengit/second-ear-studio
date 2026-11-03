import json
import os
import sys
import time
import wave
from pathlib import Path


def watch_parent(expected):
    import threading
    def watch():
        while True:
            if os.getppid()!=expected:os._exit(2)
            time.sleep(0.25)
    threading.Thread(target=watch,daemon=True).start()


def transcribe(root, id):
    # No network is needed after model setup. Telemetry disabled before imports.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    import av
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    from faster_whisper import WhisperModel
    from .store import Store, StaleAttempt
    from .models import model_path

    store = Store(root)
    row = store.get(id,False)
    if row is None:
        return 1
    def update(**fields):store.worker_update(id,row["revision"],**fields)
    started = time.monotonic()
    try:
        path = model_path(root,row["model"])
        if path is None:
            raise RuntimeError("Download this speech model in Settings, then retry this recording.")
        manifest=path/"source.json"
        if manifest.exists():
            try:update(model_revision=json.loads(manifest.read_text()).get("revision"))
            except (ValueError,OSError):pass
        update(status="running",phase="Reading audio",progress=1,error=None)
        chunks=[]; samples=0; limit=16000*7200
        resampler=av.AudioResampler(format="s16",layout="mono",rate=16000)
        directory=store.jobs/id
        with av.open(str(directory/"original")) as container:
            if not container.streams.audio:
                raise ValueError("This file has no audio track. Choose an audio file or a video with sound.")
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    data=out.to_ndarray().reshape(-1).copy()
                    samples += data.size
                    if samples > limit:
                        raise ValueError("This recording is longer than the two-hour limit. Split it into smaller files.")
                    chunks.append(data)
            for out in resampler.resample(None):
                data=out.to_ndarray().reshape(-1).copy();samples+=data.size;chunks.append(data)
        if samples == 0:
            raise ValueError("No readable audio was found. Try exporting the file as WAV or MP3.")
        if samples > limit:
            raise ValueError("This recording exceeds the two-hour limit.")
        pcm=np.concatenate(chunks);del chunks
        duration=pcm.size/16000
        temporary=directory/"playback.part"
        with wave.open(str(temporary),"wb") as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(pcm.tobytes())
        temporary.replace(directory/"playback.wav")
        blocks=np.array_split(pcm,min(720,pcm.size))
        peaks=[round(float(np.max(np.abs(b.astype(np.int32))))/32768,4) for b in blocks]
        audio=pcm.astype(np.float32)/32768;del pcm,blocks
        update(duration=duration,waveform=json.dumps(peaks),playback_ready=1,phase="Loading local speech model",progress=3)
        threads=max(1,min(8,(os.cpu_count() or 4)-1))
        model=WhisperModel(str(path),device="cpu",compute_type="int8",cpu_threads=threads,local_files_only=True)
        update(phase="Transcribing on your computer",progress=5)
        segments,info=model.transcribe(audio,language=row["language"] or None,beam_size=5,word_timestamps=True,
            vad_filter=True,condition_on_previous_text=False,initial_prompt=row["vocabulary"] or None,
            hallucination_silence_threshold=2.0)
        for n,segment in enumerate(segments):
            text=segment.text.strip()
            if not text:
                continue
            start=max(0,min(duration,float(segment.start)))
            end=max(start,min(duration,float(segment.end)))
            if end<=start:
                continue
            words=[{"word":w.word,"start":max(0,float(w.start)),"end":min(duration,float(w.end)),"probability":round(float(w.probability),4)} for w in (segment.words or [])]
            uncertain=segment.avg_logprob < -0.8 or any(w["probability"]<0.65 for w in words)
            store.append(id,n,start,end,text,words,uncertain,expected_revision=row["revision"])
            update(progress=min(98,5+93*end/max(duration,0.001)))
        count=len(store.get(id)["segments"])
        update(status="completed",phase="Ready" if count else "No speech detected",progress=100,
                     language=info.language,elapsed=round(time.monotonic()-started,3))
        return 0
    except StaleAttempt:
        return 2
    except Exception as exc:
        # No hidden retries or made-up transcript when decoding/inference fails.
        message=str(exc).strip() or type(exc).__name__
        if len(message)>700:message=message[:700]
        try:update(status="failed",phase="Could not transcribe",error=message)
        except StaleAttempt:pass
        return 1


if __name__ == "__main__":
    if len(sys.argv)>3:watch_parent(int(sys.argv[3]))
    sys.exit(transcribe(Path(sys.argv[1]),sys.argv[2]))
