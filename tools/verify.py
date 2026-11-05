"""Read-only, dependency-free verification of frozen source and named C outputs."""
from pathlib import Path
import hashlib
import json
from analyze import analyze
from build import ROOT
from reference import reference

def main():
    manifest=json.loads((ROOT/'provenance/manifest.json').read_text())
    for item in manifest['files']:
        path=(ROOT/item['path']).resolve();assert path.is_relative_to(ROOT.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],item['path']
    summary=json.loads((ROOT/'results/native/summary.json').read_text())
    cases=json.loads((ROOT/'results/native/named.json').read_text())
    for case in cases:
        assert [list(x) for x in reference(case['config'],case['events'])]==case['outputs'],case['name']
    analysis=analyze(ROOT/'results/native',write=False)
    assert json.loads(json.dumps(analysis))==json.loads((ROOT/'results/native/analysis.json').read_text())
    for path,digest in summary['source_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    arm=json.loads((ROOT/'results/arm/arm.json').read_text())
    assert arm['pass_all'] and not arm['physical_tests']
    for path,digest in arm['source_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    assert hashlib.sha256((ROOT/'results/arm/vectors.h').read_bytes()).hexdigest()==arm['vector_sha256']
    assert json.loads((ROOT/'results/replay/replay.json').read_text())['pass_all']
    assert json.loads((ROOT/'results/cmake/cmake-reference.json').read_text())['pass_all']
    print(json.dumps(dict(pass_all=True,hashed_files=len(manifest['files']),trace_comparisons=summary['total_trace_comparisons'],
                         event_comparisons=summary['total_event_comparisons'],arm_traces=arm['traces'],physical_tests=False),indent=2))

if __name__=='__main__':main()
