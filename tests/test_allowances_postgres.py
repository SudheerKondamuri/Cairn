"""Run against an isolated disposable database, never production."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from api.allowances import AdmissionDenied, reserve, transition

DSN = os.getenv('CAIRN_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='requires isolated Postgres test database')


def test_atomic_admission_and_refunds():
    import psycopg

    with psycopg.connect(DSN) as connection:
        connection.execute(Path('migrations/001_accounts.sql').read_text())
        connection.execute("INSERT INTO cairn_accounts(account_id) VALUES ('test-user')")

    def submit(number):
        try:
            with psycopg.connect(DSN) as connection:
                return reserve(connection.cursor(), account_id='test-user', idempotency_key=f'request-{number:020}', request_digest='a' * 64)[0]
        except AdmissionDenied as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(submit, range(12)))
    accepted = [value for value in results if value.startswith('inv-')]
    assert len(accepted) == 3
    assert results.count('account_allowance_exhausted') == 9

    with psycopg.connect(DSN) as connection:
        cursor = connection.cursor()
        key = connection.execute('SELECT idempotency_key FROM cairn_reservations WHERE reservation_id = %s', (accepted[0],)).fetchone()[0]
        assert reserve(cursor, account_id='test-user', idempotency_key=key, request_digest='a' * 64) == (accepted[0], False)
        with pytest.raises(AdmissionDenied, match='idempotency_conflict'):
            reserve(cursor, account_id='test-user', idempotency_key=key, request_digest='b' * 64)
        assert transition(cursor, accepted[0], 'start')
        assert not transition(cursor, accepted[0], 'release_before_execution')
        assert transition(cursor, accepted[0], 'finish')
        assert not transition(cursor, accepted[0], 'start')
        assert transition(cursor, accepted[1], 'release_before_execution')
        assert not transition(cursor, accepted[1], 'start')
    assert submit(100).startswith('inv-')

    with psycopg.connect(DSN) as connection:
        connection.execute('UPDATE cairn_trial SET run_limit = 3')
        connection.execute("INSERT INTO cairn_accounts(account_id) VALUES ('another-user')")
    with psycopg.connect(DSN) as connection:
        with pytest.raises(AdmissionDenied, match='trial_allowance_exhausted'):
            reserve(connection.cursor(), account_id='another-user', idempotency_key='another-request-0001', request_digest='a' * 64)
