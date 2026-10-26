"""Scenario choices and the conditional thickness restriction,from accepted tables."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
def rows(name):return list(csv.DictReader((R/'data'/name).open(encoding='utf8')))
def build():
    plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False})
    frontier=rows('robustness_frontier.csv');targets=rows('robustness_targets.csv')
    fig,axs=plt.subplots(1,2,figsize=(10.4,4.9))
    sets=[('nominal_favorable','F','#126782'),('near_nominal_discrete','S8','#d58033'),('broad_discrete','S24','#a64d79')]
    for name,label,color in sets:
        rr=[r for r in frontier if r['scenario_set']==name and int(r['deadline_min'])==30]
        axs[0].plot([float(r['lateral_area_cm2']) for r in rr],[100*float(r['minimum_eta']) for r in rr],color=color,label=label)
        r=next(r for r in targets if r['scenario_set']==name and int(r['deadline_min'])==30 and float(r['target_eta'])==.8)
        x=float(r['lateral_area_cm2']);y=100*float(r['minimum_eta']);h=float(r['thickness_mm'])
        axs[0].scatter(x,y,color=color,zorder=4,s=30)
        dx,dy={'F':(-35,10),'S8':(15,-13),'S24':(-85,-25)}[label]
        axs[0].annotate(f'{label}: {h:.2f} mm\n{x:.2f} cm²',(x,y),xytext=(x+dx,y+dy),fontsize=10.5,arrowprops={'arrowstyle':'-','color':color})
    axs[0].axhline(80,color='#777',ls='--',lw=1);axs[0].set(xlim=(90,450),ylim=(25,100),xlabel='Lateral area (cm²)',ylabel='Worst-scenario delivery (%)',title='A  Selected 80% designs at 30 min')
    # Aggregate all remaining thicknesses; do not presume monotonic transport.
    # The table preserves the interval and maximizer audit; the curve shows its point value.
    maxima=rows('design_constraints_maxima.csv')
    full=[r for r in maxima if r['scenario_set']=='broad_discrete']
    axs[1].step([float(r['h_min_mm']) for r in full],[100*float(r['maximum_worst_eta']) for r in full],color='#a64d79',lw=1.8,where='pre')
    for h in [.25,.30]:
        r=next(r for r in full if abs(float(r['h_min_mm'])-h)<1e-9);y=100*float(r['maximum_worst_eta'])
        axs[1].scatter(h,y,color='#a64d79',zorder=4,s=30)
        axs[1].annotate(f'{h:.2f} mm: {y:.2f}%',(h,y),xytext=(h-.08,y-13),fontsize=10.5,arrowprops={'arrowstyle':'-','color':'#a64d79'})
    for y in [80,90]:
        axs[1].axhline(y,color='#999',ls='--',lw=1);axs[1].text(.395,y+1,f'{y}%',ha='right',fontsize=10)
    axs[1].set(xlim=(.10,.40),ylim=(45,100),xlabel='Hypothetical minimum thickness (mm)',ylabel='Maximum worst-scenario delivery (%)',title='B  Remaining-grid maximum, S24')
    fig.subplots_adjust(left=.075,right=.985,wspace=.30,top=.91,bottom=.29)
    fig.text(.075,.145,r'F: $D=3$, $P=\infty$, absorbing ends.  S8: $D\in\{2.85,3\}$, $P\in\{10^{-5},\infty\}$, either end condition.',fontsize=10.5)
    fig.text(.075,.085,r'S24: $D\in\{1,2,2.85,3\}$, $P\in\{10^{-6},10^{-5},\infty\}$, either end condition.  $D$ in $10^{-10}$ m²/s; $P$ in m/s.',fontsize=10.5)
    fig.text(.075,.025,'All sources uniform and maintained to 30 min; fixed dose and density. Minimum thickness is unassigned physically.',fontsize=10.5)
    for suffix in ['png','pdf']:fig.savefig(R/'figures'/f'design_constraints.{suffix}',dpi=200,bbox_inches='tight')
    plt.close(fig)
if __name__=='__main__':build()
