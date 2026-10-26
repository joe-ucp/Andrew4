"""Conditional design robustness over an explicitly finite transport scenario set.

Run: python code/robustness.py. No probabilities or continuous parameter-box
coverage are inferred. Base primary-result files are neither read as evidence
nor overwritten. Units are SI internally, except declared output columns.
"""
from pathlib import Path
from functools import lru_cache
import csv, json, hashlib
import numpy as np
from scipy.special import jv,yv
from scipy.optimize import brentq
from numpy.polynomial.legendre import leggauss
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import modal
import finite_volume as fv

ROOT=Path(__file__).resolve().parents[1]
R=.00375; LMAX=.070; N=420000.
V=7*np.pi*(R*R-.003**2)*LMAX
RHO=N/(V*1e6)
GUARD=1e-7
EXPECTED_SPEC_SHA256='3a2013c3c6adfb42123b6858e9755c73b2422f125c4d18f772bcec0fba67eb7c'


def writecsv(name,rows):
    with (ROOT/'data'/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def geometry(h_mm):
    a=R-h_mm/1000
    length=V/(np.pi*(R*R-a*a)); n=int(np.ceil(length/LMAX-1e-10))
    remainder=length-(n-1)*LMAX
    assert 0<remainder<=LMAX+1e-12
    segments=[LMAX]*(n-1)+[remainder]
    return {'a':a,'length':length,'n':n,'remainder':remainder,'segments':segments,
      'area_cm2':2*np.pi*R*length*1e4,'end_area_cm2':2*n*np.pi*(R*R-a*a)*1e4,
      'width_mm':(n*2*R+(n-1)*.001)*1000,
      'footprint_cm2':max(segments)*(n*2*R+(n-1)*.001)*1e4}


@lru_cache(maxsize=2048)
def radial_modes(h_mm,D,P,nr):
    """Self-adjoint Robin spectrum, analytically weighted, no FV matrices."""
    a=R-h_mm/1000;h=R-a;aa=a/h;bb=R/h
    if P=='infinite':
        er,wr,meta=modal.annular_modes(a,R,nr)
        return er,wr,{'next':meta['next_eigenvalue_per_m2'],
          'residual':meta['max_root_residual'],'weight_sum':float(wr.sum()),
          'roots':np.sqrt(er)*h,'brackets':meta['brackets']}
    bi=float(P)*h/D
    def f0(q,x):return jv(0,q*x)*yv(1,q*aa)-yv(0,q*x)*jv(1,q*aa)
    def f1(q,x):return jv(1,q*x)*yv(1,q*aa)-yv(1,q*x)*jv(1,q*aa)
    def determinant(q):return q*f1(q,bb)-bi*f0(q,bb)
    roots=[];brackets=[];lo=1e-7;flo=determinant(lo);step=np.pi/16
    while len(roots)<nr+1:
        hi=lo+step;fhi=determinant(hi)
        if flo*fhi<0:
            roots.append(brentq(determinant,lo,hi,xtol=1e-12,rtol=1e-14))
            brackets.append([lo,hi])
        lo=hi;flo=fhi
    q=np.array(roots[:-1]);f0a=f0(q,aa);f0b=f0(q,bb);f1b=f1(q,bb)
    integral=bb*f1b/q
    norm=.5*(bb*bb*(f0b*f0b+f1b*f1b)-aa*aa*f0a*f0a)
    wr=integral**2/(norm*(bb*bb-aa*aa)/2)
    assert np.all(wr>=0) and wr.sum()<=1+1e-9
    return (q/h)**2,wr,{'next':(roots[-1]/h)**2,'residual':max(abs(determinant(x)) for x in q),
       'weight_sum':float(wr.sum()),'roots':q,'brackets':brackets[:-1]}


def continuum(h_mm,D,P,ends,nr=128,nz=256):
    g=geometry(h_mm);er,wr,mr=radial_modes(h_mm,D,P,nr)
    out={t:{'eta':0.,'tail':0.} for t in [15,30,60]}
    for length in sorted(set(g['segments'])):
        volume_weight=length*g['segments'].count(length)/g['length']
        ez,wz,mz=modal.axial_modes(length,nz,ends=='reflecting')
        rate=D*(er[:,None]+ez[None,:]);weight=wr[:,None]*wz[None,:]
        bound_s=max(0.,1-wr.sum())/(D*(mr['next']+ez[0]))
        if ends!='reflecting':
            bound_s+=max(0.,1-wz.sum())/(D*(mz['next_eigenvalue_per_m2']+er[0]))
        for t in out:
            out[t]['eta']+=volume_weight*modal.eta(rate.ravel(),weight.ravel(),t*60)
            out[t]['tail']+=volume_weight*bound_s/(t*60)
    for t in out:
        out[t]['lower']=out[t]['eta']-out[t]['tail']-GUARD
        out[t]['upper']=out[t]['eta']+GUARD
    return out,mr


@lru_cache(maxsize=256)
def fv_radial(h_mm,D,P,nr):
    return fv.radial(R-h_mm/1000,R,nr,D,None if P=='infinite' else float(P))[:2]


@lru_cache(maxsize=256)
def fv_axial(length,D,nz,ends):
    if ends=='reflecting':
        # Uniform source and reflecting ends excite only the constant axial mode.
        return np.array([0.]),np.array([1.])
    return fv.axial(length,nz,D,False)[:2]


def finite_volume(h_mm,D,P,ends,nr,nz):
    g=geometry(h_mm);er,wr=fv_radial(h_mm,D,P,nr)
    values={t:0. for t in [15,30,60]}
    for length in sorted(set(g['segments'])):
        ez,wz=fv_axial(length,D,nz,ends)
        rate=er[:,None]+ez[None,:];weight=wr[:,None]*wz[None,:]
        for t in values:
            values[t]+=length*g['segments'].count(length)/g['length']*modal.eta(rate.ravel(),weight.ravel(),t*60)
    return values


def quadrature_audit(h_mm,D,P,nr=128,order=1024):
    er,wr,mr=radial_modes(h_mm,D,P,nr)
    h=h_mm/1000;aa=(R-h)/h;bb=R/h;q=np.sqrt(er)*h
    x,w=leggauss(order);x=(x+1)*(bb-aa)/2+aa;w=w*(bb-aa)/2
    f=jv(0,q[:,None]*x)*yv(1,q[:,None]*aa)-yv(0,q[:,None]*x)*jv(1,q[:,None]*aa)
    integ=(f*(w*x)).sum(axis=1);norm=(f*f*(w*x)).sum(axis=1)
    qw=integ**2/(norm*(bb*bb-aa*aa)/2)
    return {'h_mm':h_mm,'D_m2_s':D,'P_m_s':P,'order':order,
       'max_weight_error':float(np.max(np.abs(qw-wr))),
       'sum_absolute_weight_error':float(np.sum(np.abs(qw-wr))),
       'root_residual_max':float(mr['residual'])}


def belongs(row,setting):
    return row['D_m2_s'] in setting['D'] and row['P_m_s'] in setting['P'] and row['end_condition'] in setting['ends']


def plot_results(frontier,reviewer,sets):
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.1))
    colors={'nominal_favorable':'#126782','near_nominal_discrete':'#d58033','broad_discrete':'#a64d79'}
    labels={'nominal_favorable':'Favorable nominal (1 scenario)','near_nominal_discrete':'Near-nominal set (8 scenarios)','broad_discrete':'Broad set (24 scenarios)'}
    for name in sets:
        rr=[r for r in frontier if r['scenario_set']==name and int(r['deadline_min'])==30]
        axes[0].plot([float(r['lateral_area_cm2']) for r in rr],[float(r['minimum_eta']) for r in rr],label=labels[name],color=colors[name])
    axes[0].axhline(.8,color='#888888',ls='--',lw=1)
    axes[0].set(xlabel='Lateral area at fixed dose (cm$^2$)',ylabel='Minimum 30-min delivery fraction',ylim=(0,1))
    axes[0].legend(frameon=False,fontsize=8,loc='lower right')
    names=['Perfect sinks','Reflecting ends','D reduced 5%',r'$D=10^{-10}$ m$^2$/s','h = 0.61 mm']
    values=[float(r['eta30']) for r in reviewer[:5]]
    axes[1].scatter(np.arange(5),values,s=50,color=['#126782','#d58033','#d58033','#a64d79','#d58033'],zorder=4)
    for i,value in enumerate(values):axes[1].text(i,value+.009,f'{value:.6f}',ha='center',fontsize=8)
    axes[1].axhline(.8,color='#444444',ls='--',lw=1)
    axes[1].set_xticks(np.arange(5),names,rotation=30,ha='right',fontsize=8)
    axes[1].set(ylabel='30-min delivery fraction',ylim=(.5,.85),xlim=(-.4,4.4),title='Sensitivity of the nominal h = 0.60 mm design')
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();fig.savefig(ROOT/'figures/robustness_frontier.png',dpi=180);fig.savefig(ROOT/'figures/robustness_frontier.pdf');plt.close(fig)


def main():
    spec_path=ROOT/'robustness_specification.json'
    actual_hash=hashlib.sha256(spec_path.read_bytes()).hexdigest()
    if actual_hash!=EXPECTED_SPEC_SHA256:
        raise RuntimeError('Robustness specification integrity failure: frozen specification changed; computation denied.')
    spec=json.loads(spec_path.read_text(encoding='utf-8'))
    rows=[];max_residual=0.;mins=1.;max_tail=0.;refined_count=0
    for hi,h in enumerate(np.round(np.arange(.10,1.001,.01),2)):
        h=float(h);g=geometry(h)
        for D in spec['scenarios']['D_m2_s']:
            for P in spec['scenarios']['outer_P_m_s']:
                for end in spec['scenarios']['ends']:
                    vals,meta=continuum(h,D,P,end)
                    # A retained-mode interval overlapping any target is refined
                    # before selection; the frozen target never moves.
                    if any(v['lower']<=target<=v['upper'] for v in vals.values() for target in spec['outputs']['eta_targets']):
                        vals,meta=continuum(h,D,P,end,512,1024);refined_count+=1
                    max_residual=max(max_residual,meta['residual']);mins=min(mins,meta['weight_sum'])
                    for t,v in vals.items():
                        max_tail=max(max_tail,v['tail'])
                        rows.append({'thickness_mm':h,'D_m2_s':D,'P_m_s':P,'end_condition':end,'deadline_min':t,
                           'eta':v['eta'],'eta_lower_estimate':v['lower'],'eta_upper_estimate':v['upper'],
                           'omitted_tail_bound_eta':v['tail'],'floating_guard_eta':GUARD,
                           'payload_IEQ':N,'density_IEQ_per_ml':RHO,'volume_ml':V*1e6,
                           'lateral_area_cm2':g['area_cm2'],'end_area_cm2':g['end_area_cm2'],
                           'area_ratio_to_nominal':g['length']/(7*LMAX),'total_length_mm':g['length']*1000,
                           'pouch_count':g['n'],'last_segment_mm':g['remainder']*1000,
                           'parallel_width_mm':g['width_mm'],'active_bounding_footprint_cm2':g['footprint_cm2'],
                           'thinner_than_150um_IEQ_reference_diameter':h<.15,
                           'parameter_status':'assumed discrete scenario; no probability or continuous-box guarantee'})
        if hi%10==0:print(f'Robustness map {hi+1}/91 thicknesses',flush=True)
    writecsv('robustness_map.csv',rows)
    frontier=[];targets=[];validation_cases=set()
    for set_name,setting in spec['sets'].items():
        for h in np.round(np.arange(.10,1.001,.01),2):
            for t in spec['outputs']['deadlines_min']:
                eligible=[row for row in rows if row['thickness_mm']==h and row['deadline_min']==t and belongs(row,setting)]
                worst=min(eligible,key=lambda row:row['eta'])
                frontier.append({'scenario_set':set_name,'scenario_count':len(eligible),'thickness_mm':float(h),'deadline_min':t,
                   'minimum_eta':worst['eta'],'minimum_eta_lower_estimate':min(r['eta_lower_estimate'] for r in eligible),
                   'minimum_eta_upper_estimate':min(r['eta_upper_estimate'] for r in eligible),
                   'worst_D_m2_s':worst['D_m2_s'],'worst_P_m_s':worst['P_m_s'],'worst_end_condition':worst['end_condition'],
                   'lateral_area_cm2':worst['lateral_area_cm2'],'area_ratio_to_nominal':worst['area_ratio_to_nominal'],
                   'pouch_count':worst['pouch_count'],'last_segment_mm':worst['last_segment_mm'],
                   'total_length_mm':worst['total_length_mm'],'active_bounding_footprint_cm2':worst['active_bounding_footprint_cm2']})
        for t in spec['outputs']['deadlines_min']:
            designs=[r for r in frontier if r['scenario_set']==set_name and r['deadline_min']==t]
            for target in spec['outputs']['eta_targets']:
                passing=[r for r in designs if r['minimum_eta_lower_estimate']>=target]
                selected=min(passing,key=lambda r:r['lateral_area_cm2']) if passing else None
                competitors=[r for r in designs if selected is None or r['lateral_area_cm2']<selected['lateral_area_cm2']-1e-9]
                uncertain=[r for r in competitors if r['minimum_eta_upper_estimate']>=target]
                status=('minimum within grid and discrete scenario set' if selected and not uncertain else
                       'feasible grid design; minimum unresolved' if selected else
                       'not attained in grid' if not uncertain else 'unresolved numerical threshold')
                item={'scenario_set':set_name,'deadline_min':t,'target_eta':target,'status':status,'unresolved_competitors':len(uncertain)}
                for col in ['thickness_mm','minimum_eta','minimum_eta_lower_estimate','lateral_area_cm2','area_ratio_to_nominal','pouch_count','last_segment_mm','total_length_mm','active_bounding_footprint_cm2','worst_D_m2_s','worst_P_m_s','worst_end_condition']:
                    item[col]=selected[col] if selected else ''
                targets.append(item)
                item['thinner_than_150um_IEQ_reference_diameter']=bool(selected and selected['thickness_mm']<.15)
                item['at_thickest_grid_boundary']=bool(selected and selected['thickness_mm']==1.)
                if selected:
                    validation_cases.add((selected['thickness_mm'],selected['worst_D_m2_s'],selected['worst_P_m_s'],selected['worst_end_condition']))
                    if selected['thickness_mm']<1:
                        neighbor=[r for r in designs if r['thickness_mm']==round(selected['thickness_mm']+.01,2)][0]
                        validation_cases.add((neighbor['thickness_mm'],neighbor['worst_D_m2_s'],neighbor['worst_P_m_s'],neighbor['worst_end_condition']))
    writecsv('robustness_frontier.csv',frontier);writecsv('robustness_targets.csv',targets)
    # Finite-set order is inspected, never promoted to continuous monotonicity.
    ordering=[]
    for h in [.10,.60,.75,1.00]:
        for t in [15,30,60]:
            subset=[r for r in rows if r['thickness_mm']==h and r['deadline_min']==t]
            worst=min(subset,key=lambda r:r['eta'])
            ordering.append({'thickness_mm':h,'deadline_min':t,'minimum_eta':worst['eta'],
                 'worst_D_m2_s':worst['D_m2_s'],'worst_P_m_s':worst['P_m_s'],'worst_end_condition':worst['end_condition'],
                 'scope':'observed ordering within evaluated discrete scenarios only'})
    writecsv('robustness_ordering.csv',ordering)
    for h in [.10,.60,.75,1.]:
        for D,P,end in [(1e-10,1e-6,'reflecting'),(3e-10,1e-5,'absorbing'),(3e-10,'infinite','absorbing')]:
            validation_cases.add((h,D,P,end))
    checks=[]
    for i,(h,D,P,end) in enumerate(sorted(validation_cases,key=str)):
        fine,meta=continuum(h,D,P,end,256,512)
        finer,_=continuum(h,D,P,end,512,1024)
        coarse_fv=finite_volume(h,D,P,end,160,560)
        fine_fv=finite_volume(h,D,P,end,320,1120)
        for t in fine:
            base=[row for row in rows if row['thickness_mm']==h and row['D_m2_s']==D and row['P_m_s']==P and row['end_condition']==end and row['deadline_min']==t][0]
            diff=fine_fv[t]-finer[t]['eta']
            checks.append({'thickness_mm':h,'D_m2_s':D,'P_m_s':P,'end_condition':end,'deadline_min':t,
              'map_eta':base['eta'],'modal256_512_eta':fine[t]['eta'],'modal512_1024_eta':finer[t]['eta'],
              'modal_refined_tail_eta':finer[t]['tail'],'FV160_560_eta':coarse_fv[t],'FV320_1120_eta':fine_fv[t],
              'FV_minus_refined_modal':diff,'FV_refinement_change':fine_fv[t]-coarse_fv[t]})
            assert abs(diff)<spec['numerics']['agreement_tolerance_eta']
            assert abs(base['eta']-finer[t]['eta'])<=base['omitted_tail_bound_eta']+2*GUARD
        if i%10==0:print(f'Independent scenario checks {i+1}/{len(validation_cases)}',flush=True)
    writecsv('robustness_verification.csv',checks)
    quad=[quadrature_audit(h,D,P) for h,D,P in [(0.10,3e-10,1e-6),(.60,2.85e-10,1e-5),(1.,1e-10,1e-6)]]
    assert max(x['sum_absolute_weight_error'] for x in quad)<GUARD/10
    # Reviewer diagnostics; no reconstruction of a new source input as evidence
    # about the original constant-production hypothesis.
    reviewer=[]
    for name,h,D,P,end in [
      ('h060_favorable',.60,3e-10,'infinite','absorbing'),
      ('h060_reflecting_ends',.60,3e-10,'infinite','reflecting'),
      ('h060_D_reduced_5percent',.60,2.85e-10,'infinite','absorbing'),
      ('h060_D_1e10',.60,1e-10,'infinite','absorbing'),
      ('h061_favorable',.61,3e-10,'infinite','absorbing'),
      ('h075_original_nominal',.75,3e-10,'infinite','absorbing')]:
        value,_=continuum(h,D,P,end,512,1024)
        reviewer.append({'check':name,'thickness_mm':h,'D_m2_s':D,'P_m_s':P,'ends':end,'eta30':value[30]['eta'],'tail_bound_eta':value[30]['tail']})
    writecsv('robustness_reviewer_checks.csv',reviewer)
    critical=brentq(lambda ratio:continuum(.60,ratio*3e-10,'infinite','absorbing',256,512)[0][30]['eta']-.8,.5,1.5,xtol=1e-10)*3e-10
    base_r,base_w,_=modal.combined(.003,R,.070,3e-10,256,512)
    impulse_out=1-float(np.dot(base_w,np.exp(-base_r*1800)))
    constant_eta=modal.eta(base_r,base_w,1800)
    waveform={'geometry':'nominal seven identical annuli; perfect outer/end sinks; D3e-10',
       'diffusion_timescale_h2_over_D_minutes':(.00075**2/3e-10)/60,
       'dimensionless_D_T_over_h2_at30min':3e-10*1800/.00075**2,
       'instant_uniform_initial_inventory_fraction_delivered_by30min':impulse_out,
       'constant_uniform_production_fraction_delivered_by30min':constant_eta,
       'interpretation':'Distinct inputs and molecule ages. Impulse uses equal total amount present internally at t0; constant source distributes that amount over30min. An ideal production impulse has no finite peak-rate constraint; it is not a demonstrated physiological burst. No stored-inventory evidence is supplied.'}
    (ROOT/'evidence/robustness_waveform.json').write_text(json.dumps(waveform,indent=2)+'\n',encoding='utf-8')
    plot_results(frontier,reviewer,spec['sets'])
    summary={'schema_version':'1.0','specification_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),
       'scope':'Finite assumed scenario sets; names are arbitrary labels, not established physical ranges. No continuous-box or probability statement. Thickest-boundary minima do not imply an unconstrained optimum.',
       'physical_feasibility':'Grid includes layers thinner than150um IEQ reference diameter. Those continuous-source idealizations are explicitly flagged, not asserted packable or buildable.',
       'map_rows':len(rows),'scenario_combinations_per_h':24,'thickness_count':91,'deadline_count':3,
       'targets':targets,'reviewer_checks':reviewer,'critical_D_h060_m2_s':critical,'waveform':waveform,
       'max_modal_tail_eta':max_tail,'max_root_residual':float(max_residual),'min_radial_weight_sum':mins,
       'near_threshold_scenarios_refined':refined_count,'FV_validation_case_count':len(validation_cases),
       'max_FV_modal_difference_eta':max(abs(x['FV_minus_refined_modal']) for x in checks),
       'max_FV_refinement_change_eta':max(abs(x['FV_refinement_change']) for x in checks),
       'max_map_refined_modal_difference_eta':max(abs(x['map_eta']-x['modal512_1024_eta']) for x in checks),
       'quadrature_checks':quad,'floating_guard_eta':GUARD,
       'threshold_scope':'Lower-tail plus guard selects passing designs; every smaller-area competitor must have a failing scenario upper estimate. Intervals are numerical estimates, not certified enclosures.',
       'checks':'PASS; independent FV and continuum Robin calculations and target-selection checks completed'}
    (ROOT/'evidence/robustness_verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'critical_D_h060_m2_s':critical,'map_rows':len(rows),'validation_cases':len(validation_cases),'reviewer_checks':reviewer},indent=2),flush=True)


if __name__=='__main__':main()
