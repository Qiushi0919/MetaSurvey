"""Bounded operator phase deadline, no capture/review/append implementation."""
import math,signal,threading,time
from contextlib import contextmanager

class DeadlineViolation(ValueError):pass
LIMITS={'capture':900,'independent_review':1800,'append':300}
class OneShotBudget:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.started=clock();self.last=self.started;self.consumed=set();self.failed=False;self.active=None;self.completed=[]
        if type(self.started) not in (float,int) or not math.isfinite(self.started):raise DeadlineViolation('HB_MONOTONIC_CLOCK_INVALID')
    def fail(self,code):
        self.failed=True;raise DeadlineViolation(code)
    def remaining(self):
        try:now=self.clock()
        except BaseException:self.failed=True;raise
        if type(now) not in (float,int) or not math.isfinite(now) or now<self.last:
            self.failed=True;raise DeadlineViolation('HB_MONOTONIC_CLOCK_INVALID')
        self.last=now;return 3600-(now-self.started)
    def begin(self,phase):
        order=tuple(LIMITS)
        if self.failed or type(phase) is not str or phase not in LIMITS or phase in self.consumed or self.active is not None or len(self.completed)>=len(order) or phase!=order[len(self.completed)]:self.fail('HB_PHASE_INVALID_OR_CONSUMED')
        remaining=self.remaining()
        if remaining<=0:self.failed=True;raise DeadlineViolation('HB_WHOLE_RUN_TIMEOUT')
        self.consumed.add(phase);self.active=(phase,self.last);return self.last,min(LIMITS[phase],remaining)
    def finish(self,phase,started):
        if self.failed or self.active!=(phase,started):self.fail('HB_PHASE_INVALID_OR_CONSUMED')
        if self.remaining()<=0:self.failed=True;raise DeadlineViolation('HB_WHOLE_RUN_TIMEOUT')
        if self.last-started>=LIMITS[phase]:self.failed=True;raise DeadlineViolation('HB_'+phase.upper()+'_TIMEOUT')
        self.completed.append(phase);self.active=None
    @contextmanager
    def phase(self,phase):
        installed=False;old=None
        try:
            # Never take ownership of a caller's existing timer; all failure latches.
            if threading.current_thread() is not threading.main_thread() or not hasattr(signal,'setitimer'):self.fail('HB_TIMEOUT_SUPERVISOR_UNAVAILABLE')
            if signal.getitimer(signal.ITIMER_REAL)!=(0.0,0.0):self.fail('HB_EXISTING_TIMER_CONFLICT')
            start,limit=self.begin(phase);old=signal.getsignal(signal.SIGALRM)
            def timeout(*_):self.fail('HB_'+phase.upper()+'_TIMEOUT')
            signal.signal(signal.SIGALRM,timeout);installed=True
            remaining=self.remaining()
            if remaining<=0:self.fail('HB_WHOLE_RUN_TIMEOUT')
            limit=min(limit-(self.last-start),remaining)
            if limit<=0:self.fail('HB_'+phase.upper()+'_TIMEOUT')
            signal.setitimer(signal.ITIMER_REAL,limit)
            yield
            self.finish(phase,start)
        except BaseException:
            self.failed=True;raise
        finally:
            if installed:
                try:
                    try:signal.setitimer(signal.ITIMER_REAL,0)
                    finally:signal.signal(signal.SIGALRM,old)
                except BaseException:self.failed=True;raise

def actual_run(*a,**k):raise DeadlineViolation('HB_NO_IMPLICIT_ACTUAL_ORCHESTRATION')
