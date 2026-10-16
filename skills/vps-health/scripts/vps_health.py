#!/usr/bin/env python3
"""Read-only VPS investigation and reproducible local evidence. Python 3.10+."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import html
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
import stat
import time
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

VERSION = '0.10.0'
SCHEMA = 'g-skills.vps-capture.v1'
ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024 * 1024
MAX_POINTS = 4033
POLICY = {'acceptable_ratio': 0.90, 'minimum_hours': 24, 'minimum_coverage': 0.75,
          'cpu_pressure_attention': 0.10, 'throttled_periods_attention': 0.05,
          'provider_contact': 'human-decision-only', 'automatic_changes': False}
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class InvalidEvidence(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pairs_unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise InvalidEvidence(f'duplicate JSON key: {key}')
        out[key] = value
    return out


def finite(value, *, minimum=None, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise InvalidEvidence('expected a finite JSON number, not a string or boolean')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise InvalidEvidence('numeric value outside allowed bounds')
    return value


def read_bytes(path):
    # JSON/config input must never wait on a FIFO or read an arbitrary device.
    # procfs counters are regular files even when their reported size is zero.
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    try:fd=os.open(path,flags)
    except OSError as exc:raise InvalidEvidence('input must be a readable regular file, not a symbolic link') from exc
    data=bytearray()
    with os.fdopen(fd,'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise InvalidEvidence('input must be a bounded regular file')
        while chunk:=handle.read(min(4096,MAX_BYTES+1-len(data))):
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise InvalidEvidence('input exceeds 8 MiB limit')
    return bytes(data)


def decode(data):
    try:
        return json.loads(data, object_pairs_hook=pairs_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(InvalidEvidence('nonfinite JSON value')))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise InvalidEvidence('invalid or ambiguous JSON') from exc


def read_json(path):
    return decode(read_bytes(path))


def stamp(value):
    if not isinstance(value, str):
        raise InvalidEvidence('timestamp must be fixed ISO 8601 with a timezone')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise InvalidEvidence('invalid timestamp') from exc
    if parsed.utcoffset() is None:
        raise InvalidEvidence('timestamp timezone is required')
    return parsed.timestamp()


def iso(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def alias(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise InvalidEvidence('node alias must be 1-80 letters, digits, dot, underscore or hyphen')
    return value


def save_json(path, value):
    raw=json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as handle:
        handle.write(raw);handle.flush();os.fsync(handle.fileno())


def new_capture(node, kind, start, end, interval):
    return {'schema': SCHEMA, 'version': VERSION, 'subject': {'id': alias(node), 'identity_verified': False},
            'source': {'kind': kind, 'tool_sha256': SOURCE_SHA256}, 'start': iso(start), 'end': iso(end),
            'interval_seconds': interval, 'samples': [], 'errors': [], 'notes': [], 'raw': {},
            'provider_cause_proven': False}


def cpu_snapshot():
    start = time.monotonic_ns()
    wall_start = time.time_ns()
    text = read_bytes('/proc/stat').decode('ascii')
    cpus = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields or not re.fullmatch(r'cpu\d+', fields[0]):
            continue
        if fields[0] in cpus or len(fields) < 9:
            raise InvalidEvidence('duplicate CPU or missing modes in /proc/stat')
        values = [int(v) for v in fields[1:9]]
        for value in values:
            finite(value, minimum=0)
        cpus[fields[0]] = values
    if not 1 <= len(cpus) <= 1024:
        raise InvalidEvidence('unsupported CPU count or missing /proc/stat')
    pressure = {}
    for resource in ('cpu', 'io', 'memory'):
        try:
            text = read_bytes('/proc/pressure/' + resource).decode('ascii')
            pressure[resource] = int(next(line for line in text.splitlines() if line.startswith('some ')).split('total=')[1])
        except (OSError, StopIteration, ValueError):
            pressure[resource] = None
    try:
        boot = hashlib.sha256(read_bytes('/proc/sys/kernel/random/boot_id')).hexdigest()
    except OSError:
        boot = None
    return {'start_ns': start, 'end_ns': time.monotonic_ns(), 'wall_start_ns': wall_start,
            'wall_end_ns': time.time_ns(), 'boot_fingerprint': boot, 'cpus': cpus, 'pressure': pressure}


def local_interval(first, last, hz, requested):
    lo = (last['start_ns'] - first['end_ns']) / 1e9
    hi = (last['end_ns'] - first['start_ns']) / 1e9
    elapsed = (lo + hi) / 2
    if lo <= 0:
        raise InvalidEvidence('overlapping or reversed monotonic intervals')
    reasons = []
    wall = ((last['wall_start_ns'] + last['wall_end_ns']) -
            (first['wall_start_ns'] + first['wall_end_ns'])) / 2e9
    if abs(wall - elapsed) > max(.02, elapsed * .01):
        reasons.append('clock_discontinuity')
    if elapsed > requested * 2.5:
        reasons.append('sampling_gap')
    if (hi - lo) / elapsed > .05:
        reasons.append('measurement_overhead')
    if not first['boot_fingerprint'] or first['boot_fingerprint'] != last['boot_fingerprint']:
        reasons.append('unknown_or_changed_boot')
    if first['cpus'].keys() != last['cpus'].keys():
        reasons.append('cpu_set_changed')
    row = {'timestamp': last['wall_end_ns'] / 1e9, 'duration_seconds': elapsed, 'quality': reasons,
           'cpu_accounted_ratio': None, 'executing_ratio': None, 'steal_ratio': None,
           'iowait_ratio': None, 'cpu_pressure_ratio': None, 'io_pressure_ratio': None,
           'memory_pressure_ratio': None, 'cfs_throttled_periods_ratio': None}
    if any(x in reasons for x in ('unknown_or_changed_boot', 'cpu_set_changed')):
        return row
    deltas = [[b - a for a, b in zip(first['cpus'][cpu], last['cpus'][cpu])] for cpu in first['cpus']]
    if any(x < 0 for values in deltas for x in values):
        reasons.append('counter_decreased')
        return row
    capacity = len(deltas) * elapsed
    modes = [sum(values[i] for values in deltas) / hz / capacity for i in range(8)]
    row.update(cpu_accounted_ratio=sum(modes[:7]), executing_ratio=sum(modes[i] for i in (0,1,2,5,6)),
               steal_ratio=modes[7], iowait_ratio=modes[4])
    rounding = 8 / hz / elapsed
    row['accounting_uncertainty'] = rounding + (hi - lo) / elapsed
    if sum(modes) > 1 + max(.01, rounding):
        reasons.append('accounting_exceeds_capacity')
    for resource in ('cpu', 'io', 'memory'):
        a, b = first['pressure'][resource], last['pressure'][resource]
        if a is not None and b is not None and b >= a:
            ratio = (b - a) / 1e6 / elapsed
            if 0 <= ratio <= 1.01:
                row[resource + '_pressure_ratio'] = ratio
            else:
                reasons.append(resource + '_pressure_invalid')
    if first.get('guest_context') and last.get('guest_context'):
        import vps_forensics as forensic
        try:row['guest_context']=forensic.interval(first['guest_context'],last['guest_context'])
        except (ValueError,TypeError,KeyError):row['guest_context']={'schema':forensic.INTERVAL,'quality':['invalid_context'],'storage':[],'pressure':{},'network':{},'memory':{},'provider_cause_proven':False}
    return row


def enriched_snapshot():
    # Keep CPU sample timing independent of optional diagnostic reads. The context
    # has its own acquisition bracket and is never used as physical-host proof.
    current=cpu_snapshot()
    import vps_forensics as forensic
    current['guest_context']=forensic.snapshot('local-context')
    return current


def collect_local(node, interval=2, samples=6):
    finite(interval, minimum=.2, maximum=5)
    if type(samples) is not int or not 2 <= samples <= 31 or interval * (samples-1) > 60:
        raise InvalidEvidence('2-31 snapshots and at most 60 seconds planned waiting')
    if sys.platform != 'linux':
        raise InvalidEvidence('collect-local needs Linux; report and demo are portable')
    started = time.time()
    capture = new_capture(node, 'passive-linux', started, started, interval)
    capture['source']['kernel'] = os.uname().release
    hz = os.sysconf('SC_CLK_TCK')
    capture['source']['user_hz'] = hz
    capture['source']['observer_affinity'] = sorted(os.sched_getaffinity(0))
    snapshots = []
    try:
        for i in range(samples):
            if i:
                time.sleep(interval)
            snapshots.append(enriched_snapshot())
            if i:
                capture['samples'].append(local_interval(snapshots[-2], snapshots[-1], hz, interval))
    except (OSError, ValueError, KeyboardInterrupt):
        capture['errors'].append('local collection stopped; partial evidence retained')
    capture['raw']['snapshots'] = snapshots
    capture['end'] = iso(time.time())
    capture['notes'] = ['Passive counter reads and sleeping only; no deliberate load.',
        'The observer cgroup and /proc visibility may differ from the full VM.',
        'No workload-specific CFS data was collected; absence is not zero.',
        'A short passive observation cannot establish a sustained or provider verdict.']
    return capture


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InvalidEvidence('redirect refused; configure the final trusted endpoint')


def endpoint(value, allow_http=False):
    p = urllib.parse.urlsplit(value)
    if p.username or p.password or p.query or p.fragment or not p.hostname:
        raise InvalidEvidence('endpoint must not contain credentials, query or fragment')
    if p.scheme not in ('http', 'https'):
        raise InvalidEvidence('only HTTP(S) metrics endpoints are supported')
    local = p.hostname in ('localhost', '127.0.0.1', '::1')
    if p.scheme == 'http' and not local and not allow_http:
        raise InvalidEvidence('remote plaintext HTTP requires explicit --allow-http; prefer HTTPS/tunnel')
    return value.rstrip('/')


def get_json(base, path, params, token=None, timeout=15):
    request = urllib.request.Request(base + path + '?' + urllib.parse.urlencode(params),
                                     headers={'Accept': 'application/json', 'User-Agent': 'G-Skills-vps-health/'+VERSION})
    if token:
        if urllib.parse.urlsplit(base).scheme != 'https':
            raise InvalidEvidence('bearer credentials require HTTPS')
        request.add_header('Authorization', 'Bearer '+token)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise InvalidEvidence('API response exceeds 8 MiB')
        result = decode(raw)
        if not isinstance(result, dict) or result.get('status') != 'success' or result.get('warnings'):
            raise InvalidEvidence('API failed or returned warnings/partial results')
        return result
    except (OSError, urllib.error.URLError) as exc:
        # Exception URLs/headers can contain secrets; preserve a category only.
        raise InvalidEvidence('endpoint request failed: '+type(exc).__name__) from exc


def plan_metadata(item):
    from vps_ops import PROVIDERS
    if item.get('provider','unknown') not in PROVIDERS:
        raise InvalidEvidence('unsupported provider label; use other')
    plan=item.get('plan')
    if plan is not None and (not isinstance(plan,str) or not 1<=len(plan)<=120 or any(ord(c)<32 for c in plan)):
        raise InvalidEvidence('plan must be a short printable owner-provided label')


def profile_load(path):
    profile = read_json(path)
    if not isinstance(profile, dict) or profile.get('schema') != 'g-skills.vps-profile.v1':
        raise InvalidEvidence('unsupported profile schema')
    assets = profile.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 100:
        raise InvalidEvidence('profile needs 1-100 expected assets')
    ids = []
    for item in assets:
        if not isinstance(item, dict):
            raise InvalidEvidence('asset must be an object')
        ids.append(alias(item.get('id')))
        if not isinstance(item.get('instance'), str) or len(item['instance']) > 255:
            raise InvalidEvidence('asset instance must match its known exporter label')
        plan_metadata(item)
    if len(ids) != len(set(ids)) or len({a['instance'] for a in assets}) != len(assets):
        raise InvalidEvidence('ambiguous expected asset identities')
    return profile


def metrics_queries(instance):
    labels = 'instance='+json.dumps(instance)
    cpu = 'node_cpu_seconds_total{'+labels+'}'
    idle = 'node_cpu_seconds_total{'+labels+',mode="idle"}'
    capacity = f'count({idle})'
    screen = f'sum(rate(node_cpu_seconds_total{{{labels},mode=~"user|nice|system|idle|iowait|irq|softirq"}}[5m])) / {capacity}'
    usable = f'(min(count_over_time({cpu}[5m])) >= 3) and (max(resets({cpu}[5m])) == 0) and (max(up{{{labels}}}) == 1)'
    # Scalar aggregation intentionally targets exactly one configured instance.
    # Duplicate exporter series are invalidated by a separate input-count guard.
    full = f'(min(count by (cpu) ({cpu})) == 8) and (max(count by (cpu) ({cpu})) == 8)'
    return {
        'cpu_accounted_ratio': f'({screen}) and ({usable}) and ({full})',
        'executing_ratio': f'sum(rate(node_cpu_seconds_total{{{labels},mode=~"user|nice|system|irq|softirq"}}[5m])) / {capacity}',
        'steal_ratio': f'sum(rate(node_cpu_seconds_total{{{labels},mode="steal"}}[5m])) / {capacity}',
        'iowait_ratio': f'sum(rate(node_cpu_seconds_total{{{labels},mode="iowait"}}[5m])) / {capacity}',
        'cpu_pressure_ratio': f'rate(node_pressure_cpu_waiting_seconds_total{{{labels}}}[5m])',
        'io_pressure_ratio': f'rate(node_pressure_io_waiting_seconds_total{{{labels}}}[5m])',
        'memory_pressure_ratio': f'rate(node_pressure_memory_waiting_seconds_total{{{labels}}}[5m])'}


def collect_prometheus(profile, base, start, end, step=300, token=None, loki=None, loki_token=None):
    seconds = end-start
    if not 3600 <= seconds <= 14*86400 or type(step) is not int or not 60 <= step <= 3600 or seconds/step+1 > MAX_POINTS:
        raise InvalidEvidence('range 1h-14d; step 60-3600s; at most 4033 samples')
    if end > time.time()+5:
        raise InvalidEvidence('future evidence range refused')
    captures = []
    deadline = time.monotonic() + 120
    for asset in profile['assets']:
        capture = new_capture(asset['id'], 'prometheus', start, end, step)
        capture['subject'].update(provider=asset.get('provider','unknown'),plan=asset.get('plan','unknown'))
        capture['notes'] = ['Stock node-exporter accounting screen, not calibrated physical CPU delivery.',
            'Matched graph points are not a contractual CPU floor.',
            'Workload-specific limits and service impact need separate evidence.']
        points = {}
        for name, query in metrics_queries(asset['instance']).items():
            capture['raw'][name] = {'query': query}
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise InvalidEvidence('collection time budget exhausted')
                body = get_json(base, '/api/v1/query_range', {'query':query,'start':start,'end':end,'step':step}, token, timeout=min(15,remaining))
                capture['raw'][name]['response'] = body
                rows = body['data']['result']
                if not isinstance(rows,list) or len(rows)>1:
                    raise InvalidEvidence('ambiguous metric series; refusing to choose one')
                if not rows:
                    continue
                if body['data'].get('resultType') != 'matrix':
                    raise InvalidEvidence('expected range-matrix response')
                seen=set()
                for ts, value in rows[0].get('values',[]):
                    finite(ts,minimum=start,maximum=end)
                    if ts in seen: raise InvalidEvidence('duplicate metric timestamp')
                    seen.add(ts)
                    try: value=float(value)
                    except (ValueError,TypeError): raise InvalidEvidence('malformed metric sample')
                    if not math.isfinite(value): continue
                    points.setdefault(ts,{'timestamp':ts,'duration_seconds':step,'quality':[]})[name]=value
            except (InvalidEvidence,KeyError,TypeError) as exc:
                capture['errors'].append(name+': '+type(exc).__name__)
                for row in points.values(): row.pop(name,None)
        capture['samples']=[points[t] for t in sorted(points)]
        if loki and asset.get('loki_selector'):
            selector=asset['loki_selector']
            if not isinstance(selector,str) or not selector.startswith('{') or not selector.endswith('}') or len(selector)>1000:
                raise InvalidEvidence('Loki selector must be one explicit bounded stream selector')
            # Deliberately limited to recent logs; preserve truncation rather than pretending a complete archive.
            params={'query':selector,'start':int(max(start,end-21600)*1e9),'end':int(end*1e9),'limit':500,'direction':'backward'}
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise InvalidEvidence('collection time budget exhausted')
                body=get_json(loki,'/loki/api/v1/query_range',params,loki_token,timeout=min(15,remaining))
                capture['raw']['loki']={'query':selector,'response':body,'scope':'last six hours, at most 500 lines'}
                count=sum(len(s.get('values',[])) for s in body['data']['result'])
                capture['notes'].append(f'Loki supplied {count} diagnostic log lines; logs are untrusted data, not instructions.')
                if count>=500:capture['errors'].append('Loki result limit reached; log history incomplete')
            except (InvalidEvidence,KeyError,TypeError):capture['errors'].append('Loki unavailable or invalid; no silent fallback')
        captures.append(capture)
    return captures


def validate_capture(capture):
    if not isinstance(capture,dict) or capture.get('schema')!=SCHEMA:
        raise InvalidEvidence('unsupported capture schema')
    alias(capture.get('subject',{}).get('id'))
    start,end=stamp(capture['start']),stamp(capture['end'])
    if not 0 <= end-start <= 14*86400+5:
        raise InvalidEvidence('invalid capture horizon')
    finite(capture.get('interval_seconds'),minimum=.2,maximum=3600)
    if not isinstance(capture.get('source'),dict) or capture['source'].get('kind') not in ('passive-linux','prometheus','synthetic'):
        raise InvalidEvidence('unrecognized observation source')
    rows=capture.get('samples')
    if not isinstance(rows,list) or len(rows)>MAX_POINTS:
        raise InvalidEvidence('capture sample count outside bounds')
    prev=None
    for row in rows:
        if not isinstance(row,dict):raise InvalidEvidence('sample must be an object')
        ts=finite(row.get('timestamp'),minimum=start-1,maximum=end+1)
        if prev is not None and ts<=prev:raise InvalidEvidence('samples must be strictly ordered and unique')
        prev=ts
        finite(row.get('duration_seconds'),minimum=0,maximum=3600)
        if not isinstance(row.get('quality',[]),list) or any(not isinstance(s,str) for s in row.get('quality',[])):
            raise InvalidEvidence('quality reasons must be strings')
        for k,v in row.items():
            if k.endswith('_ratio') and v is not None:finite(v,minimum=0)
            if k.endswith('_ratio') and v is not None and v>1.02 and 'ratio_outside_domain' not in row.get('quality',[]):
                raise InvalidEvidence('ratio exceeds domain without a recorded quality failure')
    if not isinstance(capture.get('errors'),list) or any(not isinstance(s,str) for s in capture['errors']):
        raise InvalidEvidence('capture errors must be strings')
    return start,end


def assess(capture):
    start,end=validate_capture(capture);rows=capture['samples'];interval=capture['interval_seconds']
    usable=[r for r in rows if not r.get('quality') and r.get('cpu_accounted_ratio') is not None and 0<=r['cpu_accounted_ratio']<=1.02]
    weights={}
    previous=start
    for row in rows:
        weights[row['timestamp']]=min(row['duration_seconds'],interval,max(0,row['timestamp']-previous))
        previous=row['timestamp']
    represented=sum(weights[r['timestamp']] for r in usable)
    coverage=min(1,represented/max(interval,end-start))
    weighted=lambda field: (sum(r[field]*weights[r['timestamp']] for r in usable if r.get(field) is not None)/sum(weights[r['timestamp']] for r in usable if r.get(field) is not None)) if any(r.get(field) is not None and weights[r['timestamp']]>0 for r in usable) else None
    mean=weighted('cpu_accounted_ratio');pressure=weighted('cpu_pressure_ratio');cfs=weighted('cfs_throttled_periods_ratio')
    holds=list(capture['errors'])
    holds.extend(reason for row in rows for reason in row.get('quality',[]))
    if end-start<86400:holds.append('less_than_24_hours')
    if coverage<.75:holds.append('insufficient_coverage')
    if capture['source']['kind']=='passive-linux':holds.append('short_passive_observation_only')
    if cfs is None:holds.append('workload_cfs_context_missing')
    if pressure is None:holds.append('cpu_pressure_context_missing')
    holds+=['identity_and_plan_require_owner_verification','controlled_repeats_and_service_impact_not_verified']
    if not usable or mean is None:state='NOT_MEASURED'
    elif mean is not None and mean>=.90:state='WITHIN_WORKING_TOLERANCE'
    elif pressure is not None and pressure>.10 or cfs is not None and cfs>.05:state='LOW_ACCOUNTING_WITH_CONTENTION'
    else:state='LOW_ACCOUNTING_NEEDS_CONTEXT'
    return {'subject':capture['subject']['id'],'state':state,'accounted_mean':mean,'execution_mean':weighted('executing_ratio'),
            'steal_mean':weighted('steal_ratio'),'pressure_mean':pressure,'coverage':coverage,'hours':(end-start)/3600,
            'samples':len(rows),'usable_samples':len(usable),'holds':sorted(set(holds)),
            'provider_cause_proven':False,'contact_provider':False,'service_health_verified':False,
            'next_action':'Review gaps, matching workload limits and service impact. Do not contact or migrate automatically.'}


def report(captures,out):
    if not isinstance(captures,list) or not 1<=len(captures)<=100:raise InvalidEvidence('need 1-100 captures')
    ids=[c.get('subject',{}).get('id') for c in captures]
    if len(ids)!=len(set(ids)):raise InvalidEvidence('duplicate subject captures; use compare for multiple periods')
    rows=[assess(c) for c in captures]
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    payload={'schema':'g-skills.vps-report.v1','version':VERSION,'tool_sha256':SOURCE_SHA256,'capture_sha256':digest(captures),
             'policy':POLICY,'assets':rows,'expected_assets':len(captures),'scope':'supplied subjects only; account completeness is not inferred',
             'provider_cause_proven':False,'contact_provider':False}
    save_json(out/'capture.json',captures);save_json(out/'report.json',payload)
    md=['# VPS health observations','','Internal investigation, not proof of provider responsibility.','',
        '| Subject | State | Accounted mean | Coverage |','|---|---|---:|---:|']
    html_rows=[]
    for r in rows:
        pct=lambda v: 'unknown' if v is None else f'{v*100:.1f}%'
        md.append(f"| {r['subject']} | {r['state']} | {pct(r['accounted_mean'])} | {pct(r['coverage'])} |")
        reasons='; '.join(r['holds']);md.extend(['',f"## {r['subject']}",reasons,r['next_action']])
        html_rows.append('<tr><td>'+html.escape(r['subject'])+'</td><td>'+html.escape(r['state'])+'</td><td>'+pct(r['accounted_mean'])+'</td><td>'+pct(r['coverage'])+'</td><td>'+html.escape(reasons)+'</td></tr>')
    with (out/'report.md').open('x') as h:h.write('\n'.join(md)+'\n')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>VPS observations</title><style>body{font:16px system-ui;margin:2em;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{padding:.7em;text-align:left;border-bottom:1px solid #bbb;vertical-align:top}h1{margin-bottom:0}small{display:block;margin:1em 0}</style><h1>VPS observations</h1><p>90% is a working tolerance, not a provider promise. Missing evidence is not healthy.</p><small>Only supplied subjects are covered. No report authorizes provider contact, migration or a host change.</small><table><thead><tr><th>Subject</th><th>State</th><th>Accounted mean</th><th>Coverage</th><th>Limits</th></tr></thead><tbody>'+''.join(html_rows)+'</tbody></table></html>'
    with (out/'report.html').open('x') as h:h.write(page)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    save_json(out/'manifest.json',{'schema':'g-skills.manifest.v1','files':manifest})
    return payload


def verify_bundle(path):
    path=Path(path);m=read_json(path/'manifest.json')
    if m.get('schema')!='g-skills.manifest.v1' or not isinstance(m.get('files'),dict):raise InvalidEvidence('invalid manifest')
    expected={'capture.json','report.json','report.md','report.html'}
    if set(m['files'])!=expected:raise InvalidEvidence('manifest must cover exactly the four evidence files')
    for name,h in m['files'].items():
        p=path/name
        if p.is_symlink() or not p.is_file() or hashlib.sha256(read_bytes(p)).hexdigest()!=h:
            raise InvalidEvidence('bundle integrity failed: '+name)
    captures=read_json(path/'capture.json');saved=read_json(path/'report.json')
    if saved.get('capture_sha256')!=digest(captures):raise InvalidEvidence('report/capture mismatch')
    if saved.get('policy')!=POLICY or saved.get('contact_provider') is not False or saved.get('provider_cause_proven') is not False:
        raise InvalidEvidence('report changed authority or policy')
    if saved.get('assets')!=[assess(c) for c in captures]:raise InvalidEvidence('report does not reproduce under current analyzer')
    return {'integrity':'PASS','replay':'PASS','attestation':'not independent; hashes detect changes, not a trusted signer'}


def lesson_proposal(bundle_path,out):
    verify_bundle(bundle_path)
    r=read_json(Path(bundle_path)/'report.json')
    # Whitelist aggregates, not host names, raw logs, IPs, endpoints or prose.
    data={'schema':'g-skills.lesson-proposal.v1','state':'PROPOSED_NOT_APPLIED','source_capture_hash':r['capture_sha256'],
          'analyzer_hash':SOURCE_SHA256,'state_counts':dict(collections.Counter(x['state'] for x in r['assets'])),
          'known_gap_counts':dict(collections.Counter(h for x in r['assets'] for h in x['holds'] if h in {
              'less_than_24_hours','insufficient_coverage','short_passive_observation_only','workload_cfs_context_missing',
              'cpu_pressure_context_missing','controlled_repeats_and_service_impact_not_verified'})),
          'required_review':['reproduce with synthetic non-identifying fixture','add failing regression','fix owning implementation',
                             'run all safety tests','review privacy and policy diff','maintainer approves versioned change'],
          'can_change_policy':False,'can_contact_provider':False,'can_publish':False}
    save_json(out,data);return data


def compare(before,after):
    left,right=read_json(Path(before)/'report.json'),read_json(Path(after)/'report.json')
    verify_bundle(before);verify_bundle(after)
    if left.get('policy')!=right.get('policy') or left.get('tool_sha256')!=right.get('tool_sha256'):
        raise InvalidEvidence('incomparable policy/analyzer; replay both captures with the same version first')
    a={r['subject']:r for r in left['assets']};b={r['subject']:r for r in right['assets']}
    if set(a)!=set(b):raise InvalidEvidence('subject sets differ; reconcile inventory before comparing')
    return {'schema':'g-skills.comparison.v1','causal_claim':False,'changes':[{'subject':k,'before':a[k]['state'],'after':b[k]['state'],
            'accounted_delta':None if a[k]['accounted_mean'] is None or b[k]['accounted_mean'] is None else b[k]['accounted_mean']-a[k]['accounted_mean']} for k in sorted(a)],
            'limits':'Different windows/hardware/load are not a controlled experiment. No speedup or provider attribution.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('demo');a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('collect-local');a.add_argument('--node',required=True);a.add_argument('--interval',type=float,default=2);a.add_argument('--samples',type=int,default=6);a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('collect-prometheus');a.add_argument('--profile',required=True,type=Path);a.add_argument('--url',required=True);a.add_argument('--loki-url');a.add_argument('--from',dest='start',required=True);a.add_argument('--to',dest='end',required=True);a.add_argument('--step',type=int,default=300);a.add_argument('--token-env');a.add_argument('--loki-token-env');a.add_argument('--allow-http',action='store_true');a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('report');a.add_argument('captures',nargs='+',type=Path);a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('verify');a.add_argument('bundle',type=Path)
    a=sub.add_parser('learn');a.add_argument('bundle',type=Path);a.add_argument('--out',required=True,type=Path)
    a=sub.add_parser('compare');a.add_argument('before',type=Path);a.add_argument('after',type=Path)
    import vps_workspace as workspace
    workspace.register(sub)
    args=p.parse_args(argv)
    try:
        if args.cmd in workspace.COMMANDS:
            result=workspace.dispatch(args)
            print(json.dumps(result,indent=2,allow_nan=False))
            if args.cmd=='doctor':return 0 if result.get('verdict')=='READY' else 1
            if args.cmd=='agent-plan':return 0 if result.get('ready') else 1
            if args.cmd=='agent-start':return 0 if result.get('state')=='RUNNING' and result.get('process_verified') else 1
            if args.cmd=='agent-verify':return 0 if result.get('state')=='VERIFIED' else 1
            if args.cmd=='agent-stop':return 1 if result.get('process_verified') else 0
            return 0
        if args.cmd=='demo':result=report(read_json(ROOT/'assets/demo-capture.json'),args.out)
        elif args.cmd=='collect-local':
            if args.out.exists():raise InvalidEvidence('output exists; no observation will be started')
            c=collect_local(args.node,args.interval,args.samples);save_json(args.out,c);result=assess(c)
        elif args.cmd=='collect-prometheus':
            if args.out.exists():raise InvalidEvidence('output exists; no network request will be started')
            base=endpoint(args.url,args.allow_http);loki=endpoint(args.loki_url,args.allow_http) if args.loki_url else None
            token=os.environ.get(args.token_env) if args.token_env else None
            if args.token_env and not token:raise InvalidEvidence('named token environment variable is not set')
            loki_token=os.environ.get(args.loki_token_env) if args.loki_token_env else None
            if args.loki_token_env and not loki_token:raise InvalidEvidence('named Loki token environment variable is not set')
            captures=collect_prometheus(profile_load(args.profile),base,stamp(args.start),stamp(args.end),args.step,token,loki,loki_token)
            save_json(args.out,captures);result={'collected':len(captures),'source_errors':sum(len(c['errors']) for c in captures)}
        elif args.cmd=='report':
            captures=[]
            for path in args.captures:
                d=read_json(path);captures.extend(d if isinstance(d,list) else [d])
            result=report(captures,args.out)
        elif args.cmd=='verify':
            manifest=read_json(args.bundle/'manifest.json')
            result=(workspace.verify_export(args.bundle) if isinstance(manifest,dict)
                    and manifest.get('schema')=='g-skills.workspace-export.v1' else verify_bundle(args.bundle))
        elif args.cmd=='learn':result=workspace.learning_proposal(args.bundle,args.out) if (args.bundle/'workspace.json').exists() else lesson_proposal(args.bundle,args.out)
        else:result=compare(args.before,args.after)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0
    except (InvalidEvidence,OSError,KeyError,TypeError,UnicodeError,sqlite3.Error) as exc:
        print('ERROR: '+type(exc).__name__+': '+str(exc)[:240],file=sys.stderr);return 2


if __name__=='__main__':
    raise SystemExit(main())
