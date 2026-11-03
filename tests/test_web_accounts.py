"""Account boundaries and public trial behavior against isolated PostgreSQL."""
import io
import json
import os
from pathlib import Path
import pytest
from api.app import create_app
from api.web_store import WebStore
from api.allowances import AdmissionDenied

DSN=os.getenv('CAIRN_TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not DSN,reason='requires disposable PostgreSQL')

@pytest.fixture
def store():
    import psycopg
    with psycopg.connect(DSN) as db:
        db.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
    return WebStore(DSN)


def test_identity_ownership_quota_sharing_and_deletion(store):
    token=store.login('github','123')
    owner=store.identity(token)['account_id']
    assert store.identity(store.login('github','123'))['account_id']==owner
    stranger=store.identity(store.login('google','456'))['account_id']
    job,created=store.submit(owner,'request-000000001','a'*64,'claim',{},'source.tar.gz')
    assert created
    assert store.submit(owner,'request-000000001','a'*64,'claim',{},'source.tar.gz')==(job,False)
    assert store.get(stranger,job) is None
    assert store.history(stranger)['items']==[]
    with pytest.raises(AdmissionDenied,match='not_found'):store.action(stranger,job,'cancel')
    claimed=store.claim(); assert claimed['investigation_id']==job
    store.event(job,'creating guest',execution=True)
    store.finish(job,result={'verdict':'verified'})
    shared=store.action(owner,job,'share')['token']
    assert store.shared(shared)=={'verdict':'verified'}
    store.action(owner,job,'revoke');assert store.shared(shared) is None
    shared=store.action(owner,job,'share')['token']
    store.action(owner,job,'delete');assert store.get(owner,job) is None
    assert store.shared(shared) is None
    assert store.allowance(owner)['used']==1
    store.logout(token);assert store.identity(token) is None


def test_cancel_before_and_after_start_and_pause(store):
    owner=store.identity(store.login('github','123'))['account_id']
    one,_=store.submit(owner,'request-000000001','a'*64,'claim',{},'a.tar.gz')
    store.action(owner,one,'cancel');assert store.allowance(owner)['used']==0
    two,_=store.submit(owner,'request-000000002','a'*64,'claim',{},'b.tar.gz')
    store.claim();store.event(two,'creating',execution=True);store.action(owner,two,'cancel')
    with pytest.raises(AdmissionDenied,match='cancelled'):store.event(two,'next tool')
    store.finish(two);assert store.get(owner,two)['status']=='cancelled'
    assert store.allowance(owner)['used']==1
    store.admin_update(owner,dict(action='trial',paused=True))
    with pytest.raises(AdmissionDenied,match='trial_paused'):store.submit(owner,'request-000000003','a'*64,'claim',{},'c.tar.gz')


def test_api_session_and_admin_boundaries(store,tmp_path):
    app=create_app({'TESTING':True,'DATABASE_URL':DSN,'API_KEY':'test-service-secret','API_RATE_LIMIT':1000,'UPLOAD_ROOT':str(tmp_path),'ADMIN_IDENTITIES':'github:999'})
    app.extensions['web_store']=store
    client=app.test_client()
    assert client.post('/api/web/sessions',json={'provider':'github','subject':'999'}).status_code==401
    service={'X-Cairn-API-Key':'test-service-secret'}
    token=client.post('/api/web/sessions',headers=service,json={'provider':'github','subject':'123'}).json['token']
    user={**service,'X-Cairn-Session':token}
    assert client.get('/api/web/me',headers=user).json['allowance']['remaining']==3
    assert client.get('/api/web/admin',headers=user).status_code==403
    admin_token=client.post('/api/web/sessions',headers=service,json={'provider':'github','subject':'999'}).json['token']
    assert client.get('/api/web/admin',headers={**service,'X-Cairn-Session':admin_token}).status_code==200
    manifest={'subject_type':'http_app','runtime':'python','start_argv':['python3','app.py'],'port':5002}
    archive=Path('frontend/public/examples/northstar.tar.gz').read_bytes()
    def submit():return client.post('/api/web/investigations',headers={**user,'Idempotency-Key':'submission-key-00000001'},data={'source':(io.BytesIO(archive),'source.tar.gz'),'report':'Test owned source','manifest':json.dumps(manifest)})
    first=submit();assert first.status_code==202,first.json
    second=submit();assert first.json==second.json
    assert client.get('/api/web/me',headers=user).json['allowance']['remaining']==2
    assert len(list(tmp_path.glob('*.tar.gz')))==1
    client.delete('/api/web/sessions',headers=user)
    assert client.get('/api/web/me',headers=user).status_code==401


def test_public_github_import_strips_wrapper_and_preserves_quota(store,tmp_path,monkeypatch):
    import tarfile
    import api.web_api as web_api
    def download(url,path,**kwargs):
        assert url=='https://github.com/owner/project'
        assert kwargs['max_bytes']==10*1024*1024
        with tarfile.open(path,'w:gz') as tar:
            data=b'print("owned fixture")'
            info=tarfile.TarInfo('project-main/app.py');info.size=len(data)
            tar.addfile(info,io.BytesIO(data))
    monkeypatch.setattr(web_api,'download_archive',download)
    app=create_app({'TESTING':True,'DATABASE_URL':DSN,'API_KEY':'test-service-secret','API_RATE_LIMIT':1000,'UPLOAD_ROOT':str(tmp_path)})
    client=app.test_client();headers={'X-Cairn-API-Key':'test-service-secret'}
    token=client.post('/api/web/sessions',headers=headers,json={'provider':'github','subject':'importer'}).json['token']
    headers.update({'X-Cairn-Session':token,'Idempotency-Key':'github-import-000001'})
    result=client.post('/api/web/investigations',headers=headers,data={'github_url':'https://github.com/owner/project','github_ref':'main','report':'Owned fixture','manifest':json.dumps({'subject_type':'http_app','runtime':'python','start_argv':['python3','app.py'],'port':5002})})
    assert result.status_code==202,result.json
    with tarfile.open(next(tmp_path.glob('*.tar.gz'))) as tar:
        assert tar.getnames()==['app.py']
    assert client.get('/api/web/me',headers=headers).json['allowance']['remaining']==2
