"""Conservative cylindrical FV; exact-time discrete spectral propagation.

Cell mass coefficients and face conductances are constructed independently of
the continuum Bessel/sine solution. A tensor sum is an axisymmetric 2-D FV grid.
"""
import numpy as np
from scipy.linalg import eigh_tridiagonal


def radial(a,b,n,D,permeability=None,source_outer_width=None):
    faces=np.linspace(a,b,n+1); dr=(b-a)/n
    mass=(faces[1:]**2-faces[:-1]**2)/2
    g=D*faces[1:-1]/dr
    if permeability is None:
        gout=D*b/(dr/2)
    else:
        gout=b/(dr/(2*D)+1/permeability)
    diag=np.r_[g,0.]+np.r_[0.,g]; diag[-1]+=gout
    diag/=mass
    off=-g/np.sqrt(mass[:-1]*mass[1:])
    eig,U=eigh_tridiagonal(diag,off)
    source=np.ones(n)
    if source_outer_width is not None:
        cut=b-source_outer_width
        occupied=np.maximum(0.,faces[1:]**2-np.maximum(faces[:-1],cut)**2)/2
        source=occupied/mass*(b*b-a*a)/(b*b-cut*cut)
    integ=U.T@np.sqrt(mass)
    coeff=U.T@(np.sqrt(mass)*source)
    weights=integ*coeff/mass.sum()
    return eig,weights,{'mass':mass,'U':U,'coeff':coeff,'gout':gout,'source':source,'faces':faces}


def axial(length,n,D,reflecting=False):
    dz=length/n; mass=np.full(n,dz); g=D/dz
    diag=np.full(n,2*g); diag[[0,-1]]=g
    if not reflecting:diag[[0,-1]]+=2*g
    eig,U=eigh_tridiagonal(diag/mass,np.full(n-1,-g/dz))
    eig=np.maximum(eig,0)
    coeff=U.T@np.sqrt(mass)
    return eig,coeff**2/length,{'mass':mass,'U':U,'coeff':coeff,'gout':0. if reflecting else 2*g}


def combined(a,b,length,D=3e-10,nr=160,nz=560,reflecting=False,permeability=None,source_outer_width=None):
    er,wr,rr=radial(a,b,nr,D,permeability,source_outer_width)
    ez,wz,zz=axial(length,nz,D,reflecting)
    return (er[:,None]+ez[None,:]).ravel(),(wr[:,None]*wz[None,:]).ravel(),{'radial':rr,'axial':zz,'er':er,'ez':ez}


def field_audit(meta,t=1800.,tau=1800.,steady=False):
    rr,zz=meta['radial'],meta['axial']; rate=meta['er'][:,None]+meta['ez'][None,:]
    if steady: integ=1/rate
    elif t<=tau:integ=-np.expm1(-rate*t)/rate
    else:integ=np.exp(-rate*(t-tau))*(-np.expm1(-rate*tau))/rate
    coeff=rr['coeff'][:,None]*zz['coeff'][None,:]*integ
    c=(rr['U']@coeff@zz['U'].T)/np.sqrt(rr['mass'][:,None]*zz['mass'][None,:])
    volume=rr['mass'].sum()*zz['mass'].sum()
    inventory=float(np.sum(c*rr['mass'][:,None]*zz['mass'][None,:])/volume)
    flux=(rr['gout']*np.dot(c[-1,:],zz['mass'])+
          zz['gout']*np.dot(c[:,0]+c[:,-1],rr['mass']))/volume
    ir=rr['U'].T@np.sqrt(rr['mass']); iz=zz['U'].T@np.sqrt(zz['mass'])
    edge_r=rr['gout']*rr['U'][-1,:]/np.sqrt(rr['mass'][-1])
    edge_z=zz['gout']*(zz['U'][0,:]/np.sqrt(zz['mass'][0])+zz['U'][-1,:]/np.sqrt(zz['mass'][-1]))
    face_coeff=(edge_r[:,None]*iz[None,:]+ir[:,None]*edge_z[None,:])*(rr['coeff'][:,None]*zz['coeff'][None,:])/volume
    def integrated_step_flux(time):
        return float(np.sum(face_coeff*(time/rate+np.expm1(-rate*time)/rate**2)))
    cumulative=integrated_step_flux(t)-(integrated_step_flux(t-tau) if t>tau else 0.)
    return {'time_s':t,'steady':steady,'min_concentration_source_seconds':float(c.min()),
            'max_concentration_source_seconds':float(c.max()),'inventory_source_seconds':inventory,
            'boundary_flux_over_source_rate':float(flux),
            'cumulative_boundary_flux_source_seconds':cumulative if not steady else None,
            'independent_face_integral_mass_error_source_seconds':min(t,tau)-inventory-cumulative if not steady else None}
