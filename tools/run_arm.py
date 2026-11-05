"""Cross-compile the same monitor and execute named/seeded stream cases in ARM."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import struct
import uuid
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0
from build import ROOT,execute
from cases import PROFILES,named_cases,random_cases
from reference import reference

def cval(x):
    if x==-2147483648:return 'INT32_MIN'
    if x<0:return str(x)
    return 'UINT32_C('+str(x)+')'

def make_vectors(run):
    cases=[]
    samples=list(named_cases().values())+list(random_cases(n=8))
    lines=['/* Generated test vectors from list-based Python reference. */',
           'typedef struct { fq_config_t cfg; const fq_event_t *events; const fq_output_t *expected; uint32_t count; } arm_case_t;']
    for profile in PROFILES:
        for events in samples:
            for policy in range(3):
                cfg=dict(profile,policy=policy);expected=reference(cfg,events);index=len(cases)
                lines.append('static const fq_event_t events_'+str(index)+'[] = {')
                for e in events:lines.append('{'+','.join(cval(e[k]) for k in ('kind','now','acquired','sequence','value'))+'},')
                lines.append('};\nstatic const fq_output_t expected_'+str(index)+'[] = {')
                for out in expected:lines.append('{'+','.join(cval(x) for x in out)+'},')
                lines.append('};');cases.append((cfg,len(events)))
    lines.append('static const arm_case_t arm_cases[] = {')
    keys=('trip_limit','clear_limit','trip_ticks','clear_ticks','max_age','max_gap','samples','policy')
    for index,(cfg,count) in enumerate(cases):
        lines.append('{{'+','.join(cval(cfg[k]) for k in keys)+'},events_'+str(index)+',expected_'+str(index)+','+str(count)+'},')
    lines.append('};\n#define ARM_CASE_COUNT '+str(len(cases))+'u\n')
    vector=run/'vectors.h';vector.write_text('\n'.join(lines),encoding='utf-8')
    return len(cases),sum(count for _,count in cases),vector

def main():
    p=argparse.ArgumentParser();p.add_argument('--gcc',default=os.environ.get('ARM_GCC') or shutil.which('arm-none-eabi-gcc'))
    args=p.parse_args()
    if not args.gcc:raise SystemExit('Install Arm GNU Toolchain or set ARM_GCC.')
    run=ROOT/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_arm_'+uuid.uuid4().hex[:6]);run.mkdir(parents=True)
    count,events,vector=make_vectors(run);elf=run/'fixture.elf';gcc=Path(args.gcc).resolve()
    flags=['-mcpu=cortex-m4','-mthumb','-O2','-std=c99','-ffreestanding','-fno-builtin',
           '-ffunction-sections','-fdata-sections','-fstack-usage','-I'+str(ROOT/'include')]
    command=[gcc,*flags,'-nostartfiles','-nostdlib','-I'+str(run),ROOT/'src/fq_monitor.c',ROOT/'tests/arm_fixture.c',
             '-T',ROOT/'cmake/arm-emulation.ld','-Wl,--gc-sections','-Wl,-Map='+str(run/'fixture.map'),'-lc','-lgcc','-o',elf]
    execute(command,run,run/'build.log')
    execute([gcc,*flags,'-Wall','-Wextra','-Werror','-c',ROOT/'src/fq_monitor.c','-o',run/'monitor.o'],run,run/'object-build.log')
    nm=gcc.with_name('arm-none-eabi-nm'+gcc.suffix)
    undefined=execute([nm,'-u',elf],run,run/'undefined.txt');assert not undefined.strip()
    symbols_text=execute([nm,elf],run,run/'symbols.txt')
    assert not any(line.split()[-1] in ('malloc','calloc','realloc','_sbrk') for line in symbols_text.splitlines())
    with elf.open('rb') as f:
        e=ELFFile(f);u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        u.mem_map(0x10000,0x40000);u.mem_map(0x20000000,0x20000)
        for segment in e.iter_segments():
            if segment['p_type']=='PT_LOAD' and segment['p_filesz']:u.mem_write(segment['p_vaddr'],segment.data())
        symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
    stop=0x4f000
    u.reg_write(UC_ARM_REG_SP,0x2001fff8);u.reg_write(UC_ARM_REG_LR,stop|1)
    u.emu_start(symbols['arm_smoke']|1,stop,timeout=60_000_000,count=100_000_000)
    assert u.reg_read(UC_ARM_REG_PC)==stop,'Execution bound reached'
    result=struct.unpack('<8I',bytes(u.mem_read(symbols['arm_results'],32)))
    assert u.reg_read(UC_ARM_REG_R0)==0 and result[:2]==(count,events),result
    size_tool=gcc.with_name('arm-none-eabi-size'+gcc.suffix)
    sizes=execute([size_tool,'-B',elf,run/'monitor.o'],run,run/'size.txt')
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'src/fq_monitor.c',ROOT/'include/fq_monitor.h',ROOT/'tests/arm_fixture.c',ROOT/'tools/reference.py',ROOT/'tools/cases.py']}
    record=dict(pass_all=True,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                traces=count,event_comparisons=events,monitor_bytes=result[2],output_bytes=result[3],
                compiler=execute([gcc,'--version'],run,run/'compiler.txt').splitlines()[0],
                command=[str(x) for x in command],source_sha256=hashes,vector_sha256=hashlib.sha256(vector.read_bytes()).hexdigest(),
                elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),size_output=sizes,no_dynamic_allocator_symbols=True,
                physical_tests=False,target_timing=False,scope='Actual Cortex-M4 instructions on synthetic stream cases, including input gaps and clock wrap; no peripheral or physical fault campaign')
    (run/'arm.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),pass_all=True,traces=count,events=events,monitor_bytes=result[2],sizes=sizes),indent=2))

if __name__=='__main__':main()
