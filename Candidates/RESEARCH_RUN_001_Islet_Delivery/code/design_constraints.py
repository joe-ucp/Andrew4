"""Minimum-thickness constraints and mechanism reoptimizations of verified data.

Run ``python code/design_constraints.py`` for the exact supplied inputs.
The isolated wrapper explicitly passes ``--reference-release`` for regenerated
tables: original baseline bytes are checked first, then a separate frozen
numerical-equivalence contract. No transport solver is imported or executed.
``--self-test`` exercises decision logic on synthetic records only.
"""
from pathlib import Path
from itertools import product
import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SPEC_SHA256 = "be2c3dbdc19b3d63397f87f3ef125929987e01a23658088c57c3f46151416689"
TOL = 1e-12
SELECTED = "minimum within constrained grid and discrete scenario set"
NOT_ATTAINED = "not attained within constrained grid"
UNRESOLVED = "unresolved numerical overlap"
GEOMETRY_FIELDS = [
    "payload_IEQ", "density_IEQ_per_ml", "volume_ml", "lateral_area_cm2",
    "end_area_cm2", "area_ratio_to_nominal", "total_length_mm", "pouch_count",
    "last_segment_mm", "parallel_width_mm", "active_bounding_footprint_cm2",
]
RESOURCE_FIELDS = [
    "lateral_area_cm2", "area_ratio_to_nominal", "pouch_count", "last_segment_mm",
    "total_length_mm", "active_bounding_footprint_cm2",
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded_spec(root=ROOT, reference_release=None):
    if reference_release is not None:
        # Preserve the original exact guard as the first gate. The frozen hashes
        # continue to identify reference data, never differently hashed output.
        reference_release = Path(reference_release).resolve()
        spec = guarded_spec(reference_release)
        actual = sha256(root / "design_constraints_specification.json")
        if actual != EXPECTED_SPEC_SHA256:
            raise RuntimeError(f"Frozen design-constraint specification differs: {actual}")
        from reproduction_contract import compare_transport_inputs
        result = compare_transport_inputs(reference_release, root)
        result["verification_inputs_sha256_semantics"] = (
            "design_constraints_verification.json.inputs_sha256 records the accepted "
            "original reference-input identities. Actual regenerated table hashes "
            "are recorded separately in generated_input_sha256 here.")
        (root / "evidence/regenerated_input_comparison.json").write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return spec
    path = root / "design_constraints_specification.json"
    actual = sha256(path)
    if actual != EXPECTED_SPEC_SHA256:
        raise RuntimeError(f"Frozen design-constraint specification differs: {actual}")
    spec = json.loads(path.read_text(encoding="utf-8"))
    for name, expected in spec["inputs_sha256"].items():
        actual = sha256(root / name)
        if actual != expected:
            raise RuntimeError(f"Bound scientific input differs: {name}: {actual}")
    return spec


def readcsv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def mutation_guard_checks(spec, root):
    """Mutate temporary copies; never alter reviewed inputs in the run folder."""
    tested = []
    with tempfile.TemporaryDirectory(prefix="islet_constraints_guard_") as temp:
        sandbox = Path(temp)
        names = ["design_constraints_specification.json", *spec["inputs_sha256"]]
        for name in names:
            destination = sandbox / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, destination)
        for name in names:
            destination = sandbox / name
            original = destination.read_bytes()
            destination.write_bytes(original + b"\n ")
            try:
                guarded_spec(sandbox)
            except RuntimeError:
                tested.append(name)
            else:
                raise AssertionError(f"Mutation was not rejected: {name}")
            finally:
                destination.write_bytes(original)
        guarded_spec(sandbox)
    assert len(tested) == 5
    return tested


def writecsv(path, rows):
    assert rows
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def h_index(value):
    h = float(value)
    idx = round(h * 100)
    if abs(idx / 100 - h) > TOL or not 10 <= idx <= 100:
        raise ValueError(f"Invalid existing thickness grid point: {value}")
    return idx


def p_value(value):
    return "infinite" if value == "infinite" else float(value)


def case_key(row):
    return (row["D_m2_s"], row["P_m_s"], row["end_condition"])


def case_description(row):
    return {"D_m2_s": row["D_m2_s"], "P_m_s": row["P_m_s"],
            "end_condition": row["end_condition"]}


def expected_cases(description):
    return set(product(description["D_m2_s"], description["P_m_s"], description["ends"]))


def load_map(spec, root=ROOT):
    rows = readcsv(root / "data/robustness_map.csv")
    expected = expected_cases(spec["scenario_sets"]["broad_discrete"])
    seen = set()
    geometry = {}
    for row in rows:
        for key in ["thickness_mm", "D_m2_s", "deadline_min", "eta",
                    "eta_lower_estimate", "eta_upper_estimate"] + GEOMETRY_FIELDS:
            row[key] = float(row[key])
            if not math.isfinite(row[key]):
                raise ValueError(f"Nonfinite input: {key}")
        row["P_m_s"] = p_value(row["P_m_s"])
        idx = h_index(row["thickness_mm"])
        assert row["deadline_min"] in (15, 30, 60)
        assert case_key(row) in expected
        key = (idx, row["deadline_min"], *case_key(row))
        assert key not in seen, f"Duplicate input row: {key}"
        seen.add(key)
        assert 0 <= row["eta_lower_estimate"] <= row["eta"] <= row["eta_upper_estimate"] <= 1
        assert abs(row["payload_IEQ"] - 420000) < TOL
        assert abs(row["density_IEQ_per_ml"] - 53893.73734328731) < 1e-8
        assert abs(row["volume_ml"] - 7.793113276311181) < TOL
        assert row["pouch_count"].is_integer()
        row["pouch_count"] = int(row["pouch_count"])
        assert 0 < row["last_segment_mm"] <= 70 + TOL
        if idx not in geometry:
            geometry[idx] = {field: row[field] for field in GEOMETRY_FIELDS}
        for field in GEOMETRY_FIELDS:
            assert math.isclose(row[field], geometry[idx][field], rel_tol=TOL, abs_tol=TOL)
    assert len(rows) == 6552
    assert len(seen) == 91 * 3 * 24
    assert set(geometry) == set(range(10, 101))
    return rows


def aggregate(rows):
    """Conservative estimate of a finite scenario minimum at one thickness."""
    assert rows
    assert len({r["thickness_mm"] for r in rows}) == 1
    point = min(r["eta"] for r in rows)
    lower = min(r["eta_lower_estimate"] for r in rows)
    upper = min(r["eta_upper_estimate"] for r in rows)
    point_worst = [case_description(r) for r in rows if abs(r["eta"] - point) <= TOL]
    upper_worst = min(rows, key=lambda r: r["eta_upper_estimate"])
    result = {
        "thickness_mm": rows[0]["thickness_mm"],
        "minimum_eta": point, "minimum_eta_lower_estimate": lower,
        "minimum_eta_upper_estimate": upper,
        "worst_D_m2_s": point_worst[0]["D_m2_s"],
        "worst_P_m_s": point_worst[0]["P_m_s"],
        "worst_end_condition": point_worst[0]["end_condition"],
        "point_limiting_scenarios": point_worst,
        "upper_exclusion_scenario": case_description(upper_worst),
    }
    result.update({field: rows[0][field] for field in RESOURCE_FIELDS})
    assert lower <= point <= upper
    return result


def grouped_designs(rows, cases, deadline=30):
    selected = [r for r in rows if r["deadline_min"] == deadline and case_key(r) in cases]
    designs = []
    for idx in range(10, 101):
        group = [r for r in selected if h_index(r["thickness_mm"]) == idx]
        assert len(group) == len(cases)
        designs.append(aggregate(group))
    return designs


def choose_design(designs, target):
    """No monotonicity shortcut: enumerate all qualifying and competing designs."""
    assert designs
    qualified = [d for d in designs if d["minimum_eta_lower_estimate"] >= target]
    candidate = min(qualified, key=lambda d: (d["lateral_area_cm2"], d["thickness_mm"])) if qualified else None
    smaller = [d for d in designs if candidate and d["lateral_area_cm2"] < candidate["lateral_area_cm2"]]
    unresolved = [d for d in smaller if d["minimum_eta_upper_estimate"] >= target]
    if candidate and not unresolved:
        status = SELECTED
    elif max(d["minimum_eta_upper_estimate"] for d in designs) < target:
        status = NOT_ATTAINED
    else:
        status = UNRESOLVED
    if not candidate:
        unresolved = [d for d in designs if d["minimum_eta_lower_estimate"] < target <= d["minimum_eta_upper_estimate"]]
    excluded = [d for d in smaller if d["minimum_eta_upper_estimate"] < target]
    all_failed = [d for d in designs if d["minimum_eta_upper_estimate"] < target]
    trace = {
        "status": status,
        "eligible_h_mm": [d["thickness_mm"] for d in designs],
        "qualified_h_mm": [d["thickness_mm"] for d in qualified],
        "candidate_h_mm": candidate["thickness_mm"] if candidate else None,
        "lower_area_excluded_h_mm": [d["thickness_mm"] for d in excluded],
        "unresolved_h_mm": [d["thickness_mm"] for d in unresolved],
        "upper_below_target_h_mm": [d["thickness_mm"] for d in all_failed],
        "equal_area_qualified_h_mm": [d["thickness_mm"] for d in qualified if candidate and d["lateral_area_cm2"] == candidate["lateral_area_cm2"]],
    }
    if status == SELECTED:
        assert len(excluded) == len(smaller)
    if status == NOT_ATTAINED:
        assert len(all_failed) == len(designs)
    return status, candidate, trace


def maximum_row(name, count, idx, designs):
    best = max(designs, key=lambda d: (d["minimum_eta"], -d["lateral_area_cm2"]))
    overlaps = [d for d in designs if d is not best and d["minimum_eta_upper_estimate"] >= best["minimum_eta_lower_estimate"]]
    return {
        "scenario_set": name, "scenario_count": count, "h_min_mm": idx / 100,
        "deadline_min": 30, "eligible_design_count": len(designs),
        "maximum_worst_eta": best["minimum_eta"],
        "maximum_worst_eta_lower_estimate": max(d["minimum_eta_lower_estimate"] for d in designs),
        "maximum_worst_eta_upper_estimate": max(d["minimum_eta_upper_estimate"] for d in designs),
        "point_maximizer_thickness_mm": best["thickness_mm"],
        "point_maximizer_lateral_area_cm2": best["lateral_area_cm2"],
        "point_maximizer_worst_D_m2_s": best["worst_D_m2_s"],
        "point_maximizer_worst_P_m_s": best["worst_P_m_s"],
        "point_maximizer_worst_end_condition": best["worst_end_condition"],
        "other_maximizer_interval_overlap_count": len(overlaps),
        "other_maximizer_interval_overlap_h_mm": ";".join(str(d["thickness_mm"]) for d in overlaps),
        "constraint_status": "hypothetical minimum thickness; physical value unassigned",
    }


def selection_row(name, count, idx, target, designs):
    status, candidate, trace = choose_design(designs, target)
    chosen = candidate if status == SELECTED else None
    fields = ["thickness_mm", "minimum_eta", "minimum_eta_lower_estimate", "minimum_eta_upper_estimate"] + RESOURCE_FIELDS + ["worst_D_m2_s", "worst_P_m_s", "worst_end_condition"]
    result = {"scenario_set": name, "scenario_count": count, "h_min_mm": idx / 100,
              "deadline_min": 30, "target_eta": target, "status": status,
              "eligible_design_count": len(designs),
              "lower_area_competitors_excluded": len(trace["lower_area_excluded_h_mm"]),
              "unresolved_competitor_count": len(trace["unresolved_h_mm"]),
              "maximum_worst_eta_upper_estimate": max(d["minimum_eta_upper_estimate"] for d in designs)}
    result.update({field: chosen[field] if chosen else "" for field in fields})
    result["area_increase_percent_to_nominal"] = 100 * (chosen["area_ratio_to_nominal"] - 1) if chosen else ""
    result["selected_at_h_min"] = h_index(chosen["thickness_mm"]) == idx if chosen else ""
    result["selected_at_thickest_grid_boundary"] = h_index(chosen["thickness_mm"]) == 100 if chosen else ""
    result["thinner_than_150um_IEQ_reference_diameter"] = h_index(chosen["thickness_mm"]) < 15 if chosen else ""
    trace.update({"scenario_set": name, "h_min_mm": idx / 100, "target_eta": target})
    return result, trace


def dimensionless(case, h_mm):
    h = h_mm / 1000
    return {"Fo": case["D_m2_s"] * 1800 / h**2,
            "Bi": "infinite" if case["P_m_s"] == "infinite" else case["P_m_s"] * h / case["D_m2_s"]}


def verify_existing_frontier(spec, all_designs, root=ROOT):
    existing = [r for r in readcsv(root / "data/robustness_frontier.csv") if float(r["deadline_min"]) == 30]
    assert len(existing) == 273
    columns = ["minimum_eta", "minimum_eta_lower_estimate", "minimum_eta_upper_estimate"] + RESOURCE_FIELDS
    maximum_difference = 0.0
    for row in existing:
        current = all_designs[row["scenario_set"]][h_index(row["thickness_mm"]) - 10]
        for column in columns:
            difference = abs(float(row[column]) - current[column])
            maximum_difference = max(maximum_difference, difference)
            assert difference <= TOL, (row["scenario_set"], row["thickness_mm"], column, difference)
    return maximum_difference


def main(root=ROOT, reference_release=None):
    spec = guarded_spec(root, reference_release)
    negative_guard_checks = mutation_guard_checks(spec, Path(reference_release) if reference_release else root)
    rows = load_map(spec, root)
    designs_by_set = {name: grouped_designs(rows, expected_cases(desc)) for name, desc in spec["scenario_sets"].items()}
    frontier_difference = verify_existing_frontier(spec, designs_by_set, root)
    maxima, selections, selection_traces = [], [], []
    for name, description in spec["scenario_sets"].items():
        count = len(expected_cases(description))
        designs = designs_by_set[name]
        for idx in range(10, 101):
            eligible = [d for d in designs if h_index(d["thickness_mm"]) >= idx]
            maxima.append(maximum_row(name, count, idx, eligible))
            for target in spec["grid"]["targets_eta"]:
                result, trace = selection_row(name, count, idx, target, eligible)
                selections.append(result)
                selection_traces.append(trace)
    assert len(maxima) == 273 and len(selections) == 546
    for name in designs_by_set:
        subset = [r for r in maxima if r["scenario_set"] == name]
        for key in ["maximum_worst_eta", "maximum_worst_eta_lower_estimate", "maximum_worst_eta_upper_estimate"]:
            assert all(b[key] <= a[key] for a, b in zip(subset, subset[1:]))
        for target in spec["grid"]["targets_eta"]:
            subset = [r for r in selections if r["scenario_set"] == name and r["target_eta"] == target]
            base = subset[0]
            for result in subset:
                if result["status"] == SELECTED:
                    assert result["thickness_mm"] >= result["h_min_mm"]
                if base["status"] == SELECTED and result["h_min_mm"] <= base["thickness_mm"]:
                    assert result["status"] == SELECTED and result["thickness_mm"] == base["thickness_mm"]
    old_targets = [r for r in readcsv(root / "data/robustness_targets.csv") if float(r["deadline_min"]) == 30 and float(r["target_eta"]) in (.8, .9)]
    assert len(old_targets) == 6
    for old in old_targets:
        current = next(r for r in selections if r["scenario_set"] == old["scenario_set"] and r["target_eta"] == float(old["target_eta"]) and r["h_min_mm"] == .1)
        assert current["status"] == SELECTED
        assert abs(current["thickness_mm"] - float(old["thickness_mm"])) <= TOL
    mechanisms, mechanism_designs, mechanism_traces = [], {}, []
    for case in spec["mechanism_comparison"]["cases"]:
        designs = grouped_designs(rows, {(case["D_m2_s"], case["P_m_s"], case["ends"])})
        mechanism_designs[case["name"]] = designs
        result, trace = selection_row(case["name"], 1, 10, .8, designs)
        result = {"mechanism_case": result.pop("scenario_set"), **result}
        result.update({"D_m2_s": case["D_m2_s"], "P_m_s": case["P_m_s"], "end_condition": case["ends"]})
        assert result["status"] == SELECTED
        selected_h = result["thickness_mm"]
        nominal = next(d for d in designs if h_index(d["thickness_mm"]) == 75)
        result["nominal_h_mm"] = .75
        result["eta_at_nominal_h"] = nominal["minimum_eta"]
        result["eta_lower_at_nominal_h"] = nominal["minimum_eta_lower_estimate"]
        result["eta_upper_at_nominal_h"] = nominal["minimum_eta_upper_estimate"]
        for prefix, h_mm in [("selected", selected_h), ("nominal", .75)]:
            result.update({f"{prefix}_{key}": value for key, value in dimensionless(case, h_mm).items()})
        result["selected_h_over_outer_radius"] = selected_h / 3.75
        result["selected_longest_segment_over_h"] = (70 if result["pouch_count"] > 1 else result["last_segment_mm"]) / selected_h
        result["selected_remainder_over_h"] = result["last_segment_mm"] / selected_h
        result["nominal_h_over_outer_radius"] = .75 / 3.75
        result["nominal_segment_over_h"] = 70 / .75
        smaller = [d for d in designs if d["lateral_area_cm2"] < result["lateral_area_cm2"]]
        adjacent = max(smaller, key=lambda d: d["lateral_area_cm2"]) if smaller else None
        result["next_lower_area_h_mm"] = adjacent["thickness_mm"] if adjacent else ""
        result["next_lower_area_eta"] = adjacent["minimum_eta"] if adjacent else ""
        result["next_lower_area_eta_upper_estimate"] = adjacent["minimum_eta_upper_estimate"] if adjacent else ""
        result["max_upper_among_all_lower_area_competitors"] = max(d["minimum_eta_upper_estimate"] for d in smaller) if smaller else ""
        result["minimum_target_margin_lower_estimate"] = result["minimum_eta_lower_estimate"] - .8
        result["comparison_status"] = "separate conditional reoptimization; resource changes are nonadditive"
        mechanisms.append(result)
        mechanism_traces.append(trace)
    favorable_area = mechanisms[0]["lateral_area_cm2"]
    for result in mechanisms:
        result["additional_area_cm2_vs_favorable_reoptimization"] = result["lateral_area_cm2"] - favorable_area
        result["additional_area_percent_vs_favorable_reoptimization"] = 100 * (result["lateral_area_cm2"] / favorable_area - 1)
    expected = spec["verification"]["reviewer_expected_checks"]
    reviewer_checks = []
    for h_min, expected_percent in [(.25, expected["broad_h_min_0p25_max_eta_rounded_percent"]), (.30, expected["broad_h_min_0p30_max_eta_rounded_percent"])]:
        observed = next(r for r in maxima if r["scenario_set"] == "broad_discrete" and r["h_min_mm"] == h_min)
        selection = next(r for r in selections if r["scenario_set"] == "broad_discrete" and r["h_min_mm"] == h_min and r["target_eta"] == .8)
        assert abs(100 * observed["maximum_worst_eta"] - expected_percent) < .0051
        assert selection["status"] == NOT_ATTAINED
        reviewer_checks.append({"h_min_mm": h_min, "maximum_eta": observed["maximum_worst_eta"], "maximum_lower": observed["maximum_worst_eta_lower_estimate"], "maximum_upper": observed["maximum_worst_eta_upper_estimate"], "expected_rounded_percent": expected_percent, "target_0p8_status": selection["status"]})
    for result, h, area in zip(mechanisms, expected["mechanism_selected_h_mm"], expected["mechanism_area_cm2_rounded"]):
        assert abs(result["thickness_mm"] - h) <= TOL
        assert abs(result["lateral_area_cm2"] - area) < .0051
    verification = {
        "schema_version": "1.0", "specification_sha256": EXPECTED_SPEC_SHA256,
        "inputs_sha256": spec["inputs_sha256"],
        "code_sha256": sha256(Path(__file__)),
        "scope": "Postprocessing only; minimum-thickness constrained feasibility within the sampled family. Hypothetical h_min alone is not sufficient physical feasibility.",
        "uncertainty_status": "Inherited estimated numerical brackets, not certified enclosures or biological prediction intervals.",
        "maximum_rows": len(maxima), "target_rows": len(selections), "mechanism_rows": len(mechanisms),
        "target_status_counts": {status: sum(r["status"] == status for r in selections) for status in [SELECTED, NOT_ATTAINED, UNRESOLVED]},
        "maximum_existing_frontier_difference": frontier_difference,
        "unconstrained_target_reconstructions": len(old_targets),
        "maximum_deliveries_nonincreasing_as_h_min_rises": True,
        "all_selection_competitors_checked": True,
        "negative_mutation_guard_checks_passed": negative_guard_checks,
        "maximum_point_optimizer_interval_overlap_count": max(r["other_maximizer_interval_overlap_count"] for r in maxima),
        "reviewer_constraint_checks": reviewer_checks,
        "mechanism_comparison": mechanisms,
    }
    traces = {"specification_sha256": EXPECTED_SPEC_SHA256,
              "input_map_sha256": sha256(root / "data/robustness_map.csv"),
              "design_estimates_by_set": designs_by_set,
              "constraint_selection_traces": selection_traces,
              "mechanism_design_estimates": mechanism_designs,
              "mechanism_selection_traces": mechanism_traces}
    # All data and classification validations precede scientific output writes.
    writecsv(root / "data/design_constraints_maxima.csv", maxima)
    writecsv(root / "data/design_constraints_targets.csv", selections)
    writecsv(root / "data/mechanism_comparison.csv", mechanisms)
    for name, value in [("design_constraints_verification.json", verification), ("design_constraints_selection_trace.json", traces)]:
        (root / "evidence" / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"maximum_rows": len(maxima), "target_rows": len(selections), "target_status_counts": verification["target_status_counts"], "reviewer_constraint_checks": reviewer_checks, "mechanisms": [{k: r[k] for k in ["mechanism_case", "thickness_mm", "lateral_area_cm2", "minimum_eta", "selected_Fo", "selected_Bi"]} for r in mechanisms]}, indent=2))


def self_test():
    def design(h, area, low, point, upper):
        return {"thickness_mm": h, "lateral_area_cm2": area, "minimum_eta_lower_estimate": low, "minimum_eta": point, "minimum_eta_upper_estimate": upper}
    # A cheaper interval overlap blocks minimum-area selection even if a more
    # expensive design demonstrably passes. The point estimate is not decisive.
    passing = design(.2, 200, .81, .82, .83)
    overlap = design(.3, 150, .79, .799, .801)
    assert choose_design([passing, overlap], .8)[0] == UNRESOLVED
    excluded = design(.4, 100, .77, .78, .79)
    status, candidate, trace = choose_design([passing, excluded], .8)
    assert status == SELECTED and candidate is passing and trace["lower_area_excluded_h_mm"] == [.4]
    assert choose_design([excluded], .8)[0] == NOT_ATTAINED
    assert choose_design([overlap], .8)[0] == UNRESOLVED
    boundary = design(.5, 80, .8, .8, .801)
    assert choose_design([boundary], .8)[0] == SELECTED
    boundary_fail = design(.6, 70, .79, .799, .8)
    assert choose_design([passing, boundary_fail], .8)[0] == UNRESOLVED
    assert dimensionless({"D_m2_s": 3e-10, "P_m_s": "infinite"}, .75) == {"Fo": .96, "Bi": "infinite"}
    finite = dimensionless({"D_m2_s": 1e-10, "P_m_s": 1e-6}, .3)
    assert abs(finite["Fo"] - 2) < TOL and abs(finite["Bi"] - 3) < TOL
    print("Synthetic classification, strict exclusion, equality and SI-unit checks passed; no scientific map was read.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--reference-release", type=Path,
                        help="Explicit regenerated-input mode against an exact verified original release")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        main(reference_release=args.reference_release)
