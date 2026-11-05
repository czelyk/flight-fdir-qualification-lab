"""Replay a named input stream through C and show every diagnostic state."""
import argparse
import csv
import datetime
import hashlib
import json
import uuid
from cases import named_cases,PROFILES,POLICIES
from build import ROOT
from native import Native,unpack,expected_bytes
from reference import FIELDS,reference

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scenario',choices=list(named_cases()),default='one_sample_then_silence')
    p.add_argument('--policy',choices=POLICIES,default='observed')
    p.add_argument('--run',help='Completed native run; newest by default')
    args=p.parse_args()
    previous=(ROOT/args.run).resolve() if args.run else sorted((ROOT/'runs').glob('*/summary.json'))[-1].parent
    meta=json.loads((previous/'build.json').read_text())
    for path,digest in meta['source_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
            raise SystemExit('C source changed; run tools/run_tests.py first.')
    native=Native(meta['library'])
    cfg=dict(PROFILES[0],policy=POLICIES.index(args.policy));events=named_cases()[args.scenario]
    actual=native.trace(cfg,events);expected=reference(cfg,events)
    assert actual==expected_bytes(expected)
    out=ROOT/'runs'/('replay_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]);out.mkdir()
    rows=[dict(event=e,output=dict(zip(FIELDS,x))) for e,x in zip(events,unpack(actual))]
    (out/'replay.json').write_text(json.dumps(dict(pass_all=True,scenario=args.scenario,config=cfg,rows=rows,physical_test=False),indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(out),scenario=args.scenario,policy=args.policy,rows=rows),indent=2))

if __name__=='__main__':main()
