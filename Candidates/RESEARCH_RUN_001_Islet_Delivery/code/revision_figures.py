"""Original geometry schematic and explanatory plots; all inputs are local tables."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Rectangle,FancyArrowPatch
R=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False})
def rows(name):return list(csv.DictReader((R/'data'/name).open()))
def save(fig,name):
    fig.savefig(R/'figures'/f'{name}.png',dpi=200,bbox_inches='tight')
    fig.savefig(R/'figures'/f'{name}.pdf',bbox_inches='tight');plt.close(fig)
def build():
    fig,axs=plt.subplots(1,3,figsize=(10.6,3.2),gridspec_kw={'width_ratios':[1,1.15,1.25]})
    ax=axs[0];ax.set_aspect('equal');ax.axis('off')
    ax.add_patch(Circle((0,0),1,color='#cbe7dd',ec='#147d69',lw=2))
    ax.add_patch(Circle((0,0),.8,color='white',ec='#525c69',lw=2,ls='--'))
    ax.plot([0,.8],[0,0],color='#525c69');ax.text(.3,.04,'a',fontsize=13)
    ax.annotate('',xy=(0,1),xytext=(0,0),arrowprops={'arrowstyle':'->','color':'#147d69'})
    ax.text(.06,.45,'b',fontsize=13);ax.text(-1.45,-1.42,'Uniform production in shaded annulus\nInner wall: reflecting (dashed)',fontsize=11)
    ax.text(-1.45,1.35,'A  Cross-section',weight='bold');ax.set(xlim=(-1.5,1.5),ylim=(-1.6,1.6))
    ax=axs[1];ax.axis('off');ax.set(xlim=(-.4,4.3),ylim=(-.8,2.4))
    for y in [.25,1.25]:
        ax.add_patch(Rectangle((0,y),3.8,.35,color='#cbe7dd',ec='#147d69',lw=2))
    ax.plot([0,3.8],[.6,.6],ls='--',color='#525c69',lw=2);ax.plot([0,3.8],[1.25,1.25],ls='--',color='#525c69',lw=2)
    ax.annotate('',xy=(3.8,-.04),xytext=(0,-.04),arrowprops={'arrowstyle':'<->'});ax.text(1.5,-.29,'L = 70 mm',fontsize=11)
    ax.text(-.3,2.15,'B  Axial slice',weight='bold')
    ax.text(-.3,1.85,'h = b − a = 0.75 mm',fontsize=11)
    ax.text(-.3,-.66,'Outer surface: absorbing or Robin\nEnd faces: absorbing or reflecting',fontsize=11)
    ax=axs[2];ax.axis('off');ax.set(xlim=(0,5),ylim=(-.8,2.4))
    ax.text(0,2.15,'C  Fixed-dose segmentation',weight='bold')
    for j,length in enumerate([3.8,3.8,2.1]):
        ax.add_patch(Rectangle((.05,1.45-j*.5),length,.22,color='#cbe7dd',ec='#147d69'))
    ax.text(4,1.5,'70 mm',fontsize=11);ax.text(4,1,'70 mm',fontsize=11);ax.text(2.3,.5,'remainder',fontsize=11)
    ax.text(0,-.1,'Illustrative segments; count changes with h.\nTotal volume and dose are preserved.',fontsize=11)
    ax.text(0,-.65,'Schematic, not CAD; aspect ratios altered.',fontsize=11)
    fig.tight_layout(w_pad=1.2);save(fig,'geometry_schematic')
    rr=rows('delivery_response.csv');t=np.array([float(r['time_min']) for r in rr])
    flux=np.array([float(r['external_flux_normalized']) for r in rr]);deliv=np.array([float(r['fixed_pulse_delivered_fraction']) for r in rr]);ret=np.array([float(r['retained_fraction_of_total_pulse']) for r in rr])
    fig,axs=plt.subplots(1,2,figsize=(10.3,3.8))
    axs[0].plot(t,flux,color='#126782',label='Boundary output')
    axs[0].plot([0,30,30,60],[1,1,0,0],color='#bc6c25',ls='--',label='Production')
    axs[0].set(xlim=(0,60),ylim=(0,1.08),xlabel='Time (min)',ylabel='Rate / production rate',title='A  Early response');axs[0].legend(frameon=False,loc='lower right')
    axs[1].plot(t,deliv,label='Delivered',color='#126782');axs[1].plot(t,ret,label='Retained',color='#bc6c25');axs[1].plot(t,np.minimum(t/30,1),ls=':',color='#666',label='Produced')
    axs[1].set(xlim=(0,150),ylim=(0,1.08),xlabel='Time (min)',ylabel='Amount / total pulse production',title='B  Full recovery');axs[1].legend(frameon=False,loc='center right')
    for ax in axs:ax.axvline(30,color='#777',ls=':',lw=1);ax.text(31,.04,'Shutoff',rotation=90,color='#555',fontsize=11)
    fig.tight_layout();save(fig,'production_delivery')
    rr=rows('dose_area_frontier.csv');area=np.array([float(r['side_exchange_area_cm2']) for r in rr])
    fig,axs=plt.subplots(1,2,figsize=(10.3,3.9))
    for ax in axs:
        for t,color in [(15,'#bc6c25'),(30,'#126782'),(60,'#609d6e')]:ax.plot(area,[float(r[f'eta{t}']) for r in rr],color=color,label=f'{t} min')
        for target in [.8,.9]:ax.axhline(target,color='#aaa',ls='--',lw=.8)
        ax.set(xlabel='Lateral area (cm²)',ylabel='Deadline delivery fraction')
    axs[0].set(title='A  Full tested grid',ylim=(.25,1));axs[0].legend(frameon=False,loc='lower right')
    axs[1].set(title='B  Nominal and benchmark choices',xlim=(90,220),ylim=(.55,.98))
    for h,label,offset in [(.75,'Nominal',(4,-.05)),(.6,'80% choice',(4,-.05)),(.41,'90% choice',(-43,.035))]:
        r=next(r for r in rr if abs(float(r['thickness_mm'])-h)<1e-8);x=float(r['side_exchange_area_cm2']);y=float(r['eta30']);axs[1].scatter(x,y,color='#126782',s=25,zorder=4);axs[1].annotate(label,(x,y),xytext=(x+offset[0],y+offset[1]),fontsize=11,arrowprops={'arrowstyle':'-','color':'#777'})
    axs[1].text(217,.805,'80%',ha='right',fontsize=11);axs[1].text(217,.905,'90%',ha='right',fontsize=11)
    fig.tight_layout();save(fig,'dose_area_frontier')
if __name__=='__main__':build()
