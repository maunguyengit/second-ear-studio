import pytest
from fastapi.testclient import TestClient
from second_ear.app import create_app

HEADERS={"X-Second-Ear":"1"}

@pytest.fixture
def library(tmp_path):
    model=tmp_path/'models'/'tiny.en';model.mkdir(parents=True)
    for name in ['config.json','model.bin','tokenizer.json','vocabulary.txt']:(model/name).write_bytes(b'fixture-only-not-an-inference-model')
    return tmp_path

@pytest.fixture
def client(library):
    with TestClient(create_app(library,run_worker=False)) as client:yield client

@pytest.fixture
def complete(client):
    response=client.post('/api/sessions',headers=HEADERS,files={'file':('Interview.wav',b'fixture audio')})
    assert response.status_code==201
    row=response.json();store=client.app.state.store
    store.append(row['id'],0,0.125,4.56,'Source words.',[{'word':'Source','start':.125,'end':2,'probability':.5}],True)
    store.append(row['id'],1,4.56,7.2,'A second passage.',[],False)
    store.update(row['id'],status='completed',phase='Ready',duration=7.2,progress=100)
    return client.get('/api/sessions/'+row['id']).json()
