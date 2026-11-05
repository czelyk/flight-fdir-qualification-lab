"""Read recorded C decisions and describe policy differences without accuracy claims."""
from pathlib import Path
import argparse
import hashlib
import json
from build import ROOT

def analyze(run,write=True):
    if write and not run.resolve().is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Archived results are immutable; write reports only under runs/.')
    summary=json.loads((run/'summary.json').read_text())
    cases=json.loads((run/'named.json').read_text())
    assert summary['pass_all'] and summary['c_stream_sha256']==summary['reference_stream_sha256']
    assert summary['total_trace_comparisons']==sum(summary[k] for k in ('named_trace_comparisons','exhaustive_trace_comparisons','seeded_trace_comparisons'))
    assert summary['total_event_comparisons']==sum(summary[k] for k in ('named_event_comparisons','exhaustive_event_comparisons','seeded_event_comparisons'))
    assert all(x['wrap_translation_invariant'] for x in summary['clock_translation'])
    selected={}
    for case in cases:
        assert case['reference_match'] and len(case['events'])==len(case['outputs'])
        if case['profile']!=0:continue
        trips=[e['now'] for e,out in zip(case['events'],case['outputs']) if out[1]]
        selected.setdefault(case['name'],{})[case['config']['policy']]=dict(first_alarm_tick=trips[0] if trips else None,
                                  final_alarm=case['outputs'][-1][1],final_quality=case['outputs'][-1][2])
    names=['one_sample_then_silence','same_tick_burst','gap_then_new_bad','nominal_cadence_agreement','qualified_then_stale']
    result=dict(pass_all=True,trace_comparisons=summary['total_trace_comparisons'],event_comparisons=summary['total_event_comparisons'],
                examples={name:selected[name] for name in names},physical_tests=False,accuracy_or_reliability_estimated=False)
    def label(x):return str(x) if x is not None else 'none'
    table='\n'.join('| '+name+' | '+' | '.join(label(selected[name][p]['first_alarm_tick']) for p in range(3))+' |' for name in names)
    report=f'''# Actual C/reference results

**{summary['total_trace_comparisons']:,} trace comparisons** and
**{summary['total_event_comparisons']:,} per-event comparisons** passed for the
three declared policy contracts. This comprises finite token enumeration,
seeded histories and named cases; reused profiles/policies/clock origins are
not independent physical failure modes.

- {summary['named_cases']} named input streams x two configurations x three policies.
- Eight-token histories of length {summary['enumeration_depth']}, two configurations,
  two clock origins and three policies: {summary['exhaustive_trace_comparisons']:,} comparisons.
- Seeded mixed histories: {summary['seeded_trace_comparisons']:,} comparisons,
  seed {summary['seed']}. The seed/generator are reproducible, not mission data.
- C and reference output/input stream SHA256 agree:
  `{summary['c_stream_sha256']}`.
- A second origin near uint32 wrap produces identical diagnostic output streams.

## Different contracts, different decisions

Synthetic configuration: trip dwell 4 ticks, clear dwell 3 ticks, maximum sample
age 6 ticks, observed-gap budget 2 ticks, count threshold 3. Tick units and
threshold values are deliberately not assigned to a mission.

| Named scenario | Count: first alarm tick | Hold timer | Observed-span |
|---|---:|---:|---:|
{table}

The hold timer may qualify one still-valid held measurement. The count policy
may qualify several admitted samples at one timestamp. The observed-span policy
waits for sufficiently separated endpoint observations and resets its run across
large gaps. These are explicit semantics, not measured false-positive rates.

In the gap example the observed policy does not qualify while the other policies
do. This can delay or prevent a useful trip if the gap budget is too tight. It
is not universally safer or preferable. Choose a contract against the actual
sampling, uncertainty and response requirements; this lab supplies none of those
mission requirements.

Staleness and invalid quality break pending evidence but preserve an already
asserted alarm. Alarm=false with unknown/stale data must not be interpreted as
healthy. All named output rows were obtained from the actual C bytes after a
byte-for-byte reference comparison; `named.csv` includes rejected inputs and
clock errors. No filter observes the physical signal between samples.
'''
    if write:
        (run/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (run/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path,nargs='?');args=p.parse_args()
    run=args.run or sorted((ROOT/'runs').glob('*/summary.json'))[-1].parent
    print(json.dumps(analyze(run.resolve()),indent=2))
