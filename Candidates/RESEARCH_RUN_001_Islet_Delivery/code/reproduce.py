"""Reconstruct every computational table and original scientific figure.

Usage: python code/reproduce.py (from any working directory).
All computations are local CPU operations and require no source-data download.
"""
from pathlib import Path
import csv, json, hashlib, platform, sys
import numpy as np
import scipy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import brentq
import modal
import finite_volume as fv

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; EVID=ROOT/'evidence'; FIG=ROOT/'figures'
for d in (DATA,EVID,FIG):d.mkdir(exist_ok=True)
A=.003; B=.00375; L=.070; D=3e-10; N=420000.; TAU=1800.
V=7*np.pi*(B*B-A*A)*L
RHO=N/(V*1e6)


def savecsv(name,rows):
    with (DATA/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def etaof(r,w,t):return modal.eta(r,w,t)


def run():
    frozen_sha='e1a5f46cdddaa4fbf75dc2745bbd8303ff4c8b81ea99cfccdd49ab91da9038bc'
    if hashlib.sha256((ROOT/'model_specification.json').read_bytes()).hexdigest()!=frozen_sha:
        raise ValueError('Frozen model specification changed; create an explicit amended run before reproducing these claims.')
    spec=json.loads((ROOT/'model_specification.json').read_text())
    assert spec['transport']['D_m2_per_s']==D and spec['source']['pulse_duration_s']==TAU
    r,w,meta=modal.combined(A,B,L,D)
    eta30=etaof(r,w,TAU)
    print('Continuum eta30',eta30,flush=True)
    convergence=[]
    for nr,nz in zip([40,80,160,320],[140,280,560,1120]):
        rf,wf,mf=fv.combined(A,B,L,D,nr,nz)
        value=etaof(rf,wf,TAU)
        convergence.append({'method':'finite_volume','radial_count':nr,'axial_count':nz,'eta30':value,
                            'difference_from_finest_continuum':value-eta30,'modal_tail_bound_eta':0.})
        print('FV',nr,nz,value,flush=True)
    fvfine=convergence[-1]['eta30']
    fvgrid=abs(convergence[-1]['eta30']-convergence[-2]['eta30'])
    for nr,nz in zip([32,64,128],[64,128,256]):
        rm,wm,mm=modal.combined(A,B,L,D,nr,nz)
        convergence.append({'method':'continuum_modal','radial_count':nr,'axial_count':nz,'eta30':etaof(rm,wm,TAU),
                            'difference_from_finest_continuum':etaof(rm,wm,TAU)-eta30,
                            'modal_tail_bound_eta':mm['eta_tail_bound_coefficient_s']/TAU})
    savecsv('convergence.csv',convergence)
    qc=[modal.quadrature_check(A,B,128,o) for o in [512,1024]]
    tail=meta['eta_tail_bound_coefficient_s']/TAU
    uncertainty=max(abs(fvfine-eta30),fvgrid,tail+qc[-1]['sum_absolute_weight_error'],1e-8)
    interval=[eta30-uncertainty,eta30+uncertainty]
    assert abs(fvfine-eta30)<.005 and uncertainty<.002
    rf,wf,mf=fv.combined(A,B,L,D,80,280)
    audits=[]
    for t,steady in [(300,False),(1800,False),(3600,False),(9000,False),(1800,True)]:
        audit=fv.field_audit(mf,t,TAU,steady)
        if not steady:
            retained,flux,delivered=modal.pulse_response(rf,wf,t,TAU)
            audit['inventory_spectral_discrepancy']=audit['inventory_source_seconds']-retained
            audit['flux_spectral_discrepancy']=audit['boundary_flux_over_source_rate']-flux
            audit['algebraic_mass_identity_error_source_seconds']=min(t,TAU)-retained-delivered
            assert abs(audit['independent_face_integral_mass_error_source_seconds'])<1e-7
            assert abs(audit['flux_spectral_discrepancy'])<1e-7
            assert abs(audit['inventory_spectral_discrepancy'])<1e-7
        else:
            assert abs(audit['boundary_flux_over_source_rate']-1)<1e-7
        assert audit['min_concentration_source_seconds']>=-1e-8
        audits.append(audit)
    times=np.arange(0,9001,30.)
    response=[]
    for t in times:
        retained,flux,out=modal.pulse_response(r,w,t,TAU)
        response.append({'time_s':t,'time_min':t/60,'production_rate_normalized':1. if t<TAU else 0.,
          'external_flux_normalized':flux,'cumulative_production_source_seconds':min(t,TAU),
          'cumulative_delivery_source_seconds':out,'retained_inventory_source_seconds':retained,
          'fixed_pulse_delivered_fraction':out/TAU,'retained_fraction_of_total_pulse':retained/TAU,
          'normalization':'total source rate=1 arbitrary amount/s; multiply amount columns by actual total source rate'})
    savecsv('delivery_response.csv',response)
    # Separate continuous-source deadline experiment from fixed-pulse late recovery.
    deadlines=[]
    for minutes in [5,10,15,30,60,120]:
        t=minutes*60; e=etaof(r,w,t)
        _,_,out=modal.pulse_response(r,w,t,TAU)
        deadlines.append({'deadline_min':minutes,'eta_source_maintained_until_deadline':e,
           'fixed_30min_pulse_fraction_recovered':out/TAU,
           'required_mean_secretion_per_IEQ_per_min_per_unit_B':1/(N*minutes*e),
           'source_capacity_multiplier_vs_instant_delivery':1/e,
           'modal_truncation_eta_bound':meta['eta_tail_bound_coefficient_s']/t})
    savecsv('deadline_summary.csv',deadlines)
    curve=[{'deadline_min':float(t/60),'eta_source_maintained_until_deadline':etaof(r,w,t)} for t in np.arange(30,7201,30.)]
    savecsv('continuous_deadline_curve.csv',curve)
    primary={'schema_version':'1.0','status':'supported' if interval[1]<.8 else ('refuted' if interval[0]>=.8 else 'unresolved'),
       'eta30_continuum_truncated':eta30,'eta30_finest_FV':fvfine,
       'estimated_numerical_uncertainty_eta':uncertainty,'estimated_interval_eta':interval,
       'interval_status':'estimated numerical enclosure, not formally certified proof',
       'modal_omitted_tail_bound_eta':tail,'FV_refinement_difference':fvgrid,
       'independent_method_difference':abs(fvfine-eta30),'quadrature_checks':qc,'field_audits':audits,
       'volume_ml':V*1e6,'effective_density_IEQ_per_ml':RHO,'nominal_60000_density_payload_IEQ':60000*V*1e6,
       'inventory_fraction_at_shutoff':1-eta30,'fraction_recovered_120min_after_shutoff':response[-1]['fixed_pulse_delivered_fraction'],
       'model_specification_sha256':hashlib.sha256((ROOT/'model_specification.json').read_bytes()).hexdigest()}
    primary_name='numerical_primary.json' if '--primary-only' in sys.argv else 'numerical_primary_verified.json'
    (EVID/primary_name).write_text(json.dumps(primary,indent=2)+'\n',encoding='utf-8')
    (EVID/'numerical_roots.json').write_text(json.dumps(meta['radial'],indent=2)+'\n',encoding='utf-8')
    if '--primary-only' in sys.argv:
        print(json.dumps(primary,indent=2),flush=True)
        return
    rref,wref,_=modal.combined(A,B,L,D,reflecting=True)
    boundaries=[{'scenario':'perfect_outer_and_end_sinks','permeability_m_per_s':'infinite','parameter_status':'favorable idealization','eta30':eta30},
      {'scenario':'perfect_outer_sink_reflecting_ends','permeability_m_per_s':'infinite','parameter_status':'hypothetical end obstruction','eta30':etaof(rref,wref,TAU)}]
    sensitivity_checks=[]
    for p in [1e-8,1e-7,1e-6]:
        rr,ww,_=fv.combined(A,B,L,D,160,560,permeability=p)
        rc,wc,_=fv.combined(A,B,L,D,320,1120,permeability=p)
        delta=etaof(rc,wc,TAU)-etaof(rr,ww,TAU)
        sensitivity_checks.append({'scenario':f'Robin_P_{p}','coarse_grid':'160x560','fine_grid':'320x1120','eta_difference':delta})
        assert abs(delta)<.002
        boundaries.append({'scenario':'Robin_outer_absorbing_ends','permeability_m_per_s':p,
            'parameter_status':'assumed sensitivity, not measured BEAM membrane permeability','eta30':etaof(rc,wc,TAU)})
    savecsv('boundary_sensitivity.csv',boundaries)
    diffs=[]
    for diff in spec['sensitivities']['D_values_m2_s']:
        diffs.append({'D_m2_per_s':diff,'eta30':etaof(r*diff/D,w,TAU),'status':'specified sensitivity; not measured'})
    assert all(diffs[i+1]['eta30']>diffs[i]['eta30'] for i in range(len(diffs)-1))
    critical=brentq(lambda ratio:etaof(r*ratio,w,TAU)-.8,1,10,xtol=1e-11)*D
    savecsv('diffusivity_sensitivity.csv',diffs)
    placements=[]
    ieq_volume_ml=4*np.pi*(.075**3)/3/1000 # 150 micrometre reference sphere
    for label,width in [('uniform',None),('outer_half_thickness',(B-A)/2),('outer_quarter_thickness',(B-A)/4),('outer_0.10mm',.0001)]:
        rr,ww,_=fv.combined(A,B,L,D,320,1120,source_outer_width=width)
        rc,wc,_=fv.combined(A,B,L,D,160,560,source_outer_width=width)
        delta=etaof(rr,ww,TAU)-etaof(rc,wc,TAU)
        sensitivity_checks.append({'scenario':label,'coarse_grid':'160x560','fine_grid':'320x1120','eta_difference':delta})
        assert abs(delta)<.002
        ratio=1 if width is None else (B*B-A*A)/(B*B-(B-width)**2)
        placements.append({'source':label,'occupied_shell_width_mm':(B-A if width is None else width)*1000,
          'eta30':etaof(rr,ww,TAU),'density_multiplier_for_same_dose':ratio,'local_density_IEQ_per_ml':RHO*ratio,
          'ideal_IEQ_reference_volume_fraction':RHO*ratio*ieq_volume_ml,
          'payload_IEQ':N,'physical_status':'hypothetical continuous source; packing and oxygen feasibility not established'})
    savecsv('placement_sensitivity.csv',placements)
    savecsv('sensitivity_verification.csv',sensitivity_checks)
    frontier=[]
    for h_mm in np.round(np.arange(.10,1.001,.01),2):
        h=h_mm/1000; a=B-h
        total=V/(np.pi*(B*B-a*a))
        n=int(np.ceil(total/L-1e-10)); rem=total-(n-1)*L
        lengths=[L]*(n-1)+[rem]
        e={t:0. for t in [15,30,60]}; eb={t:0. for t in [15,30,60]}
        er,wr,mr=modal.annular_modes(a,B,128)
        for length in sorted(set(lengths)):
            weight=length*lengths.count(length)/total
            ez,wz,mz=modal.axial_modes(length,256)
            rr=D*(er[:,None]+ez[None,:]); ww=wr[:,None]*wz[None,:]
            bound_s=max(0,1-wr.sum())/(D*(mr['next_eigenvalue_per_m2']+ez[0]))+max(0,1-wz.sum())/(D*(mz['next_eigenvalue_per_m2']+er[0]))
            for t in e:
                e[t]+=weight*etaof(rr.ravel(),ww.ravel(),t*60)
                eb[t]+=weight*bound_s/(t*60)
        area=2*np.pi*B*total; endarea=n*2*np.pi*(B*B-a*a)
        row={'thickness_mm':h_mm,'inner_radius_mm':a*1000,'payload_IEQ':N,'density_IEQ_per_ml':RHO,
             'cell_compartment_volume_ml':V*1e6,'total_length_mm':total*1000,'pouch_count':n,
             'full_70mm_pouches':n-1 if rem<L-1e-10 else n,'last_segment_length_mm':rem*1000,
             'side_exchange_area_cm2':area*1e4,'annular_end_exchange_area_cm2':endarea*1e4,
             'side_area_ratio_to_nominal':total/(7*L),'parallel_width_mm':(n*2*B+(n-1)*.001)*1000,
             'bounding_footprint_cm2':max(lengths)*(n*2*B+(n-1)*.001)*1e4,
             'eta15':e[15],'eta30':e[30],'eta60':e[60],
             'eta15_truncation_lower':e[15]-eb[15],'eta30_truncation_lower':e[30]-eb[30],'eta60_truncation_lower':e[60]-eb[60],
             'assumptions':'same D/uniform source/perfect sinks; minimum pouch count; generator and connectors excluded'}
        assert abs(RHO*row['cell_compartment_volume_ml']-N)<1e-6
        assert 0<rem<=L+1e-10
        frontier.append(row)
    savecsv('dose_area_frontier.csv',frontier)
    targets=[]
    for t in [15,30,60]:
        for target in [.5,.6,.7,.8,.9]:
            feasible=[row for row in frontier if row[f'eta{t}_truncation_lower']>=target]
            selected=min(feasible,key=lambda row:row['side_exchange_area_cm2']) if feasible else None
            targets.append({'deadline_min':t,'target_eta':target,'status':'grid minimum area' if selected else 'not attained in grid',
              'thickness_mm':selected['thickness_mm'] if selected else '',
              'side_exchange_area_cm2':selected['side_exchange_area_cm2'] if selected else '',
              'area_ratio_to_nominal':selected['side_area_ratio_to_nominal'] if selected else '',
              'pouch_count':selected['pouch_count'] if selected else '',
              'last_segment_length_mm':selected['last_segment_length_mm'] if selected else '',
              'eta_achieved':selected[f'eta{t}'] if selected else ''})
    savecsv('frontier_targets.csv',targets)
    # Check selected grid points and their thicker (lower-area) neighbors at
    # higher truncations. Also quantify the worst analytic omitted-tail bound
    # throughout the original frontier grid, including each short end segment.
    check_h=set([.1,.75,1.])
    for row in targets:
        if row['thickness_mm']!='':
            check_h.add(float(row['thickness_mm']))
            if row['thickness_mm']<1:check_h.add(round(row['thickness_mm']+.01,2))
    frontcheck=[]; max_front_tail=0.
    for row in frontier:
        h=row['thickness_mm']/1000; n=row['pouch_count']; total=row['total_length_mm']/1000
        lengths=[L]*(n-1)+[row['last_segment_length_mm']/1000]
        bound=0.
        for length in sorted(set(lengths)):
            _,_,mm=modal.combined(B-h,B,length,D,128,256)
            bound+=length*lengths.count(length)/total*mm['eta_tail_bound_coefficient_s']/(15*60)
        max_front_tail=max(max_front_tail,bound)
        if row['thickness_mm'] in check_h:
            for nr,nz in [(256,512),(512,1024)]:
                vals={t:0. for t in [15,30,60]}
                for length in sorted(set(lengths)):
                    rr,ww,_=modal.combined(B-h,B,length,D,nr,nz)
                    for t in vals:vals[t]+=length*lengths.count(length)/total*etaof(rr,ww,t*60)
                for t in vals:
                    frontcheck.append({'thickness_mm':row['thickness_mm'],'deadline_min':t,
                      'radial_modes':nr,'axial_modes':nz,'eta_refined':vals[t],
                      'eta_original':row[f'eta{t}'],'difference':vals[t]-row[f'eta{t}']})
    savecsv('frontier_verification.csv',frontcheck)
    max_front_diff=max(abs(x['difference']) for x in frontcheck)
    assert max_front_tail<.002 and max_front_diff<.002
    for target in targets:
        if target['thickness_mm']=='':continue
        h=target['thickness_mm'];t=target['deadline_min']
        exact=[x for x in frontcheck if x['thickness_mm']==h and x['deadline_min']==t and x['radial_modes']==512][0]
        assert exact['eta_refined']>=target['target_eta']
        # All strictly lower-area grid designs must fail, without assuming
        # monotonicity across segment-count changes.
        competitors=[row for row in frontier if row['side_exchange_area_cm2']<target['side_exchange_area_cm2']-1e-10]
        assert all(row[f'eta{t}']<target['target_eta'] for row in competitors)
        if h<1:
            worse=[x for x in frontcheck if x['thickness_mm']==round(h+.01,2) and x['deadline_min']==t and x['radial_modes']==512][0]
            assert worse['eta_refined']<target['target_eta']
    # Original figures; every quantity is dimensioned or explicitly normalized.
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    fig,axs=plt.subplots(1,2,figsize=(10,3.8))
    tm=np.array([x['time_min'] for x in response]); production=np.array([x['production_rate_normalized'] for x in response])
    axs[0].step(tm,production,where='post',label='Incremental production',color='#808080')
    axs[0].plot(tm,[x['external_flux_normalized'] for x in response],label='External delivery',color='#126782')
    axs[0].set(xlabel='Time (min)',ylabel='Rate / production pulse rate',xlim=(0,150));axs[0].legend(frameon=False)
    axs[1].plot(tm,[x['fixed_pulse_delivered_fraction'] for x in response],label='Delivered',color='#126782')
    axs[1].plot(tm,[x['retained_fraction_of_total_pulse'] for x in response],label='Retained',color='#d58033')
    axs[1].plot(tm,np.minimum(tm,30)/30,':',label='Produced',color='#808080')
    axs[1].set(xlabel='Time (min)',ylabel='Fraction of total 30-min pulse',xlim=(0,150));axs[1].legend(frameon=False)
    fig.tight_layout();fig.savefig(FIG/'production_delivery.png');fig.savefig(FIG/'production_delivery.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.7,4))
    ax.plot([x['deadline_min'] for x in curve],[x['eta_source_maintained_until_deadline'] for x in curve],color='#126782')
    ax.scatter([x['deadline_min'] for x in deadlines],[x['eta_source_maintained_until_deadline'] for x in deadlines],color='#126782')
    ax.axhline(.8,color='#d58033',ls='--',label='Prespecified engineering benchmark')
    ax.set(xlabel='Deadline and source duration (min)',ylabel='Fraction delivered by deadline',xlim=(0,120),ylim=(0,1))
    ax.legend(frameon=False,loc='lower right');fig.tight_layout();fig.savefig(FIG/'deadline_delivery.png');fig.savefig(FIG/'deadline_delivery.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.7,4))
    for t,col in [(15,'#a64d79'),(30,'#126782'),(60,'#438a5e')]:
        ax.plot([x['side_exchange_area_cm2'] for x in frontier],[x[f'eta{t}'] for x in frontier],label=f'{t} min',color=col)
    ax.scatter([2*np.pi*B*7*L*1e4],[eta30],marker='*',s=110,color='black',label='Nominal, 30 min',zorder=5)
    ax.set(xlabel='Total lateral exchange area (cm$^2$)',ylabel='Fraction delivered by deadline',ylim=(0,1))
    ax.legend(frameon=False);fig.tight_layout();fig.savefig(FIG/'dose_area_frontier.png');fig.savefig(FIG/'dose_area_frontier.pdf');plt.close(fig)
    report={'schema_version':'1.0','status':'supported' if interval[1]<.8 else ('refuted' if interval[0]>=.8 else 'unresolved'),
      'eta30_continuum_truncated':eta30,'eta30_finest_FV':fvfine,'estimated_numerical_uncertainty_eta':uncertainty,
      'estimated_interval_eta':interval,'interval_status':'numerical estimate, not a formally certified enclosure',
      'modal_omitted_tail_bound_eta':tail,'FV_refinement_difference':fvgrid,'independent_method_difference':abs(fvfine-eta30),
      'volume_ml':V*1e6,'effective_density_IEQ_per_ml':RHO,'nominal_60000_density_payload_IEQ':60000*V*1e6,
      'side_area_cm2':2*np.pi*B*7*L*1e4,'critical_D_m2_per_s_for_eta30_0_80':critical,
      'reflecting_ends_eta30':etaof(rref,wref,TAU),'inventory_fraction_at_shutoff':1-eta30,
      'fraction_recovered_120min_after_shutoff':response[-1]['fixed_pulse_delivered_fraction'],
      'source_rate_capacity_multiplier_at_30min':1/eta30,'quadrature_checks':qc,'field_audits':audits,
      'root_bracketing':'pi/8 dimensionless steps, all sign changes retained in ascending order; Brent xtol 1e-12',
      'max_root_residual':meta['radial']['max_root_residual'],'minimum_radial_modal_weight':meta['radial']['min_weight'],
      'radial_modal_weight_sum':meta['radial']['weight_sum'],'axial_modal_weight_sum':meta['axial']['weight_sum'],
      'frontier_max_omitted_tail_eta_bound':max_front_tail,'frontier_max_refinement_eta_difference':max_front_diff,
      'frontier_threshold_neighbors':'All selected points and next thicker grid neighbors confirmed at 512 radial and 1024 axial modes; lower truncation bounds govern initial selection',
      'frontier_global_grid_minimum_check':'Every strictly lower-area grid competitor has an upper truncated eta below its target; no monotonicity assumption used',
      'sensitivity_max_grid_eta_difference':max(abs(x['eta_difference']) for x in sensitivity_checks),
      'environment':{'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,'platform':platform.platform()},
      'model_specification_sha256':hashlib.sha256((ROOT/'model_specification.json').read_bytes()).hexdigest(),
      'checks':'All numerical assertions passed; no experimental or clinical validation implied'}
    (EVID/'numerical_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (EVID/'numerical_roots.json').write_text(json.dumps(meta['radial'],indent=2)+'\n',encoding='utf-8')
    (EVID/'numerical_summary.txt').write_text(json.dumps({k:v for k,v in report.items() if k not in ['field_audits','quadrature_checks']},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','eta30_continuum_truncated','estimated_numerical_uncertainty_eta','critical_D_m2_per_s_for_eta30_0_80']},indent=2),flush=True)


if __name__=='__main__':run()
