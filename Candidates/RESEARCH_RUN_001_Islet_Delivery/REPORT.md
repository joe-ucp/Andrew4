# Early delivery and fixed-dose design trade-offs

The nominal uniform continuous-source model delivers **71.53% by 30 minutes**. This remains a conditional computational result, not a general implant ceiling. Numerical uncertainty is approximately 0.0032 percentage points; unmeasured physical assumptions cause much larger changes.

The favorable 0.60 mm redesign passes 80% only narrowly. Reflecting ends gives 79.9934%, a 5% diffusivity reduction gives 79.25%, and D=1e-10m²/s gives 55.23%. Across the declared eight-scenario subset, the 80% sampled requirement becomes 0.53 mm, 158.22 cm²(+37.04%) and ten pouches. Across all 24 assumed scenarios, it becomes 0.21 mm, 381.79 cm²(+230.69%) and 24 pouches. These are finite-set grid requirements, not continuous uncertainty guarantees or validated designs.

At hypothetical minimum thicknesses of 0.25 and 0.30 mm, the full-set maximum is 75.90% and 69.67%; no remaining sampled design meets 80%. These limits are not measured biological cutoffs. Separate reoptimization gives areas of 141.18 cm² favorable, 240.09 cm² lower-D-only, 289.12 cm² finite-P-only, 143.36 cm² reflecting-only, and 381.79 cm² combined. The penalties are nonadditive.

The manuscript centers the transfer response for arbitrary uniform source histories, includes physical provenance, original geometry and design figures, area/footprint/pouch costs, closest-work comparison and a calibration/held-out-geometry validation plan. No experiment was performed.

Read manuscript/paper.pdf, code/METHODS.md, evidence/robustness_verification.json and RESPONSE_TO_REVIEW.md. Reproduce with `python reproduce.py --manuscript`. The repository contains the scientific release; reconstruction writes to an isolated output directory.
