import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('coding_holdout',Path(__file__).with_name('evaluate_coding_memory.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.TASKS=[
 dict(name='replica-leases',field='read_only_replica',values=[31,73],query='Implement the agreed lease duration for both replica modes.',contract='Replica lease duration is a previously agreed project-specific value in seconds. Do not infer it from read-only status.',history=['The developer chose a lease duration of exactly 31 seconds for read_only_replica=true after a local recovery fixture. No distributed failover guarantee was established.','For read_only_replica=false the developer chose a lease duration of exactly 73 seconds after another fixture. This is a separate mode-specific policy, not a replacement for the read-only replica policy.']),
 dict(name='preview-cache',field='public_preview',values=[17,43],query='Implement the cache retention product policy for both preview modes.',contract='Preview cache retention follows earlier product decisions in minutes. The durations are not implied by public or private visibility.',history=['After a synthetic preview test the developer chose cache retention of exactly 17 minutes when public_preview=true. This setting was not evaluated under production load.','The developer chose cache retention of exactly 43 minutes when public_preview=false. The private-preview value complements the public-preview policy; no universal privacy guarantee was tested.']),
]
raise SystemExit(m.main())
