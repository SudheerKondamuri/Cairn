"""Local access must be explicit and still service authenticated."""
from api.app import create_app
from api.web_store import WebStore


def test_local_access_requires_service_key_and_hosted_ignores_bypass(monkeypatch):
    monkeypatch.setattr(WebStore, 'local_account', lambda self: {'account_id': 'acct-local', 'identities': ['local:owner']})
    monkeypatch.setattr(WebStore, 'identity', lambda self, token: None)
    monkeypatch.setattr(WebStore, 'allowance', lambda self, owner: {'remaining': 3})
    for local in (False, True):
        app = create_app({'TESTING': True, 'LOCAL_ACCESS': local, 'API_KEY': 'local-test-service', 'API_RATE_LIMIT': 1000})
        client = app.test_client()
        assert client.get('/api/web/me', headers={'X-Cairn-Local': 'true'}).status_code == 401
        response = client.get('/api/web/me', headers={'X-Cairn-API-Key': 'local-test-service', 'X-Cairn-Local': 'true'})
        assert response.status_code == (200 if local else 401)
        if local:
            assert response.json['local'] is True
            assert response.json['admin'] is True
        assert client.get('/api/web/me', headers={'X-Cairn-API-Key': 'local-test-service'}).status_code == 401


def test_local_account_unlimited_allowance(monkeypatch):
    store = WebStore('postgresql://localhost/fake')
    class FakeCursor:
        def fetchone(self):
            return (50, 10)  # total 50, used 10
    class FakeDb:
        def execute(self, query, params=None):
            return FakeCursor()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(store, 'connect', lambda: FakeDb())
    allowance = store.allowance('acct-local')
    assert allowance['unlimited'] is True
    assert allowance['limit'] is None
    assert allowance['remaining'] is None

