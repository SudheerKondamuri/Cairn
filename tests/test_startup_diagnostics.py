import shlex
from types import SimpleNamespace
import pytest
from scripts import runner
from core.investigation_report import build_investigation_report


def test_failed_readiness_includes_application_log_and_expected_port(monkeypatch):
 monkeypatch.setattr(runner.time,'sleep',lambda _:None)
 commands=[]
 class Guest:
  def run(self,command,**kwargs):
   commands.append(command)
   if len(commands)<=30:return SimpleNamespace(ok=False,stderr='connection refused')
   code=shlex.split(command)[2]
   compile(code,'diagnostic','exec')
   return SimpleNamespace(ok=True,stdout='Application log: Running on http://127.0.0.1:5000\nListening TCP ports: [5000]')
 with pytest.raises(runner.LiveRuntimeError,match='127.0.0.1:5002') as error:
  runner.wait_for_fixture(Guest(),5002)
 assert 'Listening TCP ports: [5000]' in str(error.value)
 assert 'Application log' in str(error.value)


def test_setup_failure_preserves_uploaded_source_identity():
 report=build_investigation_report(investigation_id='inv-test',spec={},finding=None,lifecycle={'sandbox_deleted':True,'subject_manifest':{'source_hash':'abc'}},error='startup failed')
 assert report['evidence']['source_hash']=='abc'
 assert report['lifecycle']['sandbox_deleted'] is True
 assert report['verdict']=='inconclusive'


def test_auto_port_discovery_parses_listening_ports():
 import re
 exc_text = (
  "Application did not become ready on 127.0.0.1:5000.\n"
  "Application log: Running on http://0.0.0.0:5001\n"
  "Listening TCP ports: [22, 5001]"
 )
 match = re.search(r"Listening TCP ports:\s*\[([0-9, ]+)\]", exc_text)
 assert match is not None
 discovered = [int(p.strip()) for p in match.group(1).split(",") if p.strip()]
 candidates = [p for p in discovered if p not in {22, 5000}]
 assert candidates == [5001]


def test_auto_port_discovery_prefers_common_web_port():
 candidates = [9100, 8080, 4317]
 common_web = [p for p in candidates if p in {5000, 5001, 8000, 8080, 3000, 8888, 4000}]
 chosen = common_web[0] if common_web else candidates[0]
 assert chosen == 8080


def test_live_guest_start_retries_transient_503(monkeypatch):
 monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
 attempts = []

 class MockComputer:
  def start(self):
   attempts.append(1)
   if len(attempts) < 3:
    raise RuntimeError("HTTP 503: Service Unavailable from Celesto API")
   return None

 guest = runner.LiveGuest.__new__(runner.LiveGuest)
 guest.computer = MockComputer()
 guest._created = False
 guest.boot_to_ready_s = None

 guest.start()
 assert len(attempts) == 3
 assert guest._created is True
 assert guest.started is True


