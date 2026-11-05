"""Build a checked source ZIP. No upload, remote creation or repository mutation."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from build import ROOT
from make_manifest import paths

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT.parent/(ROOT.name+'-source.zip'));args=p.parse_args()
    subprocess.run([sys.executable,ROOT/'tools/verify.py'],cwd=ROOT,check=True)
    names=paths();manifest=json.loads((ROOT/'provenance/manifest.json').read_text())
    assert set(names)=={x['path'] for x in manifest['files']}|{'provenance/manifest.json'}
    assert not any(x.startswith(('.git/','.tools/','.venv/','runs/','build')) for x in names)
    target=args.output.resolve();target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in names:z.write(ROOT/name,ROOT.name+'/'+name)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name in names:assert z.read(ROOT.name+'/'+name)==(ROOT/name).read_bytes()
    print(json.dumps(dict(archive=str(target),files=len(names),bytes=target.stat().st_size,
                         sha256=hashlib.sha256(target.read_bytes()).hexdigest(),uploaded=False),indent=2))
if __name__=='__main__':main()
