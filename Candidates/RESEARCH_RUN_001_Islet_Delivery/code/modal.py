"""Independent continuum eigenfunction calculation in SI units.

No finite-volume matrix is used here. See METHODS.md for derivation.
"""
import numpy as np
from scipy.special import jv, yv
from scipy.optimize import brentq
from numpy.polynomial.legendre import leggauss


def annular_modes(a, b, count=128):
    h = b-a
    aa, bb = a/h, b/h
    def determinant(q):
        return jv(0,q*bb)*yv(1,q*aa)-yv(0,q*bb)*jv(1,q*aa)
    roots, brackets = [], []
    lo, flo, step = 1e-7, determinant(1e-7), np.pi/8
    while len(roots)<count+1:
        hi=lo+step; fhi=determinant(hi)
        if flo*fhi<0:
            roots.append(brentq(determinant,lo,hi,xtol=1e-12,rtol=1e-14))
            brackets.append((lo,hi))
        lo,flo=hi,fhi
    q=np.asarray(roots[:-1]); k=q/h
    def f0(x):
        return jv(0,q*x)*yv(1,q*aa)-yv(0,q*x)*jv(1,q*aa)
    f1b=jv(1,q*bb)*yv(1,q*aa)-yv(1,q*bb)*jv(1,q*aa)
    norm=(bb**2*f1b**2-aa**2*f0(aa)**2)/2
    integ=bb*f1b/q
    weights=integ**2/(norm*((bb**2-aa**2)/2))
    return k*k,weights,{'q_roots':q.tolist(),'brackets':brackets[:-1],
        'max_root_residual':float(max(abs(determinant(x)) for x in q)),
        'next_eigenvalue_per_m2':float((roots[-1]/h)**2),
        'weight_sum':float(weights.sum()),'min_weight':float(weights.min()),
        'analytic_norm_min':float(norm.min())}


def quadrature_check(a,b,count=128,order=1024):
    vals,w,meta=annular_modes(a,b,count)
    h=b-a; aa=a/h; bb=b/h; q=np.sqrt(vals)*h
    nodes,weights=leggauss(order)
    x=(nodes+1)*(bb-aa)/2+aa; wg=weights*(bb-aa)/2
    f=jv(0,q[:,None]*x)*yv(1,q[:,None]*aa)-yv(0,q[:,None]*x)*jv(1,q[:,None]*aa)
    integ=np.sum(f*(wg*x),axis=1)
    norm=np.sum(f*f*(wg*x),axis=1)
    qw=integ**2/(norm*((bb**2-aa**2)/2))
    return {'order':order,'max_weight_error':float(np.max(np.abs(qw-w))),
            'sum_absolute_weight_error':float(np.sum(np.abs(qw-w)))}


def axial_modes(length,count=256,reflecting=False):
    if reflecting:
        return np.array([0.]),np.array([1.]),{'next_eigenvalue_per_m2':float('inf'),'weight_sum':1.}
    odd=2*np.arange(count)+1
    return (odd*np.pi/length)**2,8/(np.pi**2*odd**2),{
        'next_eigenvalue_per_m2':float(((2*count+1)*np.pi/length)**2),
        'weight_sum':float(np.sum(8/(np.pi**2*odd**2)))}


def combined(a,b,length,D=3e-10,nr=128,nz=256,reflecting=False):
    er,wr,mr=annular_modes(a,b,nr); ez,wz,mz=axial_modes(length,nz,reflecting)
    rates=D*(er[:,None]+ez[None,:])
    weights=wr[:,None]*wz[None,:]
    return rates.ravel(),weights.ravel(),{'radial':mr,'axial':mz,
        'eta_tail_bound_coefficient_s':float(
            max(0.,1-wr.sum())/(D*(mr['next_eigenvalue_per_m2']+ez[0]))+
            max(0.,1-wz.sum())/(D*(mz['next_eigenvalue_per_m2']+er[0])))}


def integral_survival(rates,weights,t):
    return float(np.dot(weights,-np.expm1(-rates*t)/rates))


def eta(rates,weights,t):
    return 1-integral_survival(rates,weights,t)/t


def pulse_response(rates,weights,t,tau=1800.):
    if t==0:
        return 0.,0.,0.
    if t<=tau:
        retained=integral_survival(rates,weights,t)
        # Completeness fixes the exact zero-age survival; the returned flux has
        # an omitted positive survival tail no larger than 1-sum(weights).
        flux=1-float(np.dot(weights,np.exp(-rates*t)))
    else:
        lag=t-tau
        retained=float(np.dot(weights,np.exp(-rates*lag)*(-np.expm1(-rates*tau))/rates))
        flux=float(np.dot(weights,np.exp(-rates*lag)*(-np.expm1(-rates*tau))))
    return retained,flux,min(t,tau)-retained
