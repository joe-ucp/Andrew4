# Qualification of geometry, source data and oxygen accounting

Inspection date: 26 October 2026. The original BEAM supplement, source archive, workbooks and Thomson supplement were retrieved and hashed. Source identifiers, byte hashes, acquisition routes and exact locators are in `sources.tsv`. Publisher files are retained in the local source cache and are not required in the scientific export: the method uses the attributed constants below, with reproducible acquisition paths and hashes. No publisher figure is used as an original research figure.

## Geometry and the unresolved dose discrepancy

The controlling object is [Pham et al.](https://doi.org/10.1038/s41467-025-62271-2), Supplementary Figure 24, PDF page 21, visually inspected. `geometry_ledger.csv` distinguishes reported facts from derived/model quantities. The nominal straight-annulus model gives

\[
V=7\pi[(3.75)^2-(3.00)^2](70)/1000=7.7931132763\ {\rm mL}.
\]

At the reported density, this is 467,586.7966 IEQ. Even the rounded source capacity gives 7 x 1.11 x 60,000 = 466,200 IEQ, rather than the stated 420,000 IEQ. The difference is preserved, without assigning an unmeasured cause. Rounded ends, connector intrusion or fill volume could contribute; none is established here.

The primary model keeps 420,000 IEQ and uses 53,893.7373 IEQ/mL throughout the nominal annulus. The secondary case retains 60,000 IEQ/mL and the full nominal payload. Fixing the primary payload at the source density would instead require 7.0 mL, or 89.823% of nominal volume. These cases must not be mixed to obtain a favorable result. The source's separate small-cluster proposal is not interchangeable with IEQ dose.

Baseline lateral exchange area is 115.45353 cm2. Active single-row bounding footprint is 58.5 x 70 mm = 40.95 cm2. The source figure also labels 88 mm total length with overhead, yielding an illustrated bounding footprint of 51.48 cm2. Redesigned pouch footprints and connector/generator overhead require separate accounting; the illustrated baseline overhead is not evidence that every redesign is mechanically feasible.

## What the released workbooks measure

Read-only inspection found 20 main-text sheets and five supplementary sheets; full names/dimensions are in `workbook_inventory.json`. Main workbook `Figure 6F!A1:E4` contains two values per glucose condition/group. In particular, B4:C4 and D4:E4 correspond to oxygenated hypoxic human-islet assays at low and high glucose. The methods (main-text paragraph Par42, static GSIS) specify hour-long exposures and supernatant assays. Units and protocol must come from the paper, because the sheet's column labels alone do not define the measurement fully. This assay does not directly identify minute-scale intrinsic secretion, effective insulin diffusivity, a transfer kernel or within-device inventory.

Main workbook `Figure 6B!A1:C866` records time, voltage and current; it does not measure insulin delivery. Supplementary workbook `Supplementary Figure 20!A1:I3` records rat C-peptide at baseline and 90 minutes. Those sparse systemic samples neither validate the proposed human-scale geometry nor separate tissue absorption from device release. The source-data archive establishes that public workbooks exist, not that every raw measurement or required dynamic endpoint is public.

## Conditional oxygen and electrical accounting

BEAM's main-text Figure 2 discussion (Par9) assumes q = 2.1 pmol O2/min/IEQ. Supplementary Table 1, PDF page 26, is a cross-study compilation with original and converted units distinguished by color. Its conversion uses 1,560 cells and 10.4 ng DNA per IEQ. Those are conversion assumptions, not patient-specific physiology.

The two Papas-derived human values in that table are particularly easy to misread. The original [Papas et al. (2007), Table 1](https://doi.org/10.1111/j.1600-6143.2006.01655.x) compares clinical HSA-cultured and research FBS-cultured preparations, with OCR/DNA 138 and 202 nmol/min/mg DNA respectively. They are not a basal/stimulated pair. The BEAM table repeats an FBS condition for both; the primary paper's distinction is retained here. The q = 2.1 design scenario corresponds approximately to 202 x 10.4 x 0.001 = 2.1008 pmol/min/IEQ.

Human central OCR values of 1.144 and 2.912 in the compilation are included only as unpaired sensitivity scenarios. They are neither confidence limits nor physiological basal and stimulated bounds. [Wang et al. (2005)](https://doi.org/10.1677/joe.1.06092) reports glucose-induced increases in human/islet OCR, reinforcing the need for matched dynamic measurements. No matched basal-to-stimulated absolute range for this proposed implant has been established here.

For a payload N in IEQ and q in pmol/min/IEQ,

\[
\dot n_{\rm cons}=Nq\,10^{-12}/60\quad({\rm mol/s}),\qquad
I_{\rm ideal}=4F\dot n_{\rm cons}.
\]

F = 96485.33212331001 C/mol follows from the exact SI elementary charge and Avogadro constant. At N = 420,000 and q = 2.1, consumption is 0.882 micromol/min and the ideal current is 5.67334 mA. For comparison only, multiplication by the paper's 1.4-1.8 V operating range yields 7.94267-10.21201 mW. These are zero-leakage, unit-efficiency stoichiometric scenarios. They do not determine actual device power or demonstrate that oxygen reaches every cell.

If the generator must supply all consumption and leakage, the fuller requirement is

\[
I\geq\frac{4F(\dot n_{\rm cons}+\dot n_{\rm leak})}{\epsilon_F},\qquad
P_{\rm supply}\geq\frac{I V_{\rm operating}}{\epsilon_{\rm conversion}}+P_{\rm auxiliary}.
\]

Positive net oxygen supplied by tissue can be separately subtracted only with supporting evidence. Delivery losses, reserve for stimulated consumption, foreign-body effects, spatial gradients, gas handling, battery/wireless losses and control power remain unmeasured. The sensitivity values and current calculations are reproduced by `python code/source_accounting.py` in `evidence/oxygen_accounting.csv`. Thinning at fixed payload does not itself reduce total oxygen consumption.

## Diffusivity and boundary qualification

The nominal 3.0 x 10^-10 m2/s value is an explicit scenario assumption. It is not measured in the BEAM gel or a universal molecular maximum. [Buchwald et al.](https://doi.org/10.1186/s12938-015-0021-9), computational methods, uses insulin diffusion estimates of 1.5 x 10^-10 in water and 1.0 x 10^-10 m2/s in alginate. These support sensitivity context, not universal bounds. The [Thomson supplement](https://doi.org/10.2337/figshare.28500536), PDF pages 2-3, supplies a chamber-membrane time constant and Stokes-Einstein relation for its own membrane model. A selected molecular radius and water viscosity do not measure effective device diffusivity.

Perfect absorbing outer/end faces remove membrane and receiving-tissue resistance in the model. The real pouch has rounded ends and connectors. Favorable sinks are a mathematical relaxation, and finite-resistance coefficients used in sensitivity cases must remain labeled assumptions unless measured. The model does not test immune protection, tissue uptake or glucose lowering.

## Acquisition and integrity

Retrieve the [BEAM supplementary package](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12339981/supplementaryFiles), extract the named MOESM1 PDF and MOESM6 ZIP, then extract the two workbooks. Ignore macOS `._` metadata files. Retrieve Thomson's supplement from the acquisition URL in `sources.tsv`. Compare extracted-object SHA-256 hashes against that table; an archive wrapper can change while contained object bytes remain identical. Web-only literature rows have an empty hash and an explicit access status, never a fabricated byte commitment.

For external review, source reconstruction qualifies the numerical object's premises. It does not experimentally validate its transport predictions. No clinical outcome is measured.

## Revision 02 literature access update

The active comparison is `prior_art_review_v2.md`. Source S5 now records substantive inspection of Trask's public accepted-manuscript main text with publisher-indexed corroboration; no complete publisher-PDF or supplement audit is claimed. Papas2019 is source S9 and remains abstract/publisher-preview only; S8 continues to identify Wang2005. Buchwald and Ernst original XML bytes were acquired and relevant methods/results sections rechecked; their current hashes and exact acquisition endpoints are in `sources.tsv`. These changes qualify literature evidence and do not change numerical parameters or experimental status.
