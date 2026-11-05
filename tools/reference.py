"""List-based, unbounded-time specification, separate from the C state machine.

It reasons about recorded qualifying observations and lifts wrapped timestamps
onto an integer timeline. It is a test oracle, not flight code or independent
peer review. Firmware decisions cannot establish continuity of an unseen signal.
"""
M=1<<32
HALF=1<<31
FIELDS=('rc','alarm','quality','pending','span','count','accepted','rejected','epochs','bad_clock')

def forward(stamp,previous,strict=False):
    candidate=(previous//M)*M+stamp
    if candidate<previous:candidate+=M
    distance=candidate-previous
    return None if distance>=HALF or (strict and distance==0) else candidate

def past(stamp,now):
    candidate=(now//M)*M+stamp
    if candidate>now:candidate-=M
    return candidate

class Reference:
    def __init__(self,cfg):
        self.cfg=cfg
        self.now=None
        self.alarm=0
        self.quality=0
        self.sequence=None
        self.accepted_acq=None
        self.live_acq=None
        self.epoch_floor=None
        self.observations=[]
        self.accepted=self.rejected=self.epochs=self.bad_clock=0

    def invalid(self,quality):
        self.quality=quality;self.live_acq=None;self.observations=[]

    def snapshot(self,rc):
        run=self.observations
        span=0
        if run:
            span=self.now-run[0][1] if self.cfg['policy']==1 else run[-1][0]-run[0][0]
        return (rc,self.alarm,self.quality,(2 if self.alarm else 1) if run else 0,
                span,len(run),self.accepted,self.rejected,self.epochs,self.bad_clock)

    def step(self,e):
        cfg=self.cfg
        current=e['now'] if self.now is None else forward(e['now'],self.now)
        if current is None:
            self.bad_clock=min(M-1,self.bad_clock+1);self.invalid(3)
            return self.snapshot(-2)
        self.now=current
        if self.live_acq is not None and self.now-self.live_acq>cfg['max_age']:self.invalid(2)
        accepted=False;rc=0
        if e['kind']==2:
            self.invalid(3)
        elif e['kind']==3:
            self.invalid(0);self.sequence=None;self.accepted_acq=None
            self.epoch_floor=self.now;self.epochs=min(M-1,self.epochs+1)
        elif e['kind']==1:
            acquired=past(e['acquired'],self.now)
            sequence=e['sequence'] if self.sequence is None else forward(e['sequence'],self.sequence,strict=True)
            valid=(self.now-acquired<HALF and self.now-acquired<=cfg['max_age'] and sequence is not None
                   and (self.accepted_acq is None or 0<=acquired-self.accepted_acq<HALF)
                   and (self.epoch_floor is None or 0<=acquired-self.epoch_floor<HALF))
            if not valid:
                self.rejected=min(M-1,self.rejected+1);rc=1
            else:
                self.sequence=sequence;self.accepted_acq=acquired;self.live_acq=acquired
                self.epoch_floor=None;self.quality=1;self.accepted=min(M-1,self.accepted+1);accepted=True
                value=e['value']; desired=(value<=cfg['clear_limit']) if self.alarm else (value>=cfg['trip_limit'])
                if not desired:self.observations=[]
                else:
                    if cfg['policy']==2 and self.observations and acquired-self.observations[-1][0]>cfg['max_gap']:
                        self.observations=[]
                    self.observations.append((acquired,self.now))
        elif e['kind']!=0:
            self.rejected=min(M-1,self.rejected+1);self.invalid(3);rc=-3
        run=self.observations
        if run and self.quality==1:
            duration=cfg['clear_ticks'] if self.alarm else cfg['trip_ticks']
            ready=((cfg['policy']==0 and accepted and len(run)>=cfg['samples'])
                   or (cfg['policy']==1 and self.now-run[0][1]>=duration)
                   or (cfg['policy']==2 and accepted and run[-1][0]-run[0][0]>=duration))
            if ready:self.alarm=1-self.alarm;self.observations=[]
        return self.snapshot(rc)

def reference(cfg,events):
    state=Reference(cfg)
    return [state.step(e) for e in events]
