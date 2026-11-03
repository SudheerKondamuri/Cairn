"""History contract added for the private operator frontend."""
from datetime import datetime, timezone
from api.app import create_app
from api.repository import RunRepository


def test_history_requires_auth_and_validates_before_repository():
    class Repo:
        calls = []
        def list_investigations(self, **filters):
            self.calls.append(filters)
            return {'items': [], 'next_cursor': None}
    repo = Repo()
    client = create_app({'TESTING': True, 'API_KEY': 'test-history-key'}, repository=repo).test_client()
    assert client.get('/api/investigations').status_code == 401
    headers = {'X-Cairn-API-Key': 'test-history-key'}
    for query in ['limit=0', 'limit=51', 'limit=no', 'status=deleted', 'cursor=../../x', 'q='+'x'*101]:
        assert client.get('/api/investigations?'+query, headers=headers).status_code == 400
    assert repo.calls == []
    response = client.get('/api/investigations?limit=10&q=Northstar&status=completed&cursor=inv-page01', headers=headers)
    assert response.status_code == 200
    assert response.json == {'items': [], 'next_cursor': None}
    assert repo.calls == [dict(limit=10, query='Northstar', status='completed', cursor='inv-page01')]


def test_repository_history_paginates_metadata_and_parameterizes_search():
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    rows = [(f'inv-history{i}', 'completed', 'verified', now, now, 'python', 'http_app', 'claim '*40) for i in range(3)]
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, params): self.query = sql, params
        def fetchall(self): return rows
    class Connection:
        closed = False
        cursor_value = Cursor()
        def cursor(self): return self.cursor_value
    conn = Connection()
    repo = RunRepository(connection_factory=lambda _: conn)
    repo._investigations_schema_ready = True
    result = repo.list_investigations(limit=2, cursor='inv-before', query="' OR true --", status='completed')
    assert len(result['items']) == 2
    assert result['next_cursor'] == 'inv-history1'
    assert result['items'][0]['created_at'] == now.isoformat()
    assert len(result['items'][0]['title']) == 120
    assert not ({'source_path', 'report', 'result'} & result['items'][0].keys())
    sql, params = conn.cursor_value.query
    assert "' OR true --" not in sql
    assert params == ('inv-before', "%' OR true --%", "%' OR true --%", 'completed', 3)
    assert 'ORDER BY created_at DESC, investigation_id DESC' in sql
