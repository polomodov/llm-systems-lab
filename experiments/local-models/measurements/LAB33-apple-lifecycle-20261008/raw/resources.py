import datetime, subprocess, re
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sample():
    row={'timestamp':now(),'commands':{}}
    for label,args in [('vm_stat',['vm_stat']),('swap',['sysctl','vm.swapusage']),('pressure',['memory_pressure','-Q']),('power_source',['pmset','-g','batt']),('power_mode',['pmset','-g','custom'])]:
        p=subprocess.run(args,capture_output=True,text=True,timeout=10)
        row['commands'][label]={'argv':args,'returncode':p.returncode,'stdout':re.sub(r'\(id=\d+\)','(battery identity omitted)',p.stdout),'stderr':p.stderr}
    vm=row['commands']['vm_stat']['stdout'];swap=row['commands']['swap']['stdout']
    pages=re.search(r'page size of (\d+) bytes',vm);free=re.search(r'Pages free:\s+(\d+)',vm);used=re.search(r'used = ([0-9.]+)([KMG])',swap)
    row['free_pages_bytes']=int(pages[1])*int(free[1]) if pages and free else None
    row['swap_used_bytes']=int(float(used[1])*{'K':1024,'M':1024**2,'G':1024**3}[used[2]]) if used else None
    row['on_ac_power']="Now drawing from 'AC Power'" in row['commands']['power_source']['stdout']
    ac=row['commands']['power_mode']['stdout'].split('AC Power:',1)[-1];mode=re.search(r'powermode\s+(\d+)',ac)
    row['ac_power_mode']=int(mode[1]) if mode else None
    return row

def safe(row):
    return row['free_pages_bytes'] is not None and row['free_pages_bytes']>=16*2**30 and row['swap_used_bytes']==0 and row['on_ac_power'] and row['ac_power_mode']==0

