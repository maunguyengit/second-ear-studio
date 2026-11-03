"""Real speech-engine check. Never download a model silently during tests."""
import json
import os
import shutil
import uuid
from pathlib import Path
import pytest
from second_ear.store import Store
from second_ear.worker import transcribe
from second_ear.models import model_path


@pytest.mark.inference
def test_actual_human_speech_reaches_a_real_transcript(tmp_path):
    source=os.environ.get('SECOND_EAR_TEST_MODEL_DIR')
    if not source:
        pytest.skip('Set SECOND_EAR_TEST_MODEL_DIR to a library with a real tiny.en model')
    model=model_path(Path(source),'tiny.en')
    assert model is not None,'Requested real model is missing; do not substitute fixture output'
    destination=tmp_path/'models'/'tiny.en';destination.mkdir(parents=True)
    for f in model.iterdir():
        if f.is_file():(destination/f.name).symlink_to(f.resolve())
    import second_ear.app
    sample=second_ear.app.SAMPLE
    assert sample.exists()
    store=Store(tmp_path);id=str(uuid.uuid4());folder=store.jobs/id;folder.mkdir();shutil.copyfile(sample,folder/'original')
    store.create(id,'Real human speech','jfk.wav','tiny.en','en','')
    assert transcribe(tmp_path,id)==0
    row=store.get(id);text=' '.join(s['text'] for s in row['segments']).lower()
    assert row['status']=='completed' and row['duration']>10
    assert 'country' in text and 'americans' in text
    assert len(row['waveform'])>50 and max(row['waveform'])>0
    assert all(0<=s['start']<s['end']<=row['duration'] for s in row['segments'])
    assert any(s['words'] for s in row['segments'])
    assert (folder/'playback.wav').stat().st_size>1000
    print(json.dumps({'audio_seconds':row['duration'],'elapsed_seconds':row['elapsed'],'transcript':text,'segments':len(row['segments'])}))
