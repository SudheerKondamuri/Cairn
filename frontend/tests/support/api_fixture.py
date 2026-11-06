"""Isolated browser fixture using real account storage. Never shipped in Docker."""
from pathlib import Path
import json,os,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from api.app import create_app
from flask import request
class Ledger:
    def list_runs(self):return []
with tempfile.TemporaryDirectory(prefix='cairn-browser-test-') as uploads:
    app=create_app({'DATABASE_URL':os.environ['DATABASE_URL'],'UPLOAD_ROOT':uploads,'API_KEY':os.environ['CAIRN_API_KEY'],'REQUIRE_API_AUTH':True,'API_RATE_LIMIT':10000,'ADMIN_IDENTITIES':'github:browser-admin'},repository=Ledger())
    store=app.extensions['web_store']
    store.connect().close()
    @app.post('/api/test/complete/<job_id>')
    def complete(job_id):
        # Test-only fixture completion; production app has no such route.
        report=json.loads((ROOT/'frontend/public/evidence/northstar-vulnerable.json').read_text())
        report['investigation_id']=job_id
        store.event(job_id,'Test fixture: execution started',execution=True)
        store.finish(job_id,result=report)
        return {'ok':True}
    app.run(host='127.0.0.1',port=8181,threaded=True,use_reloader=False)
