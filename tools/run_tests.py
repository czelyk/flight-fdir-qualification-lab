"""Real C/reference comparisons, finite enumeration and seeded event histories."""
from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import itertools
import json
import struct
import sys
import time
from build import ROOT,build
from cases import PROFILES,POLICIES,TOKENS,expand,named_cases,random_cases
from native import Native,unpack,expected_bytes
from reference import reference,FIELDS

def source_hashes():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ('include','src','tests','tools') for p in sorted((ROOT/d).glob('*'))
            if p.suffix in ('.c','.h','.py')}

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group();g.add_argument('--zig');g.add_argument('--cc')
    p.add_argument('--quick',action='store_true',help='length-three enumeration, named cases and seeded histories')
    args=p.parse_args();run,library,build_record=build(args.zig,args.cc)
    native=Native(library)
    total_traces=total_events=0
    sha_c=hashlib.sha256();sha_ref=hashlib.sha256()
    counts={};named=[]
    def check(cfg,events,label):
        nonlocal total_traces,total_events
        expected=reference(cfg,events);expected_raw=expected_bytes(expected);actual=native.trace(cfg,events)
        if actual!=expected_raw:
            failure=dict(label=label,config=cfg,events=events,expected=expected,actual=unpack(actual))
            (run/'failure.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
            raise AssertionError('C/reference mismatch: '+str(run/'failure.json'))
        prefix=json.dumps([cfg,events],sort_keys=True,separators=(',',':')).encode()
        sha_c.update(prefix);sha_c.update(actual);sha_ref.update(prefix);sha_ref.update(expected_raw)
        total_traces+=1;total_events+=len(events)
        return actual,expected
    fixtures=named_cases()
    for profile_index,profile in enumerate(PROFILES):
        for name,events in fixtures.items():
            for policy in range(3):
                cfg=dict(profile,policy=policy)
                actual,expected=check(cfg,events,'named/'+name)
                named.append(dict(profile=profile_index,name=name,config=cfg,events=events,
                                  outputs=unpack(actual),reference_match=True))
    # Explicit semantic witnesses, not just agreement with a second implementation.
    lookup={(x['name'],x['config']['policy']):x['outputs'] for x in named if x['profile']==0}
    assert lookup['one_sample_then_silence',1][1][1]==1
    assert lookup['one_sample_then_silence',2][1][1]==0
    assert lookup['same_tick_burst',0][-1][1]==1 and lookup['same_tick_burst',2][-1][1]==0
    assert lookup['qualified_then_stale',2][-1][1:3]==(1,2)
    assert lookup['pre_epoch_queue_item',2][2][0]==1
    assert lookup['nominal_cadence_agreement',0][-1][1]==lookup['nominal_cadence_agreement',2][-1][1]
    named_traces=total_traces;named_events=total_events
    depth=3 if args.quick else 5
    translation=[]
    print('Named cases passed; enumerating token histories...',flush=True)
    for profile_index,profile in enumerate(PROFILES):
        clock_digests=[]
        for base in (0,0xfffffffc):
            digest=hashlib.sha256();start=total_traces
            for tokens in itertools.product(TOKENS,repeat=depth):
                events=expand(tokens,profile,base)
                for policy in range(3):
                    actual,_=check(dict(profile,policy=policy),events,'finite-enumeration')
                    digest.update(actual)
            clock_digests.append(digest.hexdigest())
            print(f'profile={profile_index} clock=0x{base:08x}: {total_traces-start} traces passed',flush=True)
        assert clock_digests[0]==clock_digests[1], 'Clock translation changed semantics'
        translation.append(dict(profile=profile_index,output_sha256=clock_digests[0],wrap_translation_invariant=True))
    exhaustive_traces=total_traces-named_traces;exhaustive_events=total_events-named_events
    for profile in PROFILES:
        for events in random_cases():
            for policy in range(3):check(dict(profile,policy=policy),events,'seeded-history')
    with (run/'named.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['profile','scenario','policy','event_index','kind','now','acquired','sequence','value',*FIELDS])
        for case in named:
            for index,(event,out) in enumerate(zip(case['events'],case['outputs'])):
                writer.writerow([case['profile'],case['name'],POLICIES[case['config']['policy']],index,
                                 *[event[k] for k in ('kind','now','acquired','sequence','value')],*out])
    (run/'named.json').write_text(json.dumps(named,indent=2),encoding='utf-8')
    assert sha_c.hexdigest()==sha_ref.hexdigest()
    summary=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pass_all=True,
                 compiler=build_record['compiler'],monitor_bytes=native.lib.fq_abi(3),named_cases=len(fixtures),
                 named_trace_comparisons=named_traces,named_event_comparisons=named_events,
                 enumeration_depth=depth,alphabet=list(TOKENS),profiles=PROFILES,policies=list(POLICIES),
                 exhaustive_trace_comparisons=exhaustive_traces,exhaustive_event_comparisons=exhaustive_events,
                 seeded_trace_comparisons=total_traces-exhaustive_traces-named_traces,
                 seeded_event_comparisons=total_events-exhaustive_events-named_events,
                 seed=20261104,total_trace_comparisons=total_traces,total_event_comparisons=total_events,
                 c_stream_sha256=sha_c.hexdigest(),reference_stream_sha256=sha_ref.hexdigest(),
                 clock_translation=translation,source_sha256=source_hashes(),physical_tests=False,
                 target_timing=False,independent_peer_review=False,
                 scope='Bounded synthetic token enumeration and seeded histories, not all inputs or flight reliability')
    (run/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),pass_all=True,traces=total_traces,events=total_events,
                         stream_sha256=sha_c.hexdigest(),monitor_bytes=summary['monitor_bytes']),indent=2))

if __name__=='__main__':main()
