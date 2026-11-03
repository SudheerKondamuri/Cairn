"""Private account gateway; trusted web server supplies the service key."""
from __future__ import annotations
import hashlib
import json
import secrets
import tarfile
import copy
from datetime import datetime
from pathlib import Path
from flask import Blueprint, current_app, request
import psycopg
from .allowances import AdmissionDenied
from .web_store import WebStore
from .investigation_validation import validate_investigation_form
from core.bundles import validate_source_archive, BundleValidationError
from core.github import download_archive, GitHubSourceError


def serialize(value):
    if isinstance(value,datetime): return value.isoformat()
    if isinstance(value,dict): return {k:serialize(v) for k,v in value.items()}
    if isinstance(value,list): return [serialize(v) for v in value]
    return value


def register_web(app):
    bp = Blueprint('accounts',__name__,url_prefix='/api/web')
    store = WebStore(app.config['DATABASE_URL'])
    app.extensions['web_store'] = store

    @bp.before_request
    def require_service():
        if app.config.get('LOCAL_ACCESS') and request.headers.get('X-Cairn-Local') == 'true':
            return None
        key = current_app.config['API_KEY']
        if not key or not secrets.compare_digest(request.headers.get('X-Cairn-API-Key',''),key):
            return {'error':'Service authentication required.'},401

    def identity():
        if app.config['LOCAL_ACCESS'] and request.headers.get('X-Cairn-Local') == 'true':
            return store.local_account()
        user = store.identity(request.headers.get('X-Cairn-Session',''))
        if not user: raise AdmissionDenied('sign_in_required')
        return user

    def is_admin(user):
        if app.config['LOCAL_ACCESS'] and user['account_id'] == 'acct-local': return True
        allowed = set(app.config['ADMIN_IDENTITIES'].split(','))
        return bool(allowed.intersection(user['identities']))

    @bp.errorhandler(AdmissionDenied)
    def denied(exc):
        code=exc.code
        status=401 if code=='sign_in_required' else 404 if code=='not_found' else 403 if code in ('admin_required','account_unavailable') else 409
        return {'error':code.replace('_',' '),'code':code},status

    @bp.errorhandler(psycopg.Error)
    def unavailable(exc):
        app.logger.error('Account database operation failed: %s',type(exc).__name__)
        return {'error':'Account service temporarily unavailable.'},503

    @bp.post('/sessions')
    def login():
        body=request.get_json(silent=True) or {}
        provider,subject=body.get('provider'),body.get('subject')
        if provider not in ('google','github') or not isinstance(subject,str) or not 1<=len(subject)<=255:
            return {'error':'Invalid identity.'},400
        return {'token':store.login(provider,subject)},201

    @bp.delete('/sessions')
    def logout():
        store.logout(request.headers.get('X-Cairn-Session',''))
        return {'ok':True}

    @bp.get('/me')
    def me():
        user=identity()
        return {'account_id':user['account_id'],'admin':is_admin(user),'local':user['account_id']=='acct-local','identities':user['identities'],'allowance':store.allowance(user['account_id'])}

    @bp.post('/allowance-request')
    def request_more():
        store.request_allowance(identity()['account_id'])
        return {'ok':True}

    @bp.get('/investigations')
    def history():
        user=identity()
        return serialize(store.history(user['account_id'],request.args.get('q','')[:100],request.args.get('status','')[:20],request.args.get('cursor','')[:100]))

    @bp.post('/investigations')
    def submit():
        user=identity()
        key=request.headers.get('Idempotency-Key','')
        if not 16<=len(key)<=128: return {'error':'A valid submission identifier is required.'},400
        if request.content_length and request.content_length>11*1024*1024: return {'error':'Upload limit is 10 MiB.'},413
        source=request.files.get('source')
        url=request.form.get('github_url','')
        if bool(source)==bool(url): return {'error':'Choose an archive or a public GitHub repository.'},400
        try:
            spec=validate_investigation_form(request.form.get('report'),request.form.get('manifest'))
            root=Path(app.config['UPLOAD_ROOT']); root.mkdir(parents=True,exist_ok=True)
            path=root/('src-'+secrets.token_hex(16)+'.tar.gz')
            try:
                if source:
                    source.save(path)
                else:
                    download_archive(url,path,ref=request.form.get('github_ref','').strip() or 'HEAD',max_bytes=10*1024*1024)
                if path.stat().st_size>10*1024*1024: raise ValueError('Source exceeds 10 MiB.')
                members = validate_source_archive(path)
                if url:
                    # GitHub archives wrap the repository in one generated directory.
                    roots = {m.name.split('/')[0] for m in members}
                    if len(roots) != 1: raise ValueError('Unexpected GitHub archive layout.')
                    normalized = path.with_suffix('.normalized')
                    try:
                        with tarfile.open(path, 'r:*') as incoming, tarfile.open(normalized, 'w:gz') as outgoing:
                            for member in members:
                                relative = member.name.partition('/')[2]
                                if not relative: continue
                                info = copy.copy(member); info.name = relative
                                outgoing.addfile(info, incoming.extractfile(member) if member.isfile() else None)
                        normalized.replace(path)
                    finally:
                        normalized.unlink(missing_ok=True)
                    validate_source_archive(path)
                digest=hashlib.sha256(path.read_bytes()+json.dumps(spec.as_dict(),sort_keys=True).encode()).hexdigest()
                job_id,created=store.submit(user['account_id'],key,digest,spec.report,spec.as_dict(),path.name)
                if not created: path.unlink(missing_ok=True)
                return {'investigation_id':job_id,'status':'queued'},202
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        except (ValueError,BundleValidationError,GitHubSourceError) as exc:
            if isinstance(exc,AdmissionDenied): raise
            return {'error':str(exc)[:300],'message':str(exc)[:300]},400
        except OSError:
            return {'error':'Source storage is unavailable.'},503

    @bp.get('/investigations/<job_id>')
    def detail(job_id):
        job=store.get(identity()['account_id'],job_id)
        if not job: raise AdmissionDenied('not_found')
        return serialize(job)

    @bp.post('/investigations/<job_id>/<action>')
    def action(job_id,action):
        return store.action(identity()['account_id'],job_id,action)

    @bp.get('/shared/<token>')
    def shared(token):
        result=store.shared(token)
        if result is None: raise AdmissionDenied('not_found')
        return result

    @bp.route('/admin',methods=['GET','POST'])
    def admin():
        user=identity()
        if not is_admin(user): raise AdmissionDenied('admin_required')
        if request.method=='POST':
            store.admin_update(user['account_id'],request.get_json(silent=True) or {})
            return {'ok':True}
        return serialize(store.admin())

    app.register_blueprint(bp)
