"""Account-isolated web jobs. Every operation owns its database connection."""
from __future__ import annotations
import hashlib
import json
import secrets
import threading
from pathlib import Path
import psycopg
from .allowances import AdmissionDenied, reserve, transition


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def record(cursor):
    row = cursor.fetchone()
    return dict(zip([c.name for c in cursor.description], row)) if row else None


class WebStore:
    def __init__(self, dsn):
        self.dsn = dsn
        self.ready = False
        self.lock = threading.Lock()

    def connect(self):
        if not self.ready:
            with self.lock:
                if not self.ready:
                    with psycopg.connect(self.dsn, connect_timeout=5) as db:
                        db.execute('SELECT pg_advisory_xact_lock(43821790)')
                        db.execute((Path(__file__).resolve().parents[1] / 'migrations/001_accounts.sql').read_text())
                    self.ready = True
        return psycopg.connect(self.dsn, connect_timeout=5)

    def local_account(self):
        # Dedicated local owner: never impersonate a Google or GitHub identity.
        with self.connect() as db:
            db.execute("INSERT INTO cairn_accounts(account_id, run_limit) VALUES ('acct-local', 999999) ON CONFLICT (account_id) DO UPDATE SET run_limit=999999, suspended=FALSE")
            row = record(db.execute("SELECT account_id,run_limit FROM cairn_accounts WHERE account_id='acct-local'"))
            row['identities'] = ['local:owner']
            return row

    def login(self, provider, subject):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('SELECT pg_advisory_xact_lock(43821791)')
            row = db.execute('SELECT account_id FROM cairn_identities WHERE provider=%s AND subject=%s', (provider, subject)).fetchone()
            account = row[0] if row else 'acct-' + secrets.token_hex(16)
            if not row:
                db.execute('INSERT INTO cairn_accounts(account_id) VALUES (%s)', (account,))
                db.execute('INSERT INTO cairn_identities(provider,subject,account_id) VALUES (%s,%s,%s)', (provider, subject, account))
            if db.execute('SELECT suspended FROM cairn_accounts WHERE account_id=%s', (account,)).fetchone()[0]:
                raise AdmissionDenied('account_unavailable')
            db.execute("DELETE FROM cairn_sessions WHERE expires_at < now()")
            db.execute("INSERT INTO cairn_sessions(token_hash,account_id,expires_at) VALUES (%s,%s,now()+interval '8 hours')", (token_hash(token), account))
        return token

    def identity(self, token):
        if not token or len(token) > 128:
            return None
        with self.connect() as db:
            row = record(db.execute('SELECT a.account_id, a.run_limit FROM cairn_sessions s JOIN cairn_accounts a USING(account_id) WHERE s.token_hash=%s AND s.expires_at>now() AND NOT a.suspended', (token_hash(token),)))
            if row:
                row['identities'] = [f'{p}:{s}' for p,s in db.execute('SELECT provider,subject FROM cairn_identities WHERE account_id=%s',(row['account_id'],)).fetchall()]
            return row

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM cairn_sessions WHERE token_hash=%s', (token_hash(token),))

    def allowance(self, account):
        with self.connect() as db:
            total, used = db.execute("SELECT count(*),count(*) FILTER (WHERE account_id=%s) FROM cairn_reservations WHERE state <> 'released'",(account,)).fetchone()
            limit, paused = db.execute('SELECT run_limit,paused FROM cairn_trial WHERE singleton').fetchone()
            if account == 'acct-local':
                return dict(limit=None, used=used, remaining=None, trial_remaining=None, paused=False, request_pending=False, unlimited=True)
            personal = db.execute('SELECT run_limit FROM cairn_accounts WHERE account_id=%s',(account,)).fetchone()[0]
            pending = db.execute('SELECT 1 FROM cairn_allowance_requests WHERE account_id=%s',(account,)).fetchone()
            return dict(limit=personal, used=used, remaining=max(0,personal-used), trial_remaining=max(0,limit-total), paused=paused, request_pending=bool(pending), unlimited=False)

    def submit(self, account, key, digest, report, manifest, source):
        with self.connect() as db:
            job_id, created = reserve(db.cursor(), account_id=account, idempotency_key=key, request_digest=digest)
            if created:
                db.execute('INSERT INTO cairn_web_jobs(investigation_id,account_id,report,manifest,source_path) VALUES (%s,%s,%s,%s::jsonb,%s)',(job_id,account,report,json.dumps(manifest),source))
                db.execute('INSERT INTO cairn_job_events(investigation_id,message) VALUES (%s,%s)',(job_id,'Accepted and queued for an isolated Celesto investigation.'))
            return job_id, created

    def history(self, account, query='', status='', cursor=''):
        with self.connect() as db:
            rows = db.execute("""SELECT investigation_id,status,result->>'verdict' AS verdict,created_at,updated_at,
                manifest->>'runtime' AS runtime,manifest->>'subject_type' AS subject_type,
                left(split_part(report,E'\n',1),120) AS title FROM cairn_web_jobs
                WHERE account_id=%s AND NOT deleted AND expires_at>now()
                AND (%s='' OR report ILIKE %s OR investigation_id ILIKE %s)
                AND (%s='' OR status=%s)
                AND (%s='' OR (created_at,investigation_id) < (SELECT created_at,investigation_id FROM cairn_web_jobs WHERE investigation_id=%s AND account_id=%s))
                ORDER BY created_at DESC,investigation_id DESC LIMIT 26""",(account,query,'%'+query+'%','%'+query+'%',status,status,cursor,cursor,account))
            items = [dict(zip([c.name for c in rows.description],row)) for row in rows.fetchall()]
            return dict(items=items[:25],next_cursor=items[24]['investigation_id'] if len(items)>25 else None)

    def get(self, account, job_id):
        with self.connect() as db:
            job = record(db.execute('SELECT investigation_id,status,report,manifest,result,error,created_at,updated_at,cancel_requested,expires_at,share_hash IS NOT NULL AS shared FROM cairn_web_jobs WHERE account_id=%s AND investigation_id=%s AND NOT deleted AND expires_at>now()', (account,job_id)))
            if job:
                rows = db.execute('SELECT message,created_at FROM cairn_job_events WHERE investigation_id=%s ORDER BY event_id LIMIT 500',(job_id,))
                job['events'] = [dict(message=m,created_at=t) for m,t in rows.fetchall()]
            return job

    def action(self, account, job_id, action):
        with self.connect() as db:
            job = record(db.execute('SELECT * FROM cairn_web_jobs WHERE account_id=%s AND investigation_id=%s AND NOT deleted AND expires_at>now() FOR UPDATE',(account,job_id)))
            if not job:
                raise AdmissionDenied('not_found')
            if action == 'cancel':
                if job['status'] in ('queued', 'running'):
                    db.execute("UPDATE cairn_web_jobs SET status='cancelled',cancel_requested=TRUE,updated_at=now() WHERE investigation_id=%s",(job_id,))
                    if not transition(db.cursor(),job_id,'finish'):
                        transition(db.cursor(),job_id,'release_before_execution')
                    db.execute("INSERT INTO cairn_job_events(investigation_id,message) VALUES (%s,%s)",(job_id,'Investigation cancelled by operator.'))
                else:
                    raise AdmissionDenied('already_finished')
            elif action == 'delete':
                if job['status'] in ('queued','running'):
                    raise AdmissionDenied('cancel_first')
                db.execute("UPDATE cairn_web_jobs SET deleted=TRUE,share_hash=NULL,report='',manifest='{}',result=NULL,error=NULL WHERE investigation_id=%s",(job_id,))
                db.execute('DELETE FROM cairn_job_events WHERE investigation_id=%s',(job_id,))
            elif action == 'share':
                if job['status'] != 'completed' or not job['result']:
                    raise AdmissionDenied('report_not_ready')
                token = secrets.token_urlsafe(32)
                db.execute('UPDATE cairn_web_jobs SET share_hash=%s WHERE investigation_id=%s',(token_hash(token),job_id))
                return dict(token=token)
            elif action == 'revoke':
                db.execute('UPDATE cairn_web_jobs SET share_hash=NULL WHERE investigation_id=%s',(job_id,))
            else:
                raise AdmissionDenied('invalid_action')
            return dict(ok=True)

    def shared(self, token):
        if len(token)>128:
            return None
        with self.connect() as db:
            row = db.execute('SELECT result FROM cairn_web_jobs WHERE share_hash=%s AND NOT deleted AND expires_at>now()', (token_hash(token),)).fetchone()
            return row[0] if row else None

    def request_allowance(self, account):
        with self.connect() as db:
            db.execute('INSERT INTO cairn_allowance_requests(account_id) VALUES (%s) ON CONFLICT DO NOTHING',(account,))

    def admin(self):
        with self.connect() as db:
            accounts = db.execute("SELECT a.account_id,a.suspended,a.run_limit,count(r.reservation_id) FILTER (WHERE r.state<>'released') AS used, EXISTS(SELECT 1 FROM cairn_allowance_requests q WHERE q.account_id=a.account_id) AS requested FROM cairn_accounts a LEFT JOIN cairn_reservations r USING(account_id) GROUP BY a.account_id ORDER BY a.created_at DESC LIMIT 200")
            accounts = [dict(zip([c.name for c in accounts.description],r)) for r in accounts.fetchall()]
            trial = record(db.execute('SELECT run_limit,paused FROM cairn_trial'))
            jobs = db.execute('SELECT investigation_id,status,created_at,updated_at FROM cairn_web_jobs ORDER BY created_at DESC LIMIT 50')
            jobs = [dict(zip([c.name for c in jobs.description],r)) for r in jobs.fetchall()]
            return dict(accounts=accounts,trial=trial,jobs=jobs)

    def admin_update(self, actor, body):
        with self.connect() as db:
            if body.get('action') == 'trial' and type(body.get('paused')) is bool:
                db.execute('UPDATE cairn_trial SET paused=%s WHERE singleton',(body['paused'],))
            elif body.get('action') == 'account' and isinstance(body.get('account_id'),str) and type(body.get('run_limit')) is int and 0<=body['run_limit']<=100 and type(body.get('suspended')) is bool:
                db.execute('UPDATE cairn_accounts SET run_limit=%s,suspended=%s WHERE account_id=%s',(body['run_limit'],body['suspended'],body['account_id']))
                db.execute('DELETE FROM cairn_allowance_requests WHERE account_id=%s',(body['account_id'],))
            else:
                raise AdmissionDenied('invalid_admin_action')
            db.execute('INSERT INTO cairn_admin_audit(actor,action,details) VALUES (%s,%s,%s::jsonb)',(actor,body['action'],json.dumps(body)))

    def claim(self):
        with self.connect() as db:
            db.execute('SELECT pg_advisory_xact_lock(43821792)')
            if db.execute("SELECT 1 FROM cairn_web_jobs WHERE status='running' LIMIT 1").fetchone():
                return None
            if db.execute('SELECT paused FROM cairn_trial').fetchone()[0]:
                return None
            job = record(db.execute("SELECT * FROM cairn_web_jobs WHERE status='queued' AND NOT deleted AND expires_at>now() ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"))
            if job:
                db.execute("UPDATE cairn_web_jobs SET status='running',updated_at=now() WHERE investigation_id=%s",(job['investigation_id'],))
            return job

    def event(self, job_id, message, *, execution=False):
        with self.connect() as db:
            row = db.execute('SELECT cancel_requested FROM cairn_web_jobs WHERE investigation_id=%s FOR UPDATE',(job_id,)).fetchone()
            if not row or row[0]:
                raise AdmissionDenied('cancelled')
            if execution:
                transition(db.cursor(),job_id,'start')
            db.execute('INSERT INTO cairn_job_events(investigation_id,message) VALUES (%s,%s)',(job_id,message[:1000]))
            db.execute('UPDATE cairn_web_jobs SET updated_at=now() WHERE investigation_id=%s',(job_id,))

    def finish(self, job_id, result=None, error=None):
        with self.connect() as db:
            cancelled = db.execute('SELECT cancel_requested FROM cairn_web_jobs WHERE investigation_id=%s FOR UPDATE',(job_id,)).fetchone()[0]
            state = 'cancelled' if cancelled else ('failed' if error else 'completed')
            db.execute('UPDATE cairn_web_jobs SET status=%s,result=%s::jsonb,error=%s,updated_at=now() WHERE investigation_id=%s',(state,json.dumps(result) if result else None,error,job_id))
            if not transition(db.cursor(),job_id,'finish'):
                transition(db.cursor(),job_id,'release_before_execution')
            db.execute('INSERT INTO cairn_job_events(investigation_id,message) VALUES (%s,%s)',(job_id,'Investigation '+state+'.'))

    def purge(self, upload_root):
        # Only generated source filenames are ever removed. Audit/quota rows survive deletion.
        with self.connect() as db:
            expired = db.execute("SELECT investigation_id FROM cairn_web_jobs WHERE status='queued' AND expires_at<=now() FOR UPDATE").fetchall()
            for (job_id,) in expired:
                transition(db.cursor(),job_id,'release_before_execution')
                db.execute("UPDATE cairn_web_jobs SET status='failed',updated_at=now() WHERE investigation_id=%s",(job_id,))
            rows = db.execute("SELECT investigation_id,source_path FROM cairn_web_jobs WHERE status IN ('completed','failed','cancelled') AND source_path<>''").fetchall()
            for job_id, path in rows:
                if path == Path(path).name:
                    (upload_root/path).unlink(missing_ok=True)
                db.execute("UPDATE cairn_web_jobs SET source_path='' WHERE investigation_id=%s",(job_id,))
            db.execute("DELETE FROM cairn_job_events WHERE investigation_id IN (SELECT investigation_id FROM cairn_web_jobs WHERE expires_at<=now())")
            db.execute("UPDATE cairn_web_jobs SET report='',manifest='{}',result=NULL,error=NULL,share_hash=NULL,deleted=TRUE WHERE expires_at<=now() AND status NOT IN ('queued','running')")
