import dynesty
import numpy as np
import multiprocessing as mp
import os
import time
import pytest
from utils import get_rstate
import itertools


def like(x):
    return -.5 * np.sum(x**2)


NLIVE = 300


def ptform(x):
    return 20 * x - 10


def interrupter(pid, dt):
    time.sleep(dt)
    os.kill(pid, 9)


def start_interrupter(pid, dt):
    pp = mp.Process(target=interrupter, args=(pid, dt))
    pp.start()
    return pp


def fit(fname, dynamic):
    ndim = 2
    if dynamic:
        dns = dynesty.DynamicNestedSampler(like,
                                           ptform,
                                           ndim,
                                           nlive=NLIVE,
                                           rstate=get_rstate())
    else:
        dns = dynesty.NestedSampler(like,
                                    ptform,
                                    ndim,
                                    nlive=NLIVE,
                                    rstate=get_rstate())
    dns.run_nested(checkpoint_file=fname)
    return dns


def fit_resume(fname, dynamic, result0):
    if dynamic:
        dns = dynesty.DynamicNestedSampler.restore(fname)
    else:
        dns = dynesty.NestedSampler.restore(fname)
    print('resuming')
    dns.run_nested(resume=True)
    print(dns.results.logz[-1], result0)
    assert np.abs(dns.results.logz[-1] - result0) < 1e-3


class cache:
    dt0 = None
    dt1 = None
    res0 = None
    res1 = None


def getlogz():
    if cache.dt0 is None:
        t0 = time.time()
        result0 = fit(None, False).results.logz[-1]
        t1 = time.time()
        result1 = fit(None, True).results.logz[-1]
        t2 = time.time()
        cache.dt0, cache.dt1, cache.res0, cache.res1 = t1 - t0, t2 - t1, result0, result1
    return cache.dt0, cache.dt1, cache.res0, cache.res1


@pytest.mark.parametrize(
    "dynamic,delay",
    itertools.product([False, True], [.05, .5, .75, .95]
                      #[1, 5, 10, 15]
                      ))
@pytest.mark.xdist_group(name="group1")
def test_resume(dynamic, delay):
    pid = os.getpid()
    fname = 'xx%d.pkl' % (pid)
    # result0 = fit(None, dynamic).results
    dt0, dt1, res_static, res_dynamic = getlogz()
    pp = mp.Process(target=fit, args=(fname, dynamic))
    pp.start()
    fit_pid = pp.pid
    if dynamic:
        curdt = dt0
    else:
        curdt = dt1
    pp = start_interrupter(fit_pid, delay * curdt)
    time.sleep(delay + 1)
    if dynamic:
        res0 = res_dynamic
    else:
        res0 = res_static
    fit_resume(fname, dynamic, res0)
    os.unlink(fname)
