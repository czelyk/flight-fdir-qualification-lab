"""Maintainer utility: freeze reviewed Git-eligible source/evidence; self excluded."""
import hashlib
import json
import subprocess
from build import ROOT

def paths():
    raw=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z']).decode('utf-8')
    return sorted(set(x for x in raw.split('\0') if x))
def main():
    files=[]
    for name in paths():
        if name=='provenance/manifest.json':continue
        p=ROOT/name;assert p.is_file() and p.stat().st_size<20_000_000,name
        files.append(dict(path=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (ROOT/'provenance/manifest.json').write_text(json.dumps(dict(format=1,files=files),indent=2),encoding='utf-8')
    print('Frozen',len(files),'files')
if __name__=='__main__':main()
