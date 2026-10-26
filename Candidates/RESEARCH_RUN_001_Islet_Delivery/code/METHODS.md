# Reproducible transport method

## Defined object and normalization

The cell compartment is the annular cylinder a <= r <= b, 0 <= z <= L,
with a=0.003 m, b=0.00375 m and L=0.070 m. Seven identical pouches have
volume 7.7931132763 mL. The 420,000 IEQ normalization therefore corresponds
to 53,893.7373 IEQ/mL; using the separate nominal 60,000 IEQ/mL gives
467,586.7966 IEQ. Source amplitude cancels from all reported fractions.
These are volumes of the idealized straight annuli, not measurements of actual
fill volume or cell positions.

The incremental concentration obeys dc/dt = D Laplacian(c) + s,
with c initially zero, no flux at r=a, and c=0 at r=b, z=0 and z=L.
The primary source s is uniform and constant for 0<t<=1800 s. We normalize
the total production rate across the seven pouches to one arbitrary amount/s.
Inventory and cumulative delivery consequently have units of source-seconds;
multiplication by any stated intrinsic total source rate gives amounts in that
source rate's units. They are not insulin doses inferred from experimental data.

Two different deadline quantities must remain separate. The fixed-pulse recovery
is M_out(t)/1800 for the 30-minute source, including t>1800. The continuous-source
deadline fraction eta(T) is M_out(T)/T for a source maintained until each T.
Only at T=1800 do they describe the same experiment and normalization.

## Independent continuum solution

Let u solve source-free diffusion from initial concentration one. Its volume
average S(t) is the survival probability of a uniformly released molecule before
exit. For a unit total constant source, inventory is J(t)=integral_0^t S(v)dv,
delivery is t-J(t), and external flux is 1-S(t). After shutoff at tau,
inventory is J(t)-J(t-tau), delivery is tau-inventory and flux is
S(t-tau)-S(t). This also accounts for every retained molecule.

The separated radial eigenfunctions are

f_n(r) = J_0(k_n r)Y_1(k_n a) - Y_0(k_n r)J_1(k_n a).

They satisfy f'_n(a)=0; positive k_n are the successive roots f_n(b)=0.
With q=k(b-a), roots are scanned at intervals pi/8, bracketed by sign changes,
then refined with Brent's method (absolute tolerance 1e-12 in q, relative
tolerance 1e-14). The retained roots and brackets are saved in the evidence.
The weight w_n is (integral_a^b r f_n dr)^2 divided by
[(b^2-a^2)/2 * integral_a^b r f_n^2 dr]. It is nonnegative.
Integrals and norms use analytic Bessel antiderivatives. Gauss-Legendre orders
512 and 1024 independently check the weights at 128 radial modes.

The axial survival modes are odd m=1,3,5,..., with eigenvalues (m*pi/L)^2
and weights 8/(m^2*pi^2). Thus

S(t) = sum_n sum_m w_n v_m exp[-D(k_n^2 + (m*pi/L)^2)t].

The integrated survival is evaluated using -expm1(-lambda*t)/lambda to avoid
small-argument cancellation. The primary result retains 128 radial and 256 odd
axial modes. Root/weight tests and 32/64/128 radial and 64/128/256 axial
convergence are reported. For reflecting ends only the zero axial mode remains.

Uniform initial density gives nonnegative modal weights whose complete sum is
one. The discarded contribution to J(T)/T is at most

[(1-sum w)/(D(k_next^2+mu_1)) +
 (1-sum v)/(D(mu_next+k_1^2))] / T.

This union bound allows harmless double counting where both indices are omitted.
It uses exp(-lambda*t)<=1 and its integrated bound 1/lambda. Consequently,
finite positive-mode truncation overestimates eta; the truncation interval is
[eta_truncated-tail_bound, eta_truncated] before floating-point errors.
Analytic identities and numerical roots do not constitute interval arithmetic.
The reported overall uncertainty is an estimate, not a formally certified proof.

## Conservative axisymmetric finite volume

The second path constructs a cylindrical finite-volume operator without using
Bessel functions or continuum eigenvalues. Each radial cell has mass coefficient
(r_right^2-r_left^2)/2. Neighbor conductance is D*r_face/dr. The outer absorbing
face has conductance D*b/(dr/2); the inner face has zero conductance. Axial cell
mass is dz, interior conductance D/dz and end conductances D/(dz/2). Factors 2*pi
cancel in normalized quantities. The tensor sum of these operators is the full
axisymmetric 2-D conservative finite-volume grid.

Mass weighting transforms each discrete operator into a symmetric tridiagonal
matrix. Its numerical eigendecomposition evaluates the matrix exponential and
the source integral exactly in time up to floating-point error. There is no time
step whose convergence is being assumed. Space is refined from 40x140 through
80x280 and 160x560 to 320x1120 radial/axial cells. Positive eigenvalues and source
projection determine the independent discrete survival response.

As a check beyond defining delivered mass as produced minus inventory, the code
reconstructs the 2-D concentration field and independently sums boundary face
conductances times concentrations. That boundary flux must match the temporal
inventory derivative; the steady-source boundary flux must equal total source.
The face-flux functional is also integrated over time mode by mode using its
own face projections, without defining delivered amount as production minus
inventory. Its sum with the reconstructed inventory must equal production.
Fields are checked for nonnegativity at 5, 30, 60 and 150 minutes. Boundary-flux
agreement is required below 1e-7 of source rate. The finite-volume semigroup's
Metzler generator supplies the positivity structure; these sampled field checks
detect implementation errors rather than proving a universal floating-point
positivity guarantee.

The overall eta uncertainty estimate is the maximum of the finest FV/modal
difference, the last FV refinement difference, the modal omitted tail plus
quadrature-weight discrepancy, and 1e-8. The two methods must agree within .005;
estimated uncertainty must be below .002. The original deterministic benchmark
is classified below .80 only if the entire estimated interval is below .80;
otherwise it is at/above or numerically unresolved. This is not statistical testing. Numerical verification is not experimental validation.

## Conditional ordering for the original benchmark

For this fixed linear passive geometry, D multiplies the entire generator.
Each molecule's first-exit time scales as 1/D. Equivalently each uniform-mode
inventory factor g(x)=(1-exp(-x))/x decreases with x>0 because
g'(x)=[exp(-x)(1+x)-1]/x^2<0. Therefore eta(T) increases with D. The D scan
checks the implementation; the scaling argument establishes the monotonicity
for the specified model. It does not apply automatically to arbitrary
reaction-transport systems.

Perfect absorption removes delay at the designated surfaces. Replacing it with
partial absorption or reflecting end caps can only postpone exit for the same
source and passive domain. Ideal oxygen, immediate production, zero binding and
degradation, and the declared diffusivity cap make the test favorable within its
scope. A different source position, stored initial inventory, secretion waveform,
convection or architecture is a different problem. The result is not a bound over
all feasible implants. The 3e-10 m^2/s cap is an assumption, not a measured BEAM
value or a universal maximum.

## Sensitivity and dose-preserving geometry

Robin sensitivities impose -D dc/dn = P c on the outer face, keeping the favorable
absorbing ends. The FV boundary conductance is b/[dr/(2D)+1/P]. P values 1e-8,
1e-7 and 1e-6 m/s are hypothetical, not fitted membrane properties. Reflecting
ends and the stated D range are separate sensitivities; a scalar root solve
finds D needed for eta30=.80 without reinterpreting that D as source-supported.

Source-localization sensitivities keep the full annular transport domain and
the same total IEQ/source amplitude but place production in outer shells.
Cells intersecting a shell boundary receive exact radial volume fractions.
The resulting local density multiplier and ideal volume fraction based on the
150-micrometre IEQ reference sphere are reported. These continuous-source tests
do not prove that the placement, packing, oxygenation or containment is realizable.

For the frozen redesign grid h=.10,.11,...,1.00 mm at b=3.75 mm, preserve both
420,000 IEQ and the reconciled density. Thus active volume remains constant and
total length is V/[pi(b^2-(b-h)^2)]. Use the minimum number of pouches of at most
70 mm: full 70-mm pouches and one positive remainder. Compute each actual
segment's end effects and take a volume-weighted mean. This prevents arbitrary
subdivision from creating unaccounted absorbing ends. Truncation convergence and
threshold-neighbor checks determine adequate modal counts; the nominal
high-resolution comparison is retained.

Lateral exchange area is 2*pi*b*total_length. Absorbing annular end area is
reported separately. The bounding parallel arrangement has width
n*2b+(n-1)*1 mm and length equal to the longest segment; it excludes connectors,
manifolds, generator and implantation clearances. Target tables select the
least-area sampled design reaching each eta target at 15, 30 and 60 minutes.
They are grid-limited engineering requirements, not clinically validated choices.

Selection uses the lower endpoint after the positive omitted-mode tail bound,
not just the point estimate. The final grid uses 128 radial and 256 axial modes;
selected points and next thicker neighbors are checked at 256/512 and 512/1024.
An initial 64/128 selection at h=.42 mm, T=15 min crossed .80 on refinement
(0.80000854 became 0.79999649). The run rejected that selection and raised the
required area to the next passing grid design. The retained correction record
documents this numerical threshold issue; it does not affect primary H1.

For a symbolic incremental amount B required by T, intrinsic mean secretion per
IEQ must be at least B/[N*T*eta(T)]. No clinical B or intrinsic secretion rate
is inferred from hour-long external assay measurements. Oxygen demand remains
that of the unchanged cell payload and requires a separate source-qualified
oxygen budget, even if transport improves.


## Revision2: source-history response

The central object is S(t), the surviving fraction from a uniform unit initial
inventory under a fixed linear operator. With q(u) the total intrinsic generation
rate and zero incremental initial inventory,

M_out(T) = integral_0^T q(u) [1 - S(T-u)] du.

A uniform initial amount M0 adds M0[1-S(T)] separately. Sustained-source eta(T)
and fixed-pulse R_tau(t) retain the different denominators described above.
The initial-inventory illustration and constant30minute source may have equal
total amount, but the ideal instantaneous input has no finite peak-rate bound.
Neither a new cellular waveform nor stored insulin has been measured here.
At nominal h=.75mm,D=3e-10m²/s,h²/D=31.25minutes and DT/h²=.96 at30minutes.

## Revision2: independently checked Robin continuum extension

The frozen robustness_specification.json is a separate, hash-checked extension;
the original model specification remains unchanged. For finite P, the outer
condition is -D f'(b)=P f(b). The same inner-Neumann Bessel basis has roots
D*k*f1(b)=P*f0(b), with f1=-f0'/k. Its norm is
[b²(f0(b)²+f1(b)²)-a² f0(a)²]/2. Dropping f0(b)² would be wrong for Robin
boundaries. Analytic integrals generate nonnegative uniform weights;1024-point
quadrature independently checks representative cases. Roots are bracketed in
q=k*h steps pi/16 and refined to1e-12 absolute tolerance.

Each Robin survival mode decays at D(k²+mu). The positive omitted-survival tail
uses the next omitted radial/axial rates as in the original method. The retained
eta is an upper approximation; subtracting that tail and1e-7 floating guard gives
the classification lower estimate. Adding the guard gives the upper estimate.
These are numerical estimates, not interval-arithmetic certified enclosures.
The map uses128/256 modes, threshold refinement uses256/512 and512/1024.
Finite-volume checks use independent Robin conductance b/[dr/(2D)+1/P], with
160/560 and320/1120 grids. Seventy representative,selected-worst and adjacent
scenarios are checked at three deadlines. Additional internal A-review FV400/1400
calculations, including direct face-flux mass closure, are retained privately.

All24 Cartesian D/P/end scenarios are evaluated at91thicknesses and3deadlines.
The eight-case subset and24-case full set are assumptions, not measured ranges.
Selection requires every scenario lower estimate to meet the target and every
lower-area competitor to have at least one scenario upper estimate below target.
All45decisions resolve:44selected designs and one unattained broad15minute90%
target. Eight selected cases are already at the thickest tested layer; the grid
must be extended before asserting an unconstrained minimum. Sub150µm thicknesses
are flagged as unvalidated continuous-source idealizations.

At fixed finite P, P/D changes with D, so the perfect-sink clock proof is not
reused. No monotonicity is assumed for selection, no probability is assigned,
and no continuous parameter-box guarantee follows from the finite map.
Every geometry preserves N,rho,b and actual maximum70mm segmentation. Density
is converted fromIEQ/mL toIEQ/m³ before use with metre-based geometry. Footprint
is the active single-row bounding rectangle at1mm spacing; it excludes system
overhead. See data/robustness_*.csv and evidence/robustness_verification.json.

Numerical accuracy, physical parameter uncertainty and structural discrepancy
remain distinct. The proposed discrimination/calibration/held-out-geometry plan
is in evidence/proposed_validation.md; it describes work not performed here.


## Revision3: minimum-thickness constraints and mechanism comparison

This extension postprocesses the verified raw map; it does not solve a new PDE.
The supplied specification and all four reference inputs are hash-checked before calculation. A separate regeneration route, described below, compares derived numerical data against those unchanged reference inputs.
The three inherited scenario sets,420,000IEQ,density,outer radius,source history,
finite segmentation and numerical estimates are unchanged.

For a declared set S,let e(h)=min_s eta_s(h),l(h)=min_s lower_s(h),
and u(h)=min_s upper_s(h). A hypothetical minimum h_min restricts the original
grid G to H={h in G:h>=h_min}. Integer hundredths of a millimetre avoid threshold
roundoff in this membership test. Enumerate every eligible thickness; no transport
monotonicity across segmentation changes is assumed. Report E=max_H e(h),with
estimated numerical interval[max_H l(h),max_H u(h)]. The point maximizer and
any competitor whose upper overlaps its lower are retained in the table.

For target theta,a selected design must have l(h)>=theta,and every lower-area
eligible competitor must have u(h)<theta. If max_H u(h)<theta,the target is
not attained on the constrained grid. Otherwise any obstruction to selection
is unresolved; point rounding is never used as a substitute. Since H shrinks
as h_min rises,the maximum estimates cannot increase. This structural check
holds regardless of response monotonicity in thickness.

At30minutes,all91h_min values from0.10to1.00mm are applied to all3sets,with
80% and90% targets:273maxima and546classifications. There are169selections,
377not-attained cases and no unresolved classifications. All source-frontier
reconstructions match exactly. The specification does not assign a biological
or manufacturing h_min;150micrometres is an IEQ volume-reference diameter,
not a universal lower bound on permissible layers. Satisfying h_min is not
sufficient for physical realizability. Not-attained means this sampled family,
not all possible architectures or a continuous global optimization.

Five single-scenario80%/30minute grids are separately reoptimized: favorable,
lowerDonly,finitePonly,reflectingendsonly,and allthree. Each uses the same
lower/upper selection rule and every lower-area competitor. Their area changes
are nonadditive,conditional comparisons; they are not causal contribution shares.
Fo=D*T/h² and Bi=P*h/D use h in metres and T=1800s. Both are reported at each
selected thickness and at the nominal0.75mm. P=infinite is recorded explicitly,
not as a finite proxy or JSON infinity. Aspect/curvature ratios remain relevant.

The independent postprocessing audit uses rawCSV and a separate implementation;
no new transport validation is implied. The 8,936 constrained lower-area
exclusions and all infeasibility exclusions are retained in the audit record.
`python code/design_constraints.py --self-test` exercises overlap,equality,
strict exclusion and SI units without reading scientific data. The normal
command re-creates the three tables and two evidence JSONs,including input
mutation checks. See design_constraints_specification.json and the evidence.


## Supplied-file integrity and numerical reproduction

These are separate checks. `python code/verify_manifest.py` checks the distributed release bytes, sizes, required files and safe unique paths against its manifest. It does not decide whether independently regenerated floating-point data agree numerically. The three original scientific specification files and original reference-table commitments remain unchanged.

`python reproduce.py` first verifies the supplied release, then rebuilds into a new `_reproduced/` directory. The `--output` option selects a new directory; it must not already exist. Supplied files are never overwritten. The derived-data route in `design_constraints.py` explicitly identifies the verified reference release and checks the newly generated robustness tables under `reproduction_comparison_specification.json` before using their actual generated values. The normal standalone route retains exact original input guards. No values are rounded, replaced from the reference or silently blessed by updating frozen hashes.

The comparison contract enumerates numerical fields, row identities, schemas and units. Small floating-point differences are allowed only in named numerical quantities. Row keys, scenario parameters, counts, statuses, selected thicknesses and decision lists are exact. Lower-estimate eligibility and upper-estimate exclusions are also compared as predicates, so a tiny change that crosses a scientific decision boundary fails even when inside the numerical tolerance. Missing/extra/duplicate records, malformed types, nonfinite values and invalid numerical ordering fail. Detailed per-field tolerances and validated provenance exceptions are in the machine-readable contract.

Reproduction tolerances are far smaller than the numerical estimates used for scientific selection. They are not expanded uncertainty intervals, physical variability or permission to change a target. The comparison report retains actual generated hashes, reference hashes and numerical differences separately. The supplied manifest remains valid after reproduction. Binary plots and document metadata need not be byte-identical across platforms; scientific data and decision agreement are evaluated separately from final visual review.

For all manuscript formats, install `requirements-manuscript.txt` and run `python reproduce.py --manuscript`. The tested TeX engine is pdfTeX1.40.28/MiKTeX25.12 with article,geometry,lmodern,amsmath,amssymb,graphicx,booktabs,array,tabularx,hyperref and microtype. Word and TeX share `manuscript/content.json`, generated by `code/compose_paper.py`; the reviewed PDF is the TeX rendering.

Regenerated `REPORT.md` and `manuscript/content.json` use strict UTF-8 decoding and CRLF-pair-to-LF normalization only. Every other character remains significant. This narrow text comparison is separate from exact supplied-file integrity and does not affect any numerical field. Generated runtime metadata must describe the actual execution environment; the reference record remains historical.

The repository uses `* -text` in `.gitattributes` to preserve frozen artifact bytes across Git checkouts, including systems with `core.autocrlf=true`. Do not renormalize release files. Verify the supplied manifest immediately after cloning.
