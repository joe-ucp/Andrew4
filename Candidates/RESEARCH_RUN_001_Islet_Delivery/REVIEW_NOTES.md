# Final hostile review of Revision 3

The hostile review found substantive implementation and portability defects. The conditional transport and fixed-dose design findings remain unchanged. This is an internal computational review, not external scientific or experimental validation.

## Findings and corrections

| Finding | Consequence | Correction |
|---|---|---|
| Reproduction overwrote supplied tables and then applied original byte hashes to regenerated output | Harmless floating-point variation could stop a valid reproduction; the supplied reference could be changed by the attempt | Verify the supplied release first, rebuild into a separate directory, and compare generated numerical results under an explicit tolerance/schema contract. Preserve the actual generated values and separate hashes. |
| Manifest validation used Python assertions | Running with `python -O` could disable checks and report success for an invalid manifest | Use unconditional validation errors for schema, paths, sizes, hashes and required artifacts; test the optimized interpreter explicitly. |
| Build intermediates and an older redundant numerical record remained beside review files | A future broad repository add could include logs or confusing obsolete output | Keep private records and archived intermediates under `_UCP`, and test `.gitignore` rules while keeping scientific deliverables visible. |

Transport-map differences of approximately **5.6 × 10⁻¹⁴**, with unchanged decisions, motivate the numerical-comparison regression case. It does not rewrite the scientific specifications, round results into agreement or widen any engineering acceptance rule.

Adversarial testing of the replacement comparator also caught two defects before acceptance: ordinary JSON float parsing could erase a tiny change to an exact numeric identity, and a sub-tolerance negative recovery fraction could evade a generic difference check. The repair preserves decimal values during identity/decision comparison and checks physical fraction domains separately from numerical closeness. Both failures are retained as regression cases.

## Cross-platform portability

Regenerated narrative text accepts CRLF/LF differences only: strict UTF-8 decoding is followed by replacement of CRLF pairs with LF, preserving every other character, including lone carriage returns, byte-order marks, spaces and final-newline presence. Raw reference and generated hashes remain in the comparison report. Supplied-file integrity always checks exact bytes.

Test fixtures refresh only generated environment records to the actual test runtime; historical reference metadata stays fixed. Deliberately incorrect generated runtime metadata remains a rejection case. `.gitattributes` uses `* -text` to prevent Git newline conversion from altering frozen files.

## What must agree

The [comparison contract](reproduction_comparison_specification.json) defines each numeric field, its units and permitted reproduction difference. It covers 22 generated CSV tables and eight scientific JSON/TXT records. Supplied-file integrity remains an exact SHA-256 check.

Generated row identities, scenario parameters, counts, selected thicknesses, statuses and decision lists must match exactly. Lower-estimate eligibility and upper-estimate exclusion predicates must also match, even if a decision-changing numerical difference falls inside a floating-point tolerance. Structural errors, nonfinite numbers, invalid signs/order and material drift are failures.

The source tables and all three original scientific specifications remain fixed. The reference and generated output hashes are recorded separately. A successful regenerated comparison establishes agreement within the stated reproduction contract; it does not assert byte identity, certified interval bounds or calibrated device performance.

## Additional scientific challenge

An independent derivation of the radial mean exit time from the Poisson problem was evaluated with 60-digit decimal arithmetic in 12 geometry/diffusivity/permeability cases. The existing spectral moments agreed within their omitted-tail estimates and a small floating-point allowance. This checks the Robin boundary sign, modal normalization and weights through a different mathematical calculation; it is not another experiment or a complete independent transport implementation.

The 71.53% nominal result, minimum-thickness exclusions and nonadditive mechanism comparisons retain their original scope. No actual biological minimum thickness has been assigned, and no clinical or manufacturing recommendation follows.

## Regression checks

The public suite passed **24 tests**, covering newline equivalence, significant text differences, truthful generated-runtime metadata, strict foreign-runtime rejection, isolated outputs, frozen-reference guards, tampering under normal and optimized Python, exact decimal identities, numerical drift, threshold decisions and physical fraction/flux domains. An additional portability audit passed **39 targeted probes**. The earlier scientific challenge covered 12 exact mean-residence-time cases.

```bash
python code/test_reproduction_contract.py
```

These regression tests mutate temporary fixtures and do not claim to be a new transport calculation. The full `python reproduce.py --manuscript` command independently regenerates the transport outputs into a fresh directory and writes `reproduction_report.json`, including reference/generated hashes, actual numerical differences and exact-decision checks.

## Review materials

- [Manuscript](manuscript/paper.pdf) and [editable Word version](manuscript/paper.docx).
- [Methods and reproduction distinctions](code/METHODS.md).
- [Original focused review response](RESPONSE_TO_REVIEW.md).
- [Proposed discriminating validation](evidence/proposed_validation.md).

Private framework sources, internal review history and historical archives are excluded from the repository release.
