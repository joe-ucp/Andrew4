"""Rebuild source-derived geometry and conditional oxygen accounting (standard library).

These constants are attributed in sources.tsv and evidence/source_qualification.md.
They do not depend on publisher files or the private workflow directory.
"""
from pathlib import Path
import csv
import math

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build():
    radius, thickness, length, count, dose = 3.75, 0.75, 70., 7, 420000.
    inner = radius - thickness
    cross_section = math.pi * (radius**2 - inner**2)
    volume = count * length * cross_section / 1000  # mm3 / 1000 = mL
    density = dose / volume
    surface = 2 * math.pi * radius * count * length / 100  # mm2 / 100 = cm2
    rows = []

    def row(identifier, name, value, units, status, source, location, derivation, limitation):
        rows.append(dict(parameter_id=identifier, quantity=name, value=value, units=units,
                         status=status, source_id=source, source_location=location,
                         derivation=derivation, limitation=limitation))

    loc = 'Supplementary Figure 24; PDF page 21'
    row('G01', 'pouch_count', count, 'pouches', 'source_reported', 'S1-SUPP', loc, '', 'Proposed human configuration; not clinical measurement')
    row('G02', 'pouch_outer_diameter', 2*radius, 'mm', 'source_reported', 'S1-SUPP', loc, '', 'Approximate source dimensions')
    row('G03', 'cell_layer_thickness', thickness, 'mm', 'source_reported', 'S1-SUPP', loc, '', 'Annular idealization; source end shape rounded')
    row('G04', 'active_length_per_pouch', length, 'mm', 'source_reported_and_idealized', 'S1-SUPP', loc, '', 'Treat full indicated length as straight active annulus')
    row('G05', 'pouch_separation', 1., 'mm', 'source_reported', 'S1-SUPP', loc, '', 'Clear gap for single-row parallel layout')
    row('G06', 'intended_human_payload', dose, 'IEQ', 'source_reported', 'S1-SUPP', loc, '', 'IEQ is volume normalized, not cluster count or potency')
    row('G07', 'source_loading_density', 60000., 'IEQ/mL', 'source_reported', 'S1-SUPP', loc, '', 'Not reconciled with stated 420000 IEQ and full nominal volume')
    row('G08', 'source_rounded_volume_per_pouch', 1.11, 'mL', 'source_reported', 'S1-SUPP', loc, '', 'Rounded volume')
    row('G09', 'outer_radius', radius, 'mm', 'derived', 'S1-SUPP', loc, 'G02 / 2', '')
    row('G10', 'inner_radius', inner, 'mm', 'derived', 'S1-SUPP', loc, 'G09 - G03', '')
    row('G11', 'annular_cross_section', cross_section, 'mm2', 'derived', 'S1-SUPP', loc, 'pi*(G09^2-G10^2)', '')
    row('G12', 'nominal_volume_per_pouch', volume/count, 'mL', 'derived', 'S1-SUPP', loc, 'G11*G04/1000', 'Straight annulus omits detailed rounded ends and connector intrusion')
    row('G13', 'nominal_total_cell_compartment_volume', volume, 'mL', 'derived', 'S1-SUPP', loc, 'G12*G01', 'Same idealization')
    row('G14', 'full_nominal_payload_at_source_density', volume*60000, 'IEQ', 'secondary_case', 'S1-SUPP', loc, 'G13*G07', 'Separate case; not substituted for stated payload')
    row('G15', 'rounded_volume_payload_at_source_density', 1.11*count*60000, 'IEQ', 'derived_discrepancy', 'S1-SUPP', loc, 'G08*G01*G07', '466200 IEQ differs from stated 420000 IEQ')
    row('G16', 'effective_uniform_density_primary', density, 'IEQ/mL', 'model_normalization', 'S1-SUPP', loc, 'G06/G13', 'Preserves reported dose in full nominal model volume; not measured fill density')
    row('G17', 'volume_required_at_source_density', dose/60000, 'mL', 'derived', 'S1-SUPP', loc, 'G06/G07', 'Alternative occupied-volume interpretation; not assumed as fact')
    row('G18', 'fraction_nominal_volume_for_reported_dose', dose/(60000*volume), 'fraction', 'derived', 'S1-SUPP', loc, 'G17/G13', 'Unresolved effective fill explanation')
    row('G19', 'outer_lateral_exchange_area', surface, 'cm2', 'derived', 'S1-SUPP', loc, '2*pi*G09*G04*G01/100', 'Excludes annular ends and overhead')
    row('G20', 'both_annular_end_area', 2*count*cross_section/100, 'cm2', 'derived', 'S1-SUPP', loc, '2*G01*G11/100', 'Both ends are perfect sinks only in favorable model')
    row('G21', 'baseline_active_row_width', count*2*radius+(count-1)*1, 'mm', 'derived', 'S1-SUPP', loc, 'G01*G02+(G01-1)*G05', 'Single-row bounding width')
    row('G22', 'baseline_active_rectangular_footprint', (count*2*radius+(count-1))*length/100, 'cm2', 'derived', 'S1-SUPP', loc, 'G21*G04/100', 'Excludes generator and connectors; not total implant footprint')
    row('G23', 'illustrated_total_length_with_overhead', 88., 'mm', 'source_figure_label', 'S1-SUPP', loc, '', 'Source illustration; not imposed on redesigned layouts')
    row('G24', 'illustrated_total_bounding_footprint', 88*58.5/100, 'cm2', 'derived_from_figure_labels', 'S1-SUPP', loc, '88*58.5/100', 'Illustrated baseline bound includes source overhead; does not prove buildability')
    write_csv(ROOT/'geometry_ledger.csv', rows)

    # Faraday constant = elementary charge * Avogadro constant, exact SI values.
    faraday = 1.602176634e-19 * 6.02214076e23
    oxygen = []
    for name, payload, q, status, source_id, source_location in [
        ('source_design_scenario_primary', dose, 2.1, 'BEAM main text Fig2 discussion assumed human OCR; not paired stimulated maximum',
         'S1-MAIN;S1-SUPP;S7', 'Main text Par9 Fig2 discussion; Supplementary Table1 p26 human row ref10; Papas2007 Table1 research FBS group'),
        ('source_design_scenario_nominal_payload', volume*60000, 2.1, 'Same OCR assumption at secondary full nominal dose',
         'S1-MAIN;S1-SUPP;S7', 'Main text Par9 Fig2 discussion; Supplementary Table1 p26 human row ref10; Papas2007 Table1 research FBS group'),
        ('human_table_low_central_value', dose, 1.144, 'Unpaired published condition; not a basal lower bound',
         'S1-SUPP', 'Supplementary Table1 PDF p26 human row ref12; converted central value1.144 pmol/min/IEQ; underlying paper not independently inspected'),
        ('human_table_high_central_value', dose, 2.912, 'Unpaired published condition; not a stimulated upper bound',
         'S1-SUPP', 'Supplementary Table1 PDF p26 human row ref8 day2; converted central value2.912 pmol/min/IEQ; underlying thesis not independently inspected'),
    ]:
        mol_s = payload*q*1e-12/60
        current = 4*faraday*mol_s
        oxygen.append(dict(scenario=name, payload_IEQ=payload, OCR_pmol_per_min_per_IEQ=q,
                           oxygen_mol_per_s=mol_s, oxygen_umol_per_min=mol_s*60e6,
                           ideal_current_mA=current*1000,
                           ideal_electrolyzer_power_at_1p4V_mW=current*1.4*1000,
                           ideal_electrolyzer_power_at_1p8V_mW=current*1.8*1000,
                           source_id=source_id, source_location=source_location, interpretation=status,
                           assumed_oxygen_leakage_mol_per_s=0, assumed_faradaic_efficiency=1,
                           limitation='Stoichiometric floor only; actual leakage/efficiency/delivery/peak demand and auxiliary power unmeasured'))
    write_csv(ROOT/'evidence'/'oxygen_accounting.csv', oxygen)
    return {'volume_mL':volume, 'effective_density_IEQ_per_mL':density, 'area_cm2':surface,
            'ideal_current_mA':oxygen[0]['ideal_current_mA']}


if __name__ == '__main__':
    import json
    print(json.dumps(build(), indent=2))

