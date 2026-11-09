"""Compare first alarm timing against compiled NASA LC code on labeled synthetic signals."""
import argparse
import csv
import ctypes as ct
from dataclasses import dataclass
import hashlib
import itertools
import json
import os
import re
import urllib.request

from build import ROOT, build, compiler, execute
from cases import event, POLICIES
from native import Native, unpack

REVISION = "c9104f85b3a9b795be5c67702c8e190b36e4cdd5"
UPSTREAM = {
    "lc_action.c": ("d1f94ee481ea3de89fcf5e5169e5fcb55c7ead08864b9a15bd06c7e2696136dd",
                    ("LC_SampleSingleAP", "LC_SampleAPs")),
    "lc_cmds.c": ("6578bc4524755f0df72c37270c8df9b9e3c4ce8294a8b91d03c6a76f424ce4f6",
                  ("LC_SampleAPReq",)),
}
CACHE = ROOT / ".tools" / ("lc-" + REVISION)
ARCHIVE = ROOT / "results/lc-alarm"
HORIZON, DWELL, PERIOD = 40, 4, 2
CONFIG = dict(trip_limit=20, clear_limit=10, trip_ticks=DWELL, clear_ticks=DWELL,
              max_age=5, max_gap=4, samples=3)
LC_SETTINGS = {
    "lc_age_1": (2, 1),
    "lc_age_2": (2, 2),
    "lc_age_3": (2, 3),
    "lc_fast_age_2": (1, 2),
    "lc_fast_age_4": (1, 4),
    "lc_fast_age_6": (1, 6),
}
ALIGNED = ("nominal", "lag_2", "drop_onset", "drop_after_first", "drop_recovery")
OFF_GRID = ("lag_1", "alternate_lag", "irregular_capture", "clustered_capture")
DELIVERIES = ALIGNED + OFF_GRID
METHODS = (*POLICIES, *LC_SETTINGS)
OUTCOMES = ("timely", "before_dwell", "after_recovery", "missed", "no_alarm_expected")


def load_source(filename, expected):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / filename
    url = f"https://raw.githubusercontent.com/nasa/LC/{REVISION}/fsw/src/{filename}"
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"NASA source hash mismatch: {filename}")
    if not path.exists():
        path.write_bytes(data)
    return data.decode("utf-8"), url


def build_lc(run, driver):
    functions, sources = [], {}
    for filename, (digest, names) in UPSTREAM.items():
        source, url = load_source(filename, digest)
        for name in names:
            match = re.search(rf"^void {name}\([^\n]*\)\n\{{\n.*?^\}}", source, re.M | re.S)
            if match is None:
                raise RuntimeError(f"Cannot locate the pinned function {name}")
            functions.append(match.group())
        sources[filename] = {"url": url, "sha256": digest, "functions": list(names)}
    (run / "lc-extract.inc").write_text("\n\n".join(functions) + "\n", encoding="utf-8", newline="\n")
    library = run / ("lc-probe.dll" if os.name == "nt" else "lc-probe.so")
    shared = ["-shared"] if os.name == "nt" else ["-shared", "-fPIC"]
    flags = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", *shared]
    execute([*driver, *flags, "-I", run, "experiments/lc_alarm_probe.c", "-o", library],
            ROOT, run / "lc-build.log")
    probe = ct.CDLL(str(library))
    probe.lc_probe_reset.argtypes = [ct.c_uint]
    probe.lc_probe_reset.restype = None
    probe.lc_probe_update.argtypes = [ct.c_uint, ct.c_uint]
    probe.lc_probe_update.restype = None
    probe.lc_probe_evaluate.argtypes = []
    probe.lc_probe_evaluate.restype = ct.c_uint
    return probe, sources


@dataclass(frozen=True)
class Case:
    onset: int
    duration: int
    delivery: str

    @property
    def recovery(self):
        return self.onset + self.duration

    def signal_bad(self, time):
        return self.onset <= time < self.recovery

    def messages(self):
        first = self.onset + (-self.onset % PERIOD)
        if self.delivery == "irregular_capture":
            return {tick: tick for tick in range(HORIZON + 1) if tick % 4 < 2}
        if self.delivery == "clustered_capture":
            return {tick: tick for tick in range(HORIZON + 1) if tick % 6 < 3}
        if self.delivery == "alternate_lag":
            return {tick + index % 2: tick for index, tick in enumerate(range(0, HORIZON, PERIOD))}
        omissions = {
            "drop_onset": range(first, first + 6),
            "drop_after_first": range(first + PERIOD, first + 8),
            "drop_recovery": range(self.recovery, self.recovery + 6),
        }.get(self.delivery, ())
        lag = {"lag_1": 1, "lag_2": 2}.get(self.delivery, 0)
        return {capture + lag: capture for capture in range(0, HORIZON + 1 - lag, PERIOD)
                if capture not in omissions}

    def classify(self, alarm):
        if alarm is None:
            return "missed" if self.duration > DWELL else "no_alarm_expected"
        if alarm >= self.recovery:
            return "after_recovery"
        if alarm < self.onset + DWELL:
            return "before_dwell"
        return "timely"


def lab_alarms(native, case, messages):
    events = [event(1, tick, messages[tick], sequence=messages[tick],
                    value=25 if case.signal_bad(messages[tick]) else 5)
              if tick in messages else event(0, tick) for tick in range(HORIZON + 1)]
    results = {}
    for policy, name in enumerate(POLICIES):
        output = unpack(native.trace(dict(CONFIG, policy=policy), events))
        results[name] = next((tick for tick, entry in enumerate(output) if entry[1]), None)
    return results


def lc_alarm(probe, case, messages, period, age):
    probe.lc_probe_reset(DWELL // period + 1)
    for tick in range(HORIZON + 1):
        if tick in messages:
            probe.lc_probe_update(case.signal_bad(messages[tick]), age)
        if tick % period == 0 and probe.lc_probe_evaluate():
            return tick
    return None


def scenarios():
    durations = (0, 2, 3, 4, 5, 6, 8, 12, 18)
    for delivery in DELIVERIES:
        onsets = range(6, 12) if delivery == "clustered_capture" else (8, 9)
        for onset, duration in itertools.product(onsets, durations):
            yield Case(onset, duration, delivery)


def run_cases(native, probe):
    rows = []
    for case in scenarios():
        messages = case.messages()
        alarms = lab_alarms(native, case, messages)
        alarms.update({name: lc_alarm(probe, case, messages, *setting)
                       for name, setting in LC_SETTINGS.items()})
        for method, alarm in alarms.items():
            outcome = case.classify(alarm)
            rows.append(dict(onset=case.onset, duration=case.duration, recovery=case.recovery,
                             delivery=case.delivery, method=method, first_alarm=alarm, outcome=outcome,
                             extra_delay=alarm - case.onset - DWELL if outcome == "timely" else None,
                             arrivals=" ".join(f"{arrival}:{capture}" for arrival, capture in messages.items())))
    return rows


def check_controls(native, probe, rows):
    nominal = [row for row in rows if row["delivery"] == "nominal" and row["onset"] == 8
               and row["duration"] == 18]
    if len(nominal) != len(METHODS) or any(row["first_alarm"] != 12 for row in nominal):
        raise RuntimeError("Policies do not agree in the nominal aligned control")
    if any(row["first_alarm"] is not None for row in rows if row["duration"] == 0):
        raise RuntimeError("A no-fault control raised an alarm")
    case = Case(6, 18, "clustered_capture")
    if lab_alarms(native, case, case.messages()) != {"count": 8, "hold": 10, "observed": 12}:
        raise RuntimeError("The clustered-acquisition boundary control failed")
    case = Case(8, 18, "nominal")
    single = {8: 8}
    if (lc_alarm(probe, case, single, 2, 1) is not None or lc_alarm(probe, case, single, 2, 3) != 12
            or lc_alarm(probe, case, single, 1, 6) != 12):
        raise RuntimeError("The LC retained-result and aging boundary control failed")
    if lab_alarms(native, case, single) != {"count": None, "hold": 12, "observed": None}:
        raise RuntimeError("The lab retained-result boundary control failed")


def summarize(rows):
    counts = {outcome: sum(row["outcome"] == outcome for row in rows) for outcome in OUTCOMES}
    delay = max((row["extra_delay"] for row in rows if row["outcome"] == "timely"), default=None)
    return dict(counts, max_timely_extra_delay=delay)


def groups(rows):
    yield "all", rows
    yield "aligned", [row for row in rows if row["delivery"] in ALIGNED]
    yield "off_grid", [row for row in rows if row["delivery"] in OFF_GRID]
    for delivery in DELIVERIES:
        yield delivery, [row for row in rows if row["delivery"] == delivery]


def paired_matches(rows):
    cases = {}
    for row in rows:
        key = row["onset"], row["duration"], row["delivery"]
        cases.setdefault(key, {})[row["method"]] = row["first_alarm"]
    pairs = (("count", "lc_age_1"), ("observed", "lc_age_1"), ("hold", "lc_age_3"),
             ("hold", "lc_fast_age_6"), ("count", "observed"))
    return {f"{left}_vs_{right}": dict(cases=len(cases),
                                       exact=sum(alarms[left] == alarms[right] for alarms in cases.values()))
            for left, right in pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare deterministic results with the archive")
    args = parser.parse_args()
    run, library, build_record = build()
    probe, sources = build_lc(run, compiler())
    native = Native(library)
    rows = run_cases(native, probe)
    check_controls(native, probe, rows)
    csv_path = run / "cases.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    record = dict(revision=REVISION, upstream_sources=sources, compiler=build_record["compiler"],
                  signals=len(rows) // len(METHODS), policy_runs=len(rows), physical_tests=False,
                  config=CONFIG, nominal_sample_period=PERIOD, synthetic_inputs=True,
                  lc_settings={name: dict(period=period, age=age, evaluations=DWELL // period + 1)
                               for name, (period, age) in LC_SETTINGS.items()},
                  nominal_control_first_alarm=12,
                  stats={group: {method: summarize([row for row in sample if row["method"] == method])
                                 for method in METHODS} for group, sample in groups(rows)},
                  paired_first_alarm_matches={group: paired_matches(sample) for group, sample in groups(rows)
                                              if group in ("aligned", "off_grid")},
                  cases_csv_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest())
    (run / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.check:
        expected = json.loads((ARCHIVE / "summary.json").read_text(encoding="utf-8"))
        for key in record.keys() - {"compiler"}:
            if record[key] != expected[key]:
                raise RuntimeError(f"{key} differs from the archived run: {run}")
    print(json.dumps(dict(run=str(run), signals=record["signals"], policy_runs=len(rows),
                          stats=record["stats"]["all"]), indent=2))


if __name__ == "__main__":
    main()
