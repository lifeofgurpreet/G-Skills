#!/usr/bin/env python3
"""Bounded guest-visible context, not hypervisor access or provider fault proof.

No shell commands, network traffic, benchmark allocations or storage writes are
performed by snapshot(). All observations are private, optional and source-scoped.
"""
from __future__ import annotations
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import vps_health as core

SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
SCHEMA='g-skills.guest-context.v1'
INTERVAL='g-skills.guest-context-interval.v1'
MAX_SOURCE=1024*1024
MAX_DEVICES=128
COUNTERS=('/proc/diskstats','/proc/net/softnet_stat','/proc/net/dev','/proc/vmstat','/proc/meminfo',
          '/proc/pressure/cpu','/proc/pressure/io','/proc/pressure/memory')


def read_source(path):
    try:
        with open(path,'rb') as f:data=f.read(MAX_SOURCE+1)
        if len(data)>MAX_SOURCE:return {'state':'oversized','text':None}
        return {'state':'observed','text':data.decode('utf-8')}
    except PermissionError:return {'state':'permission_denied','text':None}
    except FileNotFoundError:return {'state':'unavailable','text':None}
    except (OSError,UnicodeError):return {'state':'unreadable','text':None}


def cpu_identity(text):
    """Guest-configured model/features, never the physical-host identity."""
    if text is None:return None
    records=[part for part in text.split('\n\n') if part.strip()];models=set();fields={}
    allowed=('model name','vendor_id','cpu family','model','stepping','microcode','cache size','Hardware','CPU implementer','CPU part')
    flags=set()
    for record in records[:1024]:
        values={line.split(':',1)[0].strip():line.split(':',1)[1].strip() for line in record.splitlines() if ':' in line}
        models.add(values.get('model name',values.get('Hardware','unknown')))
        if not fields:fields={k:values[k][:256] for k in allowed if k in values}
        flags.update(v for v in values.get('flags',values.get('Features','')).split() if v in ('aes','avx','avx2','avx512f','sha_ni','vaes','asimd','sha2','hypervisor'))
    return {'guest_fields':fields,'models':sorted(models)[:16],'visible_records':len(records),'feature_subset':sorted(flags),
            'physical_cpu_verified':False,'performance_baseline':None}


def root_mount(text):
    if text is None:return {'state':'unavailable','device_id':None,'filesystem':None}
    matches=[]
    for line in text.splitlines():
        front,sep,back=line.partition(' - ');parts=front.split();suffix=back.split()
        if sep and len(parts)>=6 and len(suffix)>=2 and parts[4]=='/':
            if not re.fullmatch(r'\d+:\d+',parts[2]):continue
            matches.append({'state':'observed','device_id':parts[2],'filesystem':suffix[0]})
    return matches[0] if len(matches)==1 else {'state':'ambiguous_or_missing','device_id':None,'filesystem':None}


def parse_diskstats(text):
    if text is None:return None
    result={}
    for line in text.splitlines():
        parts=line.split()
        if len(parts)<14:raise ValueError('incomplete diskstats row')
        values=[int(v) for v in parts[3:]]
        if any(v<0 for v in values):raise ValueError('negative disk counter')
        key=f'{int(parts[0])}:{int(parts[1])}'
        if key in result:raise ValueError('duplicate disk identity')
        result[key]={'name':parts[2],'read_ios':values[0],'read_sectors':values[2],'read_ms':values[3],
                     'write_ios':values[4],'write_sectors':values[6],'write_ms':values[7],
                     'in_flight':values[8],'busy_ms':values[9],'weighted_ms':values[10]}
        if len(result)>MAX_DEVICES:raise ValueError('device budget exceeded')
    return result


def parse_softnet(text):
    if text is None:return None
    result={}
    for index,line in enumerate(text.splitlines()):
        fields=line.split()
        if len(fields)<3:raise ValueError('incomplete softnet row')
        if any(not re.fullmatch(r'[0-9a-fA-F]+',f) for f in fields):raise ValueError('invalid hexadecimal softnet counter')
        values=[int(v,16) for v in fields]
        cpu=str(values[12]) if len(values)>=13 else str(index)
        if cpu in result:raise ValueError('duplicate softnet CPU')
        result[cpu]={'processed':values[0],'dropped':values[1],'time_squeeze':values[2]}
        if len(result)>1024:raise ValueError('CPU budget exceeded')
    return result


def parse_netdev(text):
    if text is None:return None
    rows={}
    for line in text.splitlines():
        if ':' not in line:continue
        name,body=line.split(':',1);name=name.strip();parts=body.split()
        if len(parts)!=16 or name in rows:raise ValueError('invalid interface row')
        values=[int(v) for v in parts]
        if any(v<0 for v in values):raise ValueError('negative interface counter')
        rows[name]={'rx_bytes':values[0],'rx_packets':values[1],'rx_errors':values[2],'rx_dropped':values[3],
                    'tx_bytes':values[8],'tx_packets':values[9],'tx_errors':values[10],'tx_dropped':values[11]}
        if len(rows)>MAX_DEVICES:raise ValueError('interface budget exceeded')
    return rows


def parse_pairs(text,keys):
    if text is None:return None
    result={}
    for line in text.splitlines():
        parts=line.replace(':',' ').split()
        if len(parts)<2 or parts[0] not in keys:continue
        if parts[0] in result:raise ValueError('duplicate counter')
        value=int(parts[1])
        if value<0:raise ValueError('negative counter')
        result[parts[0]]=value
    return result


def parse_psi(text):
    if text is None:return None
    result={}
    for line in text.splitlines():
        fields=line.split()
        if not fields or fields[0] not in ('some','full'):continue
        if fields[0] in result:raise ValueError('duplicate pressure row')
        values=dict(f.split('=',1) for f in fields[1:]);total=int(values['total'])
        if total<0:raise ValueError('negative pressure time')
        result[fields[0]]=total
    return result


def snapshot(node='local-context',reader=read_source):
    if sys.platform!='linux':raise core.InvalidEvidence('guest-context snapshot requires the authorized Linux target')
    start=time.monotonic_ns();wall=time.time_ns();raw={path:reader(path) for path in COUNTERS}
    cpu=reader('/proc/cpuinfo');boot=reader('/proc/sys/kernel/random/boot_id')
    clock=reader('/sys/devices/system/clocksource/clocksource0/current_clocksource')
    vendor=reader('/sys/class/dmi/id/sys_vendor');product=reader('/sys/class/dmi/id/product_name')
    environment={'cpu':cpu_identity(cpu['text']),'clocksource':clock['text'].strip() if clock['text'] else None,
                 'dmi_vendor':vendor['text'].strip()[:256] if vendor['text'] else None,
                 'dmi_product':product['text'].strip()[:256] if product['text'] else None,
                 'identity_scope':'guest-configured traits; no unique physical-host identifier'}
    mount=root_mount(reader('/proc/self/mountinfo')['text'])
    # Bounded fixed vulnerability names: no arbitrary recursive sysfs traversal.
    mitigations={}
    for name in ('spectre_v1','spectre_v2','meltdown','retbleed','mds','gather_data_sampling','spec_store_bypass'):
        value=reader('/sys/devices/system/cpu/vulnerabilities/'+name)
        mitigations[name]={'state':value['state'],'value':value['text'].strip()[:512] if value['text'] else None}
    return {'schema':SCHEMA,'subject':core.alias(node),'tool_sha256':SOURCE_SHA256,
            'wall_ns':wall,'start_ns':start,'end_ns':time.monotonic_ns(),
            'boot_fingerprint':hashlib.sha256(boot['text'].encode()).hexdigest() if boot['text'] else None,
            'environment':environment,'root_mount':mount,'mitigations':mitigations,'sources':raw,
            'physical_host_verified':False,'network_probes_run':False,'active_benchmarks_run':False}


def validate_snapshot(value):
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA:raise core.InvalidEvidence('unsupported guest-context snapshot')
    core.alias(value.get('subject'))
    for field in ('wall_ns','start_ns','end_ns'):core.finite(value.get(field),minimum=0)
    if value['end_ns']<value['start_ns']:raise core.InvalidEvidence('snapshot timing reversed')
    if not isinstance(value.get('environment'),dict) or not isinstance(value.get('sources'),dict):raise core.InvalidEvidence('missing context fields')
    if len(core.canonical(value))>8*1024*1024:raise core.InvalidEvidence('snapshot budget exceeded')
    for key,source in value['sources'].items():
        if key not in COUNTERS or not isinstance(source,dict) or source.get('state') not in ('observed','oversized','permission_denied','unavailable','unreadable'):
            raise core.InvalidEvidence('unrecognized source boundary')
        if source.get('text') is not None and (not isinstance(source['text'],str) or len(source['text'].encode())>MAX_SOURCE):raise core.InvalidEvidence('invalid raw context')
    return value


def source_value(snap,path,parser):
    source=snap['sources'].get(path,{'state':'unavailable','text':None})
    if source.get('state')!='observed':return None,source.get('state','unavailable')
    try:return parser(source['text']),'observed'
    except (ValueError,TypeError,KeyError,IndexError):return None,'invalid'


def delta_map(first,last):
    if first is None or last is None or first.keys()!=last.keys():return None
    if any(type(last[k]) is not int or type(first[k]) is not int or last[k]<first[k] for k in first):return None
    return {k:last[k]-first[k] for k in first}


def interval(first,last):
    validate_snapshot(first);validate_snapshot(last)
    if first['subject']!=last['subject']:raise core.InvalidEvidence('cannot compare different subjects')
    elapsed=((last['start_ns']+last['end_ns'])-(first['start_ns']+first['end_ns']))/2e9
    wall=(last['wall_ns']-first['wall_ns'])/1e9
    quality=[]
    if not first.get('boot_fingerprint') or first['boot_fingerprint']!=last.get('boot_fingerprint'):quality.append('counter_epoch_unverified')
    if first.get('tool_sha256')!=last.get('tool_sha256'):quality.append('method_changed')
    if not 0<elapsed<=3600:quality.append('interval_outside_bounds')
    if elapsed>0 and abs(wall-elapsed)>max(.1,.02*elapsed):quality.append('clock_discontinuity')
    if elapsed>0 and ((last['end_ns']-last['start_ns'])+(first['end_ns']-first['start_ns']))/1e9>elapsed*.05:quality.append('context_read_overhead')
    result={'schema':INTERVAL,'timestamp':last['wall_ns']/1e9,'seconds':elapsed,'quality':quality,
            'storage':[],'pressure':{},'network':{},'memory':{},'root_mount':last.get('root_mount'),'environment':last.get('environment'),'mitigations':last.get('mitigations',{}),
            'provider_cause_proven':False,'scope':'guest-visible counters; no physical-medium identification or tail latency'}
    if quality:return result
    disks_a,sa=source_value(first,'/proc/diskstats',parse_diskstats);disks_b,sb=source_value(last,'/proc/diskstats',parse_diskstats)
    result['storage_source']=[sa,sb]
    if disks_a is not None and disks_b is not None:
        for key in sorted(disks_a.keys()|disks_b.keys()):
            a=disks_a.get(key);b=disks_b.get(key)
            row={'device_id':key,'name':(b or a)['name'],'state':'device_changed','read_await_ms':None,'write_await_ms':None,'iops':None}
            if a and b and a['name']==b['name']:
                d=delta_map({k:v for k,v in a.items() if k not in ('name','in_flight')},{k:v for k,v in b.items() if k not in ('name','in_flight')})
                if d is not None:
                    row.update(state='observed',iops=(d['read_ios']+d['write_ios'])/elapsed,
                               read_await_ms=d['read_ms']/d['read_ios'] if d['read_ios'] else None,
                               write_await_ms=d['write_ms']/d['write_ios'] if d['write_ios'] else None,
                               read_bytes_per_second=d['read_sectors']*512/elapsed,write_bytes_per_second=d['write_sectors']*512/elapsed,
                               in_flight=b['in_flight'],busy_fraction=d['busy_ms']/1000/elapsed)
                else:row['state']='counter_reset'
            result['storage'].append(row)
    for resource in ('cpu','memory','io'):
        path='/proc/pressure/'+resource;a,sa=source_value(first,path,parse_psi);b,sb=source_value(last,path,parse_psi);d=delta_map(a,b)
        result['pressure'][resource]={'state':'observed' if d is not None else 'unavailable_or_reset','some':None,'full':None}
        if d is not None:
            for kind,micros in d.items():
                ratio=micros/1e6/elapsed
                if 0<=ratio<=1.01:result['pressure'][resource][kind]=ratio
                else:result['pressure'][resource]['state']='counter_invalid'
        if resource=='cpu':result['pressure'][resource]['full']=None  # system-wide full is undefined
    for path,parser,label in (('/proc/net/softnet_stat',parse_softnet,'softnet'),('/proc/net/dev',parse_netdev,'interfaces')):
        a,sa=source_value(first,path,parser);b,sb=source_value(last,path,parser);rows=[]
        if a is not None and b is not None:
            for key in sorted(a.keys()|b.keys()):
                d=delta_map(a.get(key),b.get(key));rows.append({'id':key,'state':'observed' if d is not None else 'changed_or_reset','delta':d})
        result['network'][label]={'sources':[sa,sb],'rows':rows}
    keys=('pgmajfault','pswpin','pswpout','balloon_inflate','balloon_deflate','allocstall_normal','allocstall_movable','allocstall_dma32')
    a,sa=source_value(first,'/proc/vmstat',lambda t:parse_pairs(t,keys));b,sb=source_value(last,'/proc/vmstat',lambda t:parse_pairs(t,keys));d=delta_map(a,b)
    gauges,gs=source_value(last,'/proc/meminfo',lambda t:parse_pairs(t,('MemTotal','MemAvailable','SwapTotal','SwapFree')))
    result['memory']={'counters_state':'observed' if d is not None else 'unavailable_or_reset','counter_deltas':d,'guest_kib':gauges,'gauge_state':gs,
                      'host_swap_verified':False,'note':'Guest faults, balloon activity and swap are not direct measurements of host memory pressure.'}
    return result


def compare(first,last):
    validate_snapshot(first);validate_snapshot(last)
    if first['subject']!=last['subject']:raise core.InvalidEvidence('different subjects cannot be migration comparisons')
    if last['wall_ns']<first['wall_ns']:raise core.InvalidEvidence('comparison chronology is reversed')
    changed=[];unknown=[]
    for field in ('cpu','clocksource','dmi_vendor','dmi_product'):
        a=first['environment'].get(field);b=last['environment'].get(field)
        if a is None or b is None:unknown.append(field)
        elif a!=b:changed.append(field)
    return {'schema':'g-skills.guest-comparison.v1','subject':first['subject'],'before_utc':core.iso(first['wall_ns']/1e9),'after_utc':core.iso(last['wall_ns']/1e9),
            'guest_traits':'CHANGED' if changed else 'INCOMPLETE' if unknown else 'NO_VISIBLE_CHANGE',
            'changed_fields':changed,'unknown_fields':unknown,'boot_changed':first.get('boot_fingerprint')!=last.get('boot_fingerprint'),
            'physical_host_verified':False,'migration_verdict':'NOT_ESTABLISHED_FROM_GUEST_EVIDENCE',
            'interpretation':'Guest CPU/clock/DMI traits may be preserved across migration or changed without one. Identical values do not prove a fake move; changed values do not attest a physical host.',
            'before_sha256':core.digest(first),'after_sha256':core.digest(last),'window_context':interval(first,last)}


def observe(node,seconds=2):
    core.finite(seconds,minimum=.2,maximum=30)
    first=snapshot(node);time.sleep(seconds);last=snapshot(node)
    return {'schema':'g-skills.forensic-observation.v1','subject':core.alias(node),'tool_sha256':SOURCE_SHA256,
            'snapshots':[first,last],'interval':interval(first,last),'active_tests':False,'contact_authorized':False}


def save_private(path,value):
    path=Path(path).expanduser().absolute()
    if core.ROOT==path or core.ROOT in path.parents:raise core.InvalidEvidence('choose a private output outside the installed skill')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,'wb') as f:f.write(core.canonical(value)+b'\n')
    return {'path':str(path),'sha256':core.digest(value),'provider_cause_proven':False}


def register(sub):
    p=sub.add_parser('forensic-snapshot',help='Passive guest CPU/clock/storage/memory/network context; no active tests');p.add_argument('--node',required=True);p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('forensic-observe',help='Bounded repeated guest-context sample, retained raw sources');p.add_argument('--node',required=True);p.add_argument('--seconds',type=float,default=2);p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('forensic-compare',help='Compare guest traits without claiming physical migration proof');p.add_argument('--before',required=True,type=Path);p.add_argument('--after',required=True,type=Path);p.add_argument('--out',required=True,type=Path)


def dispatch(args):
    if args.cmd=='forensic-snapshot':value=snapshot(args.node)
    elif args.cmd=='forensic-observe':value=observe(args.node,args.seconds)
    elif args.cmd=='forensic-compare':value=compare(core.read_json(args.before),core.read_json(args.after))
    else:raise core.InvalidEvidence('unrecognized forensic command')
    return save_private(args.out,value)
