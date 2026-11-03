"""Exercise guest installer selection without installing anything on the host."""
import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

@pytest.mark.parametrize('runtime,filename,scripts,expected',[
 ('python','requirements.txt',False,['python3','-m','pip','install']),
 ('node','package-lock.json',False,['npm','ci']),
 ('node','package.json',True,['npm','install']),
 ('go','go.mod',False,['go','mod','download']),
])
def test_installs_in_project_directory(tmp_path,monkeypatch,capsys,runtime,filename,scripts,expected):
 spec=importlib.util.spec_from_file_location('guest_install',Path('guest/dependency-install.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 project=tmp_path/'app';project.mkdir();(project/filename).write_text('')
 monkeypatch.setattr(module,'ROOT',tmp_path)
 # Redirect dependency target creation; no host package manager is executed.
 mkdir=Path.mkdir
 monkeypatch.setattr(Path,'mkdir',lambda self,*a,**k: None if str(self)=='/input/deps' else mkdir(self,*a,**k))
 calls=[]
 def run(command,**kwargs):
  calls.append((command,kwargs));return SimpleNamespace(returncode=0,stdout='installed',stderr='')
 monkeypatch.setattr(module.subprocess,'run',run)
 encode=lambda x:base64.urlsafe_b64encode(x.encode()).decode()
 monkeypatch.setattr(module.sys,'argv',['install',*[encode(x) for x in (runtime,'controlled_network',str(scripts).lower(),'app')]])
 assert module.main()==0
 command,kwargs=calls[0];assert command[:len(expected)]==expected
 assert kwargs['cwd']==project and kwargs['timeout']==270
 if runtime=='python':assert '--only-binary=:all:' in command
 if runtime=='node':assert ('--ignore-scripts' in command)==(not scripts)
 assert json.loads(capsys.readouterr().out)['installed'] is True

def test_github_404_explains_repository_and_ref(monkeypatch,tmp_path):
 import urllib.error
 from core.github import download_archive,GitHubSourceError
 class Opener:
  def open(self,*args,**kwargs):raise urllib.error.HTTPError('https://github.com/example/repo',404,'missing',{},None)
 monkeypatch.setattr('core.github.urllib.request.build_opener',lambda *args:Opener())
 with pytest.raises(GitHubSourceError,match='Repository or branch not found'):
  download_archive('https://github.com/example/repo',tmp_path/'source.tar.gz',ref='HEAD')
 assert not (tmp_path/'source.tar.gz').exists()
