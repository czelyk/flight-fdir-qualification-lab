"""Local C99 builds. No third-party runtime library or system installation."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]

def compiler(zig=None,cc=None):
    if zig:return [str(Path(zig).resolve()),'cc']
    if cc:return [cc]
    for name in ('gcc','clang','cc'):
        if shutil.which(name):return [shutil.which(name)]
    if os.name=='nt':
        from bootstrap_zig import bootstrap
        return [str(bootstrap()),'cc']
    raise RuntimeError('Install GCC/Clang or select --cc/--zig.')

def execute(command,cwd,log,timeout=180):
    r=subprocess.run([str(x) for x in command],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    log.write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:raise RuntimeError(f'Command failed; see {log}\n{r.stderr[-1500:]}')
    return r.stdout

def build(zig=None,cc=None):
    driver=compiler(zig,cc)
    run=ROOT/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]);run.mkdir(parents=True)
    suffix='.dll' if os.name=='nt' else '.so'
    library=run/('fq'+suffix)
    flags=['-std=c99','-O2','-Wall','-Wextra','-Werror','-Iinclude']
    command=driver+flags+['-shared']+([] if os.name=='nt' else ['-fPIC'])+['src/fq_monitor.c','tests/bridge.c','-o',str(library)]
    execute(command,ROOT,run/'library-build.log')
    unit=run/('unit.exe' if os.name=='nt' else 'unit')
    execute(driver+flags+['src/fq_monitor.c','tests/unit.c','-o',str(unit)],ROOT,run/'unit-build.log')
    execute([unit],run,run/'unit.log')
    version=execute(driver+['--version'],ROOT,run/'compiler.txt').splitlines()[0]
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('include','src','tests') for p in sorted((ROOT/folder).glob('*')) if p.suffix in ('.c','.h')}
    record=dict(compiler=version,library=str(library),command=command,source_sha256=source_hashes,physical_tests=False)
    (run/'build.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return run,library,record
