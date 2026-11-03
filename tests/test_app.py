import json
from pathlib import Path
from fastapi.testclient import TestClient
from second_ear.app import create_app
from conftest import HEADERS


def test_single_user_origin_and_host_boundary(client):
    assert client.get('/api/health').json()['product']=='second-ear'
    assert client.get('/api/health',headers={'host':'attacker.example'}).status_code==400
    assert client.post('/api/sample').status_code==403
    assert client.post('/api/sample',headers={**HEADERS,'origin':'https://attacker.example'}).status_code==403
    assert client.get('/').headers['x-content-type-options']=='nosniff'
    assert "script-src 'self'" in client.get('/').headers['content-security-policy']


def test_upload_is_real_file_with_safe_name(client,library):
    r=client.post('/api/sessions',headers=HEADERS,files={'file':('../../private/hello.wav',b'original-file')})
    assert r.status_code==201
    row=r.json();assert row['filename']=='hello.wav' and row['status']=='queued'
    assert (library/'recordings'/row['id']/'original').read_bytes()==b'original-file'
    assert client.patch('/api/sessions/'+row['id'],headers=HEADERS,json={'revision':0,'changes':[]}).status_code==409


def test_input_limits_and_missing_model_are_actionable(client,library):
    assert client.post('/api/sessions',headers=HEADERS,files={'file':('empty.wav',b'')}).status_code==422
    assert client.post('/api/sessions',headers=HEADERS,data={'model':'base'},files={'file':('a.wav',b'a')}).status_code==409
    assert client.post('/api/sessions',headers=HEADERS,data={'language':'vi'},files={'file':('a.wav',b'a')}).status_code==422
    assert list((library/'recordings').iterdir())==[]


def test_oversize_file_removes_partial_data(library):
    with TestClient(create_app(library,run_worker=False,max_upload=5)) as client:
        response=client.post('/api/sessions',headers=HEADERS,files={'file':('big.wav',b'123456')})
        assert response.status_code==413
        assert client.get('/api/sessions').json()==[]
    assert list((library/'recordings').iterdir())==[]


def test_edits_persist_and_revision_conflicts_preserve_newer_text(client,complete):
    path='/api/sessions/'+complete['id']
    text='A corrected passage with <untrusted> text.'
    saved=client.patch(path,headers=HEADERS,json={'revision':0,'title':'My interview','changes':[{'n':0,'text':text,'reviewed':True}]})
    assert saved.status_code==200 and saved.json()['revision']==1
    assert client.get(path).json()['segments'][0]['text']==text
    stale=client.patch(path,headers=HEADERS,json={'revision':0,'changes':[{'n':0,'text':'Old window','reviewed':False}]})
    assert stale.status_code==409
    assert client.get(path).json()['segments'][0]['text']==text
    assert client.get('/api/sessions').json()[0]['review_count']==0


def test_failed_batch_edit_is_atomic(client,complete):
    path='/api/sessions/'+complete['id']
    r=client.patch(path,headers=HEADERS,json={'revision':0,'changes':[{'n':0,'text':'Should roll back','reviewed':True},{'n':999,'text':'Missing','reviewed':True}]})
    assert r.status_code==409
    unchanged=client.get(path).json()
    assert unchanged['revision']==0 and unchanged['segments'][0]['text']=='Source words.'


def test_exports_use_saved_edits_and_do_not_claim_stale_word_alignment(client,complete):
    path='/api/sessions/'+complete['id']
    client.patch(path,headers=HEADERS,json={'revision':0,'changes':[{'n':0,'text':'Corrected words.','reviewed':True}]})
    srt=client.get(path+'/export/srt');assert srt.status_code==200
    assert '00:00:00,125 --> 00:00:04,560' in srt.text and 'Corrected words.' in srt.text
    assert client.get(path+'/export/vtt').text.startswith('WEBVTT\n\n')
    data=client.get(path+'/export/json').json()
    assert data['segments'][0]['word_timestamps'] is None
    assert data['segments'][0]['original_text']=='Source words.'
    assert 'Corrected words.' in client.get(path+'/export/txt').text
    assert 'attachment;' in srt.headers['content-disposition']
    assert client.get(path+'/export/exe').status_code==404


def test_audio_range_requests_and_id_boundary(client,complete,library):
    id=complete['id'];(library/'recordings'/id/'playback.wav').write_bytes(b'RIFF0123456789')
    response=client.get(f'/api/sessions/{id}/media',headers={'Range':'bytes=4-7'})
    assert response.status_code==206 and response.content==b'0123'
    assert client.get('/api/sessions/not-an-id').status_code==404
    assert client.get('/api/sessions/00000000-0000-0000-0000-000000000000/media').status_code==404


def test_cancel_retry_and_delete_work_on_disposable_recording(client,library):
    row=client.post('/api/sessions',headers=HEADERS,files={'file':('a.wav',b'original')}).json();path='/api/sessions/'+row['id']
    assert client.post(path+'/cancel',headers=HEADERS).json()['status']=='cancelled'
    assert client.post(path+'/retry',headers=HEADERS).json()['status']=='queued'
    assert client.post(path+'/retry',headers=HEADERS).status_code==409
    assert client.delete(path,headers=HEADERS).status_code==204
    assert client.get(path).status_code==404
    assert not (library/'recordings'/row['id']).exists()


def test_library_survives_reopening_application(complete,library):
    with TestClient(create_app(library,run_worker=False)) as reopened:
        row=reopened.get('/api/sessions/'+complete['id']).json()
        assert row['status']=='completed' and len(row['segments'])==2


def test_import_without_audio_fails_in_real_decoder(library):
    import uuid
    from second_ear.store import Store
    from second_ear.worker import transcribe
    store=Store(library);id=str(uuid.uuid4());folder=store.jobs/id;folder.mkdir();(folder/'original').write_bytes(b'This is not a recording')
    store.create(id,'Invalid file','invalid.wav','tiny.en','en','')
    assert transcribe(library,id)==1
    row=store.get(id)
    assert row['status']=='failed' and row['error'] and not row['segments']


def test_cancelled_or_retried_worker_cannot_overwrite_a_new_attempt(client,complete):
    import pytest
    from second_ear.store import StaleAttempt
    store=client.app.state.store;id=complete['id']
    store.update(id,status='cancelled')
    with pytest.raises(StaleAttempt):store.worker_update(id,0,status='completed')
    store.reset(id)
    with pytest.raises(StaleAttempt):store.worker_update(id,0,status='running')
    store.worker_update(id,1,status='running')
    with pytest.raises(StaleAttempt):store.append(id,0,0,1,'stale',[],False,expected_revision=0)
    assert store.get(id)['segments']==[]
    store.append(id,0,0,1,'current',[],False,expected_revision=1)
    assert store.get(id)['segments'][0]['text']=='current'
