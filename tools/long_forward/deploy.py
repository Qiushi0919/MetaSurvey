"""One-time frozen paper runtime installation from a clean Git source commit.
No market request, no credential read, no schedule creation. Never overwrite.
"""
from pathlib import Path
import json, subprocess, os
from tools.long_forward import run
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT.parent/'metasurvey-forward-frozen-v1'
def install():
 run.check_freeze();git='/opt/homebrew/bin/git'
 def cmd(*a):return subprocess.check_output([git,'-C',str(ROOT),*a])
 if cmd('status','--porcelain'):raise ValueError('CLEAN_COMMITTED_SOURCE_REQUIRED')
 commit=cmd('rev-parse','HEAD').decode().strip()
 DEST.mkdir(mode=0o700,exist_ok=False)
 paths=cmd('ls-files','-z').decode().split('\0');pins={}
 for name in paths:
  if not name:continue
  p=ROOT/name
  if p.is_symlink():raise ValueError('NO_SYMLINK_SOURCE')
  out=DEST/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(p.read_bytes());out.chmod(0o400);pins[name]=run.sha(out)
 manifest=dict(kind='FrozenPaperRuntimeDeployment',version='1.0.0',directory=str(DEST),source_commit=commit,installed_at=run.stamp(),file_pins=pins,freeze_hash=run.sha(DEST/'docs/long-forward/Code-Freeze.json'))
 run.write(run.ARCHIVE/'Runtime-Deployment.json',manifest)
 return {'directory':str(DEST),'source_commit':commit,'files':len(pins),'deployment_hash':run.sha(run.ARCHIVE/'Runtime-Deployment.json')}
if __name__=='__main__':print(json.dumps(install()))
