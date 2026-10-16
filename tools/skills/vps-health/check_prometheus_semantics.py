#!/usr/bin/env python3
"""Evaluate actual stock-adapter PromQL with an installed promtool (developer-only).

No server, exporter, network request or deployment. This is query-semantics proof,
not validation of a user's Prometheus deployment or underlying raw-scrape coverage.
"""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/vps-health/scripts'))
import vps_health as core


def fixture():
    # Binary-exact increments avoid promtool's exact-float fixture mismatch.
    label='example.invalid:9100';queries=core.metrics_queries(label);series=[]
    for mode in ('user','nice','system','idle','iowait','irq','softirq','steal'):
        values=[0.]
        for minute in range(1,121):
            accounted=.5 if (minute-1)%60<55 else .9375
            rate=.25 if mode=='user' else accounted-.25 if mode=='idle' else 1-accounted if mode=='steal' else 0.
            values.append(values[-1]+rate*60)
        series.append({'series':f'node_cpu_seconds_total{{instance="{label}",cpu="0",mode="{mode}"}}',
                       'values':' '.join(format(x,'.12g') for x in values)})
    series.append({'series':f'up{{instance="{label}"}}','values':'1+0x120'})
    tests=[]
    # The actual query sees only the quiet final five minutes, not an hour.
    for at in ('60m','120m'):
        tests.append({'expr':queries['cpu_accounted_ratio'],'eval_time':at,'exp_samples':[{'labels':'{}','value':.9375}]})
    # A long view does not cure this: it evaluates the same expression repeatedly.
    tests.append({'expr':'avg_over_time(('+queries['cpu_accounted_ratio']+')[1h:1h])','eval_time':'120m',
                  'exp_samples':[{'labels':'{}','value':.9375}]})
    return {'evaluation_interval':'1m','tests':[{'name':'coarse evaluation cannot expand five-minute source support',
             'interval':'1m','input_series':series,'promql_expr_test':tests}]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--promtool',default=shutil.which('promtool'));parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if not args.promtool:raise SystemExit('NOT VERIFIED: an approved local promtool is required; no install attempted')
    import yaml
    body=fixture()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'semantics.yml';path.write_text(yaml.safe_dump(body,sort_keys=False))
        check=subprocess.run([args.promtool,'test','rules',str(path)],capture_output=True,text=True,timeout=30)
        if check.returncode:raise SystemExit(check.stdout+check.stderr)
    version=subprocess.check_output([args.promtool,'--version'],text=True,stderr=subprocess.STDOUT,timeout=10).splitlines()[0]
    receipt={'schema':'g-skills.promql-window-proof.v1','state':'PASS','engine':version,
             'query_source_sha256':core.SOURCE_SHA256,'evaluated_cases':3,'reported_five_minute_ratio':.9375,
             'synthetic_time_weighted_hour_ratio':(.5*55+.9375*5)/60,
             'query_window_seconds':300,'hourly_windows_do_not_imply_hourly_observation':True,
             'raw_scrape_coverage_certified':False,'network_or_service_started':False}
    if args.out:
        args.out.mkdir(mode=0o700,parents=True,exist_ok=False)
        (args.out/'semantics.yml').write_text(yaml.safe_dump(body,sort_keys=False))
        (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
