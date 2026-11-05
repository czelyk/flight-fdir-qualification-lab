"""Declared synthetic fixtures; no mission thresholds or hardware timing."""
import random
MASK=(1<<32)-1
TOKENS=('good','bad','neutral','tick','gap','duplicate','invalid','epoch')
PROFILES=[dict(trip_limit=20,clear_limit=10,trip_ticks=4,clear_ticks=3,max_age=6,max_gap=2,samples=3),
          dict(trip_limit=20,clear_limit=10,trip_ticks=2,clear_ticks=2,max_age=3,max_gap=1,samples=2)]
POLICIES=('count','hold','observed')
def event(kind,now,acquired=None,sequence=0,value=0):
    return dict(kind=kind,now=now&MASK,acquired=(now if acquired is None else acquired)&MASK,
                sequence=sequence&MASK,value=value)

def expand(tokens,profile,base=0):
    now=base;seq=1;last=(base,0,25);out=[]
    for token in tokens:
        if token in ('good','bad','neutral'):
            now+=2;value={'good':5,'bad':25,'neutral':15}[token]
            last=(now,seq,value);out.append(event(1,now,now,seq,value));seq+=1
        elif token=='tick':now+=1;out.append(event(0,now))
        elif token=='gap':now+=profile['max_age']+1;out.append(event(0,now))
        elif token=='duplicate':
            now+=1;out.append(event(1,now,*last))
        elif token=='invalid':now+=1;out.append(event(2,now))
        elif token=='epoch':now+=1;seq=0;out.append(event(3,now))
    return out

def named_cases():
    S=lambda t,v=25,s=None,a=None:event(1,t,t if a is None else a,t if s is None else s,v)
    return {
      'one_sample_then_silence':[S(0),event(0,4),event(0,7)],
      'same_tick_burst':[S(0,s=0),S(0,s=1),S(0,s=2)],
      'qualified_then_stale':[S(0),S(2),S(4),event(0,11)],
      'gap_then_new_bad':[S(0),S(1),S(5),event(0,7)],
      'neutral_breaks_run':[S(0),S(2,15),S(4),S(6),S(8)],
      'stale_good_does_not_clear':[S(0),S(2),S(4),S(10,5,s=10,a=1),event(0,11)],
      'clear_requires_evidence':[S(0),S(2),S(4),S(5,5),event(0,8),S(9,5),S(11,5),S(12,5)],
      'nominal_cadence_agreement':[S(0),S(2),S(4),S(6,5),S(8,5),S(10,5)],
      'producer_epoch_retains_alarm':[S(0),S(2),S(4),event(3,5),S(6,5,s=0),S(8,5,s=1),S(9,5,s=2)],
      'pre_epoch_queue_item':[S(0),event(3,2),S(3,s=0,a=1),S(4,s=0,a=4)],
      'sequence_wrap':[S(0,s=MASK-1),S(2,s=MASK),S(4,s=0)],
      'clock_wrap':[S(MASK-2,s=0),S(MASK,s=1),S(1,s=2),event(0,8)],
      'future_acquisition':[S(1,s=0,a=2),S(2,s=1,a=2)],
      'clock_regression':[S(3),event(0,2),S(4,s=4)],
      'half_range_ambiguity':[S(0),event(0,1<<31)],
      'invalid_quality_preserves_alarm':[S(0),S(2),S(4),event(2,5),S(6,5,s=6)],
      'out_of_order_source':[S(0,s=0),S(2,s=2),S(3,s=1,a=1),S(4,s=3)],
      'boundary_age':[S(0),event(0,6),event(0,7)],
      'threshold_endpoints':[S(0,20),S(2,20),S(4,20),S(5,10),S(7,10),S(8,10)]
    }

def random_cases(n=256,seed=20261104):
    rng=random.Random(seed)
    for index in range(n):
        now=(MASK-rng.randrange(8)) if index%2 else rng.randrange(32)
        seq=MASK-2 if index%3==0 else 0
        packets=[];out=[]
        for _ in range(24):
            now+=rng.choice([0,1,2,3,8]);kind=rng.randrange(9)
            if kind<=2:
                acquired=now-rng.choice([0,0,1,2,9,-1]);value=rng.choice([-2147483648,5,10,15,20,25,2147483647])
                packet=event(1,now,acquired,seq,value);seq+=1;packets.append(packet);out.append(packet)
            elif kind==3 and packets:
                packet=dict(rng.choice(packets));packet['now']=now&MASK;out.append(packet)
            elif kind==4:out.append(event(2,now))
            elif kind==5:out.append(event(3,now));seq=0
            elif kind==6:out.append(event(0,now-1))
            elif kind==7:out.append(event(99,now))
            else:out.append(event(0,now))
        yield out
