"""Archive a completed result set into a NEW directory; never overwrite evidence."""
from pathlib import Path
import argparse
import json
import shutil
from build import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);args=p.parse_args()
    native=sorted((ROOT/'runs').glob('*/summary.json'))[-1].parent
    arm=sorted((ROOT/'runs').glob('*/arm.json'))[-1].parent
    replay=sorted((ROOT/'runs').glob('replay_*/replay.json'))[-1].parent
    assert json.loads((native/'summary.json').read_text())['pass_all']
    assert json.loads((arm/'arm.json').read_text())['pass_all']
    assert (native/'REPORT.md').exists()
    files=[]
    for folder,name in [(native,'native'),(arm,'arm'),(replay,'replay')]:
        for source in folder.iterdir():
            if source.suffix in ('.json','.csv','.log','.txt','.md','.h','.map'):
                files.append((source,Path(name)/source.name))
    for name in ('cmake.json','cmake.log','cmake-reference.json'):
        files.append((ROOT/'runs'/name,Path('cmake')/name))
    files.append((ROOT/'build-cmake/Testing/Temporary/LastTest.log',Path('cmake/LastTest.log')))
    dest=args.destination.resolve();dest.mkdir(parents=True,exist_ok=False)
    for source,relative in files:
        target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    stacks='\n'.join(p.name+'\n'+p.read_text() for p in sorted(arm.glob('*.su')))
    (dest/'arm/stack-usage.txt').write_text(stacks,encoding='utf-8')
    print('Archived',len(files),'non-executable evidence files:',dest)

if __name__=='__main__':main()
