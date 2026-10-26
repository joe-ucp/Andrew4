# Proposed calibration and held-out validation

Date: 26 October 2026. Scientific measurement proposal. No experiment, fit, funding award, investigator commitment or ethics approval is claimed. This is a measurement-design rationale for qualified investigators, not a clinical protocol or completed evidence.

## Discrimination required

For fixed geometry, materials, boundary conditions and spatial source pattern, the linear response separates production history from transport: external output is a convolution of production with the transfer kernel. If both production and that kernel are unknown, an external curve generally cannot identify them separately. A slow trace may arise from secretion, gel diffusion, membrane/external-film resistance, source depth or combinations. Fitting one trace does not establish a unique explanation.

Tight modal/FV agreement establishes agreement for a specified operator. It does not establish that D, permeability, source pattern or geometry represent the physical implant. The nominal 0.60 mm example is close to the target; its margin must be compared with parameter uncertainty and model discrepancy, rather than only numerical error.

## Proposed sequence

1. **Measure geometry and separate materials.** Record actual inner/outer radii, lengths, thickness variation, open ends, membrane thickness and exposed surfaces. Obtain independent gel-only and membrane-only insulin transport measurements where feasible, with partition/recovery measurements. A tracer may help develop the assay, but molecular-size similarity does not establish identical insulin binding, aggregation or partitioning. Vary external mixing in acellular tests to distinguish a membrane effect from an external stagnant film. State which surface an effective permeability represents and distinguish its units from hydraulic permeability.

2. **Calibrate transport with known inputs.** Use a known incremental amount and documented spatial loading profile in a prespecified calibration geometry. Collect external recovery and retained inventory, resolving early response and the late tail. Correct sample-volume changes, apparatus dead volume, mixing delay and assay recovery. Test mass balance directly rather than impose complete recovery. Cell-free controls and independent assay recovery help discriminate adsorption/degradation from uncollected or delayed transport. Measured initial inventory belongs in the input; background insulin is not newly produced mass.

3. **Freeze before held-out prediction.** Prespecify calibration and validation geometries. One possible arrangement calibrates the nominal 0.75 mm geometry and holds out the 0.60 and 0.41 mm alternatives. Include a different length or end-exposure condition to test radial/end tradeoffs. Fit only calibration data and independent material measurements, freeze the parameter distribution and then predict complete held-out output/inventory curves without refitting each geometry. If fabrication changes properties with geometry, define and measure that relation rather than absorb discrepancies into arbitrary fits.

4. **Challenge the temporal input separately.** Compare known pulse, sustained and delayed inputs using the same frozen operator. Report absolute amounts and denominator definitions: total event production and production accumulated by a deadline are different quantities. A delayed or short input changes molecule ages at the deadline despite unchanged transport. Test for structured early/late residuals; a matching 30-minute total may conceal incorrect dynamics.

5. **Add living sources only after transport calibration.** Characterize positions and viable IEQ payload, independently estimate production and measure external output under documented glucose/oxygen conditions. A paired unencapsulated reference may help but is not automatically ground truth for encapsulated secretion. A single hourly external GSIS value cannot resolve minute-scale production and transfer. Spatially heterogeneous, time-varying secretion may require a distributed source rather than one common waveform multiplied by a fixed position profile.

6. **Evaluate the whole map.** Prespecify errors for the output curve, retained inventory, multiple deadlines and recovery, with acceptance criteria based on assay precision and a meaningful predictive tolerance chosen before validation. No empirically justified tolerance or sample size is invented here; a pilot and prospective precision/power analysis should inform these choices. Assess independent preparations and device batches, prediction intervals, and systematic model discrepancy. Any robust-design claim must name its uncertainty/scenario set, preserve payload/density and report area, segment count and footprint. Report infeasible regions instead of relaxing a failed target.

## Identifiability checks

For a simple layer, D*T/h^2 and P*h/D describe diffusion time and boundary versus internal transport. A finite annulus also depends on radius ratio and aspect ratio. These groups explain tradeoffs among uncertain thickness, D and P. They do not prove that D and P are always structurally unidentifiable: informative curves and independent geometry can distinguish them in some regimes. Evaluate practical identifiability for the actual experiment.

- Examine sensitivity matrices, parameter correlations and profile likelihoods for D, effective P, partition, source depth and timing. Report weak directions rather than only fitted values or optimizer convergence.
- Near a perfect sink, data may yield only a lower bound on P; in a boundary-limited regime, D can be weakly constrained. More replicates alone may not resolve this. Geometry/mixing changes should alter the relevant sensitivity pattern.
- Unknown production amplitude trades off with viable payload, accessible volume and assay recovery. Use absolute mass and inventory alongside normalized fractions. A normalized response suppresses amplitude information and cannot establish therapeutic capacity.
- A membrane experiment may identify K*D_membrane/thickness rather than K and D separately. Distinct partition or diffusion measurements are needed before assigning separate microscopic parameters.
- A fitted source-depth profile can compensate for D or P. Obtain independent position information; otherwise retain alternative profiles as scenarios.
- Late residuals can reflect binding, degradation, multiple transport times or unmodeled reservoirs. Use recovery and inventory to discriminate them rather than add unconstrained exponentials merely to improve fit.

## Interpretation and stopping boundary

Failure on held-out geometry or waveform reopens the operator/source description even if the calibration case can be refitted. Successful acellular prediction would support transport mapping for those materials/boundaries. It would not establish immune protection, oxygen sufficiency, chronic tissue response, insulin pharmacokinetics or glucose control. Living-cell and eventual in vivo evidence address separate outcomes.

The current computational revision can finish without these experiments by presenting the map, identifying its unmeasured parameters and stating this discriminating route. The proposal must not be labeled a completed validation, a clinically robust design or demonstrated therapeutic efficacy.
