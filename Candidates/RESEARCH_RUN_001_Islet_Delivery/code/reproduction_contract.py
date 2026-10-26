"""Exact release integrity and separately specified numerical regeneration checks.

This module uses no transport solver. Every numerical comparison rule is listed
in the frozen public contract. It reconstructs the design decisions from each
operand's own map; a tolerated floating-point change cannot change a decision.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation
from itertools import product
import csv
import hashlib
import json
import math
import platform
import sys

EXPECTED_CONTRACT_SHA256 = "b02f72dec758f6b8b6d969495585ae22346df8c12a01ef9d76bebfc5118eff17"
FROZEN_SPECS = {
    "model_specification.json": "e1a5f46cdddaa4fbf75dc2745bbd8303ff4c8b81ea99cfccdd49ab91da9038bc",
    "robustness_specification.json": "3a2013c3c6adfb42123b6858e9755c73b2422f125c4d18f772bcec0fba67eb7c",
    "design_constraints_specification.json": "be2c3dbdc19b3d63397f87f3ef125929987e01a23658088c57c3f46151416689",
}
TRANSPORT_TABLES = ["data/robustness_map.csv", "data/robustness_frontier.csv", "data/robustness_targets.csv"]
# These are actual bounded fractions, not every field sharing the fraction
# tolerance profile. Signed differences and residuals deliberately stay signed.
FRACTION_FIELDS = set("""
eta eta15 eta30 eta60 eta15_truncation_lower eta30_truncation_lower eta60_truncation_lower
eta_achieved eta_refined eta_original eta_lower_estimate eta_upper_estimate
eta_source_maintained_until_deadline fixed_30min_pulse_fraction_recovered
fixed_pulse_delivered_fraction retained_fraction_of_total_pulse ideal_IEQ_reference_volume_fraction external_flux_normalized
minimum_eta minimum_eta_lower_estimate minimum_eta_upper_estimate maximum_worst_eta
maximum_worst_eta_lower_estimate maximum_worst_eta_upper_estimate eta_at_nominal_h
eta_lower_at_nominal_h eta_upper_at_nominal_h next_lower_area_eta next_lower_area_eta_upper_estimate
max_upper_among_all_lower_area_competitors map_eta modal256_512_eta modal512_1024_eta
FV160_560_eta FV320_1120_eta eta30_continuum_truncated eta30_finest_FV estimated_interval_eta
reflecting_ends_eta30 inventory_fraction_at_shutoff fraction_recovered_120min_after_shutoff
instant_uniform_initial_inventory_fraction_delivered_by30min constant_uniform_production_fraction_delivered_by30min
maximum_eta maximum_lower maximum_upper minimum_radial_modal_weight radial_modal_weight_sum
axial_modal_weight_sum weight_sum min_weight min_radial_weight_sum
""".split())


class ComparisonError(ValueError):
    """A release, schema, numerical, or decision requirement was violated."""


def require(condition, message):
    if not condition:
        raise ComparisonError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    def nonfinite(value):
        raise ComparisonError(f"Nonfinite JSON constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal,
                      object_pairs_hook=unique_object, parse_constant=nonfinite)


def load_contract(root):
    path = Path(root) / "reproduction_comparison_specification.json"
    require(sha256(path) == EXPECTED_CONTRACT_SHA256, "Frozen regeneration comparison contract changed")
    return read_json(path)


def verify_reference(root):
    """Verify supplied bytes before they serve as the comparison reference."""
    root = Path(root).resolve()
    from verify_manifest import verify
    verify(root)
    contract = load_contract(root)
    for name, digest in FROZEN_SPECS.items():
        require(sha256(root / name) == digest, f"Frozen scientific specification changed: {name}")
    frozen = read_json(root / "design_constraints_specification.json")
    for name, digest in frozen["inputs_sha256"].items():
        require(sha256(root / name) == digest, f"Bound original reference input changed: {name}")
    return contract


def decimal_number(value, where):
    require(type(value) in (str, int, float, Decimal), f"Wrong numeric type at {where}")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ComparisonError(f"Malformed number at {where}: {value!r}") from exc
    require(number.is_finite() and math.isfinite(float(number)), f"Nonfinite number at {where}")
    return number


def field_rule(schema, raw, field):
    key_text = "|".join(raw[k] for k in schema["keys"])
    return schema.get("field_overrides_by_key", {}).get(key_text, {}).get(field, schema["fields"][field])


def parse_cell(value, rule, where):
    if rule["type"] == "string":
        require(value in rule["allowed_values"], f"Unexpected category at {where}: {value!r}")
        return value
    if value == "":
        require(rule.get("allow_blank", False), f"Missing numeric value at {where}")
        return value
    if value == "infinite":
        require(rule.get("allow_infinite", False), f"Unexpected infinite sentinel at {where}")
        return value
    return decimal_number(value, where)


def load_csv(path, schema):
    """Strict CSV parser; both reference and generated data use the same schema."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        require(header == schema["headers"], f"Missing, extra, duplicate, or reordered headers: {path}")
        require(len(set(header)) == len(header), f"Duplicate headers: {path}")
        records = {}
        for line, values in enumerate(reader, 2):
            require(len(values) == len(header), f"Malformed/blank CSV row at {path}:{line}")
            raw = dict(zip(header, values))
            row = {field: parse_cell(raw[field], field_rule(schema, raw, field), f"{path}:{line}:{field}") for field in header}
            key = tuple(row[field] for field in schema["keys"])
            require(key not in records, f"Duplicate row key at {path}:{line}: {key}")
            records[key] = (row, raw)
    require(len(records) == schema["row_count"], f"Wrong row count in {path}: {len(records)}")
    return records


def compare_number(a, b, profile, where, contract):
    rule = contract["numeric_profiles"][profile]
    da, db = decimal_number(a, where), decimal_number(b, where)
    if profile == "exact_number":
        require(da == db, f"Exact numerical identity changed at {where}: {a} -> {b}")
    else:
        allowed = Decimal(str(rule["atol"])) + Decimal(str(rule["rtol"])) * max(abs(da), abs(db))
        require(abs(da - db) <= allowed, f"Numerical tolerance exceeded at {where}: delta={abs(da-db)}, allowed={allowed}")
    return float(abs(da - db))


def compare_csv(reference, generated, name, contract):
    schema = contract["csv"][name]
    before = load_csv(Path(reference) / name, schema)
    after = load_csv(Path(generated) / name, schema)
    require(set(before) == set(after), f"Missing or extra row keys: {name}")
    drift = {}
    for key, (left, raw_left) in before.items():
        right, raw_right = after[key]
        for field in schema["headers"]:
            a, b = left[field], right[field]
            rule = field_rule(schema, raw_left, field)
            if isinstance(a, Decimal) and isinstance(b, Decimal):
                delta = compare_number(str(a), str(b), rule["profile"], f"{name}:{key}:{field}", contract)
                old = drift.get(field)
                if old is None or delta > old["maximum_absolute_difference"]:
                    drift[field] = {"maximum_absolute_difference": delta, "at_key": [str(x) for x in key], "profile": rule["profile"]}
            else:
                require(type(a) is type(b) and a == b, f"Exact category/blank/sentinel changed at {name}:{key}:{field}")
    return {"rows": len(before), "fields_with_nonzero_drift": {k: v for k, v in drift.items() if v["maximum_absolute_difference"] > 0}}


def runtime_environment():
    from importlib.metadata import version
    return {"python": platform.python_version(), "numpy": version("numpy"),
            "scipy": version("scipy"), "matplotlib": version("matplotlib"), "platform": platform.platform()}


def json_kind(value):
    if value is None:
        return "null"
    return {bool: "bool", int: "integer", float: "number", Decimal: "number", str: "string"}.get(type(value))


def compare_json(reference, generated, name, contract):
    schema = contract["json"][name]
    left, right = read_json(Path(reference) / name), read_json(Path(generated) / name)
    drift = {}
    metadata = {}

    def walk(a, b, path=()):
        pattern = "/" + "/".join(path)
        special = schema.get("validated_metadata_exceptions", {}).get(pattern)
        if special:
            if special == "runtime_environment":
                require(type(a) is dict and type(b) is dict and set(a) == set(b) == set(runtime_environment()), f"Malformed runtime metadata: {name}")
                require(all(type(v) is str and bool(v) for v in a.values()), f"Invalid reference environment: {name}")
                require(b == runtime_environment(), f"Generated environment does not match actual runtime: {name}")
            elif special == "actual_generated_code_sha256":
                require(type(a) is str and len(a) == 64, f"Invalid original code hash: {name}")
                require(b == sha256(Path(generated) / "code/design_constraints.py"), "Generated code hash is not actual isolated code")
                require(sha256(Path(generated) / "code/design_constraints.py") == sha256(Path(reference) / "code/design_constraints.py"), "Isolated code differs from verified release code")
            elif special == "actual_generated_map_sha256":
                require(a == sha256(Path(reference) / "data/robustness_map.csv"), "Reference map evidence hash is invalid")
                require(b == sha256(Path(generated) / "data/robustness_map.csv"), "Generated map evidence hash is not actual generated data")
            else:
                raise ComparisonError(f"Unknown metadata rule: {special}")
            metadata[pattern] = {"reference": a, "generated": b, "validation": special}
            return
        if type(a) is dict:
            require(type(b) is dict and set(a) == set(b), f"JSON field set/type mismatch: {name}:{pattern}")
            for key in a:
                walk(a[key], b[key], path + (key,))
        elif type(a) is list:
            require(type(b) is list and len(a) == len(b), f"JSON list length/type mismatch: {name}:{pattern}")
            for av, bv in zip(a, b):
                walk(av, bv, path + ("*",))
        else:
            rule = schema["leaf_rules"].get(pattern)
            require(rule is not None, f"Unspecified JSON field: {name}:{pattern}")
            ka, kb = json_kind(a), json_kind(b)
            require(ka in rule["types"] and kb == ka, f"JSON type mismatch: {name}:{pattern}")
            if ka in ("integer", "number"):
                delta = compare_number(a, b, rule["profile"], f"{name}:{pattern}", contract)
                drift[pattern] = max(drift.get(pattern, 0), delta)
            else:
                require(a == b, f"Exact JSON value changed: {name}:{pattern}")
    walk(left, right)
    return {"fields_with_nonzero_drift": {k: v for k, v in drift.items() if v > 0}, "validated_metadata": metadata}


def numeric_rows(root, name, contract):
    records = load_csv(Path(root) / name, contract["csv"][name])
    return [dict(row) for row, _ in records.values()]


def canonical_signature(value):
    return json.dumps(value, sort_keys=True, default=lambda v: format(v.normalize(), "f") if type(v) is Decimal else str(v))


def close_value(a, b, where, contract, profile="fraction"):
    compare_number(a, b, profile, where, contract)


def summarize_designs(rows):
    """Independent finite-scenario aggregation; no production module imported."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["thickness_mm"], []).append(row)
    result = []
    for h in sorted(grouped):
        group = grouped[h]
        worst = min(group, key=lambda r: r["eta"])
        result.append({"h": h, "eta": min(r["eta"] for r in group),
                       "lower": min(r["eta_lower_estimate"] for r in group),
                       "upper": min(r["eta_upper_estimate"] for r in group),
                       "area": worst["lateral_area_cm2"], "worst": (worst["D_m2_s"], worst["P_m_s"], worst["end_condition"])})
    return result


def select_design(designs, target):
    passing = [r for r in designs if r["lower"] >= target]
    chosen = min(passing, key=lambda r: (r["area"], r["h"])) if passing else None
    competitors = [r for r in designs if chosen is None or r["area"] < chosen["area"]]
    uncertain = [r for r in competitors if r["upper"] >= target]
    status = "selected" if chosen and not uncertain else "not_attained" if max(r["upper"] for r in designs) < target else "unresolved"
    return {"status": status, "h": chosen["h"] if chosen else None,
            "passing": [r["h"] for r in passing], "excluded": [r["h"] for r in competitors if r["upper"] < target],
            "uncertain": [r["h"] for r in uncertain]}, chosen


def decision_audit(root, contract, complete=False):
    """Reconstruct all comparisons; returns discrete identities, never rounded eta."""
    root = Path(root)
    rows = numeric_rows(root, "data/robustness_map.csv", contract)
    spec = read_json(root / "robustness_specification.json")
    identities = set(product([Decimal(i) / 100 for i in range(10, 101)], spec["scenarios"]["D_m2_s"],
                             spec["scenarios"]["outer_P_m_s"], spec["scenarios"]["ends"], [15., 30., 60.]))
    actual = {(r["thickness_mm"], r["D_m2_s"], r["P_m_s"], r["end_condition"], r["deadline_min"]) for r in rows}
    require(actual == identities, "Scenario/grid/deadline membership changed")
    predicates = []
    for row in sorted(rows, key=lambda r: (r["thickness_mm"], r["D_m2_s"], str(r["P_m_s"]), r["end_condition"], r["deadline_min"])):
        require(0 <= row["eta_lower_estimate"] <= row["eta"] <= row["eta_upper_estimate"] <= 1, "Invalid map numerical bracket/fraction range")
        require(row["omitted_tail_bound_eta"] >= 0 and row["floating_guard_eta"] >= 0, "Negative map tail/guard")
        for target in map(Decimal, [".5", ".6", ".7", ".8", ".9"]):
            predicates.append((row["eta_lower_estimate"] >= target, row["eta_upper_estimate"] < target))
    supplied_frontier = numeric_rows(root, "data/robustness_frontier.csv", contract)
    supplied_targets = numeric_rows(root, "data/robustness_targets.csv", contract)
    signature = {"raw_predicates": predicates, "robust_targets": [], "constraint_targets": [], "maximizers": [], "mechanisms": []}
    grouped_sets = {}
    for name, description in spec["sets"].items():
        members = set(product(description["D"], description["P"], description["ends"]))
        for deadline in [15, 30, 60]:
            chosen_rows = [r for r in rows if r["deadline_min"] == deadline and (r["D_m2_s"], r["P_m_s"], r["end_condition"]) in members]
            require(len(chosen_rows) == 91 * len(members), "Invalid finite scenario-set size")
            designs = summarize_designs(chosen_rows)
            grouped_sets[name, deadline] = designs
            for d in designs:
                match = [r for r in supplied_frontier if r["scenario_set"] == name and r["deadline_min"] == deadline and r["thickness_mm"] == d["h"]]
                require(len(match) == 1, "Missing set frontier row")
                r = match[0]
                for field, key in [("minimum_eta", "eta"), ("minimum_eta_lower_estimate", "lower"), ("minimum_eta_upper_estimate", "upper")]:
                    close_value(r[field], d[key], "Set frontier does not aggregate own map", contract)
                require((r["worst_D_m2_s"], r["worst_P_m_s"], r["worst_end_condition"]) == d["worst"], "Set frontier limiting scenario changed")
            for target in map(Decimal, [".5", ".6", ".7", ".8", ".9"]):
                outcome, selected = select_design(designs, target)
                match = [r for r in supplied_targets if r["scenario_set"] == name and r["deadline_min"] == deadline and r["target_eta"] == target]
                require(len(match) == 1, "Missing robust target row")
                r = match[0]
                expected_status = {"selected": "minimum within grid and discrete scenario set", "not_attained": "not attained in grid"}.get(outcome["status"])
                require(expected_status is not None and r["status"] == expected_status, "Robust target status inconsistent with own map")
                require(r["thickness_mm"] == (selected["h"] if selected else ""), "Robust selected thickness inconsistent with own map")
                require(r["unresolved_competitors"] == len(outcome["uncertain"]), "Robust uncertainty count mismatch")
                signature["robust_targets"].append((name, deadline, target, outcome))
    if not complete:
        return signature
    maxima = numeric_rows(root, "data/design_constraints_maxima.csv", contract)
    constrained = numeric_rows(root, "data/design_constraints_targets.csv", contract)
    mechanisms = numeric_rows(root, "data/mechanism_comparison.csv", contract)
    for name in spec["sets"]:
        for idx in range(10, 101):
            minimum = Decimal(idx) / 100
            designs = [r for r in grouped_sets[name, 30] if r["h"] >= minimum]
            best = max(designs, key=lambda r: (r["eta"], -r["area"]))
            matched = [r for r in maxima if r["scenario_set"] == name and r["h_min_mm"] == minimum]
            require(len(matched) == 1, "Missing constrained maximum")
            r = matched[0]
            require(r["point_maximizer_thickness_mm"] == best["h"], "Constrained maximizer inconsistent with own map")
            for field, expected in [("maximum_worst_eta", best["eta"]), ("maximum_worst_eta_lower_estimate", max(d["lower"] for d in designs)), ("maximum_worst_eta_upper_estimate", max(d["upper"] for d in designs))]:
                close_value(r[field], expected, "Constrained maximum does not aggregate own map", contract)
            overlaps = [d["h"] for d in designs if d is not best and d["upper"] >= best["lower"]]
            require(r["eligible_design_count"] == len(designs) and r["other_maximizer_interval_overlap_count"] == len(overlaps), "Constrained maximum counts inconsistent")
            signature["maximizers"].append((name, minimum, best["h"], overlaps))
            for target in map(Decimal, [".8", ".9"]):
                outcome, selected = select_design(designs, target)
                match = [r for r in constrained if r["scenario_set"] == name and r["h_min_mm"] == minimum and r["target_eta"] == target]
                require(len(match) == 1, "Missing constrained target")
                validate_constraint_row(match[0], outcome, selected, len(designs))
                signature["constraint_targets"].append((name, minimum, target, outcome))
    cases = read_json(root / "design_constraints_specification.json")["mechanism_comparison"]["cases"]
    for case in cases:
        designs = summarize_designs([r for r in rows if r["deadline_min"] == 30 and (r["D_m2_s"], r["P_m_s"], r["end_condition"]) == (case["D_m2_s"], case["P_m_s"], case["ends"])])
        outcome, selected = select_design(designs, Decimal(".8"))
        match = [r for r in mechanisms if r["mechanism_case"] == case["name"]]
        require(len(match) == 1, "Missing mechanism comparison")
        validate_constraint_row(match[0], outcome, selected, len(designs))
        signature["mechanisms"].append((case["name"], outcome))
    original = numeric_rows(root, "data/dose_area_frontier.csv", contract)
    targets = numeric_rows(root, "data/frontier_targets.csv", contract)
    signature["original_frontier_predicates"] = []
    for deadline in [15, 30, 60]:
        for target in map(Decimal, [".5", ".6", ".7", ".8", ".9"]):
            signature["original_frontier_predicates"].append([(r[f"eta{deadline}_truncation_lower"] >= target, r[f"eta{deadline}"] < target) for r in original])
            for r in original:
                require(0 <= r[f"eta{deadline}_truncation_lower"] <= r[f"eta{deadline}"] <= 1, "Invalid original frontier bracket")
            passing = [r for r in original if r[f"eta{deadline}_truncation_lower"] >= target]
            selected = min(passing, key=lambda r: r["side_exchange_area_cm2"]) if passing else None
            match = [r for r in targets if r["deadline_min"] == deadline and r["target_eta"] == target]
            require(len(match) == 1 and match[0]["thickness_mm"] == (selected["thickness_mm"] if selected else ""), "Original frontier selection inconsistent")
            require(match[0]["status"] == ("grid minimum area" if selected else "not attained in grid"), "Original frontier status inconsistent")
            if selected:
                require(all(r[f"eta{deadline}"] < target for r in original if r["side_exchange_area_cm2"] < selected["side_exchange_area_cm2"]), "Original lower-area exclusion failed")
    return signature


def validate_constraint_row(row, outcome, selected, count):
    labels = {"selected": "minimum within constrained grid and discrete scenario set", "not_attained": "not attained within constrained grid", "unresolved": "unresolved numerical overlap"}
    require(row["status"] == labels[outcome["status"]], "Constrained/mechanism status inconsistent with own map")
    require(row["thickness_mm"] == (selected["h"] if outcome["status"] == "selected" else ""), "Constrained/mechanism selected h inconsistent")
    require(row["eligible_design_count"] == count, "Eligible-design count mismatch")
    expected_exclusions = len(outcome["excluded"]) if selected else 0
    require(row["lower_area_competitors_excluded"] == expected_exclusions, "Lower-area exclusion count mismatch")
    require(row["unresolved_competitor_count"] == len(outcome["uncertain"]), "Unresolved-competitor count mismatch")


def scientific_invariants(root, contract):
    """Original solver checks remain binding independently of drift tolerances."""
    for name in contract["json"]:
        obj = read_json(Path(root) / name)
        def walk(value, key=""):
            if type(value) is dict:
                for k, v in value.items():
                    walk(v, k)
            elif type(value) is list:
                for v in value:
                    walk(v, key)
            elif type(value) in (int, float, Decimal):
                require(math.isfinite(value), f"Nonfinite scientific evidence: {name}:{key}")
                if key in FRACTION_FIELDS:
                    require(0 <= value <= 1, f"Fraction outside [0,1]: {name}:{key}")
                if any(word in key for word in ("tail", "weight", "uncertainty")):
                    require(value >= 0, f"Negative tail/weight/uncertainty: {name}:{key}")
        walk(obj)
    primary = read_json(Path(root) / "evidence/numerical_verification.json")
    require(abs(primary["eta30_finest_FV"] - primary["eta30_continuum_truncated"]) < Decimal(".005"), "Original independent-method limit failed")
    require(0 <= primary["estimated_numerical_uncertainty_eta"] < Decimal(".002"), "Original uncertainty limit failed")
    lo, hi = primary["estimated_interval_eta"]
    require(0 <= lo <= primary["eta30_continuum_truncated"] <= hi <= 1, "Invalid primary estimated interval")
    for row in primary["field_audits"]:
        require(row["min_concentration_source_seconds"] >= Decimal("-1e-8"), "Original positivity limit failed")
        if row["steady"]:
            require(abs(row["boundary_flux_over_source_rate"] - 1) < Decimal("1e-7"), "Original steady flux limit failed")
        else:
            for field in ["independent_face_integral_mass_error_source_seconds", "flux_spectral_discrepancy", "inventory_spectral_discrepancy"]:
                require(abs(row[field]) < Decimal("1e-7"), f"Original conservation/identity limit failed: {field}")
    robust = read_json(Path(root) / "evidence/robustness_verification.json")
    require(robust["max_FV_modal_difference_eta"] < Decimal(".0002"), "Original Robin independent-method limit failed")
    for row in robust["quadrature_checks"]:
        require(row["sum_absolute_weight_error"] < Decimal("1e-8"), "Original Robin quadrature limit failed")
    for name in contract["csv"]:
        rows = numeric_rows(root, name, contract)
        for row in rows:
            for field, value in row.items():
                if type(value) in (float, Decimal) and field in FRACTION_FIELDS:
                    require(0 <= value <= 1, f"Fraction outside [0,1]: {name}:{field}")
                if type(value) in (float, Decimal) and any(term in field for term in ("tail", "truncation_eta_bound", "floating_guard")):
                    require(value >= 0, f"Negative tail/guard: {name}:{field}")
    return "original limits and numerical-domain checks passed"


def compare_transport_inputs(reference, generated):
    """Gate explicit regenerated-input mode before constraint postprocessing."""
    reference, generated = Path(reference).resolve(), Path(generated).resolve()
    require(reference != generated, "Regenerated-input mode requires a separate output directory")
    contract = verify_reference(reference)
    require(sha256(generated / "reproduction_comparison_specification.json") == EXPECTED_CONTRACT_SHA256, "Isolated comparison contract differs")
    for name, digest in FROZEN_SPECS.items():
        require(sha256(generated / name) == digest, f"Isolated frozen specification changed: {name}")
    comparisons = {name: compare_csv(reference, generated, name, contract) for name in TRANSPORT_TABLES}
    a, b = decision_audit(reference, contract), decision_audit(generated, contract)
    require(a == b, "A regeneration drift changed a transport eligibility/exclusion/selection predicate")
    return {"mode": "exact original reference integrity plus regenerated numerical equivalence",
            "contract_sha256": EXPECTED_CONTRACT_SHA256,
            "reference_input_sha256": {n: sha256(reference / n) for n in TRANSPORT_TABLES},
            "generated_input_sha256": {n: sha256(generated / n) for n in TRANSPORT_TABLES},
            "tables": comparisons, "exact_transport_decision_signature_sha256": hashlib.sha256(canonical_signature(a).encode()).hexdigest()}


def compare_regenerated_text(reference, generated, name, contract):
    """Compare allowed regenerated text with only CRLF/LF equivalence.

    Reading bytes and decoding explicitly preserves lone CR and BOM; universal
    newline translation, whitespace stripping and Unicode normalization are
    deliberately absent. Release integrity is verified separately beforehand.
    """
    require(name in contract["regenerated_text_exact"], f"Unspecified regenerated narrative: {name}")
    require(contract["regenerated_text_policy"] == {
        "encoding": "utf-8", "decoding_errors": "strict",
        "newline_normalization": "CRLF-to-LF-only", "all_other_content": "exact",
    }, "Unsupported regenerated text comparison policy")
    raw = [(Path(root) / name).read_bytes() for root in (reference, generated)]
    try:
        text = [value.decode("utf-8", errors="strict").replace("\r\n", "\n") for value in raw]
    except UnicodeDecodeError as exc:
        raise ComparisonError(f"Invalid UTF-8 in regenerated narrative comparison: {name}") from exc
    require(text[0] == text[1], f"Regenerated narrative changed: {name}")
    return {"policy": "strict UTF-8; CRLF-to-LF-only; all other content exact",
            "reference_sha256": hashlib.sha256(raw[0]).hexdigest(),
            "generated_sha256": hashlib.sha256(raw[1]).hexdigest(),
            "byte_identical": raw[0] == raw[1]}


def compare_reproduction(reference, generated):
    reference, generated = Path(reference).resolve(), Path(generated).resolve()
    contract = verify_reference(reference)
    csv_results = {name: compare_csv(reference, generated, name, contract) for name in contract["csv"]}
    json_results = {name: compare_json(reference, generated, name, contract) for name in contract["json"]}
    a, b = decision_audit(reference, contract, True), decision_audit(generated, contract, True)
    require(a == b, "A regenerated value changed a discrete decision or threshold predicate")
    scientific_invariants(reference, contract)
    scientific_invariants(generated, contract)
    text_results = {name: compare_regenerated_text(reference, generated, name, contract)
                    for name in contract["regenerated_text_exact"]}
    for name in contract["required_figures"]:
        require((generated / name).is_file() and (generated / name).stat().st_size > 0, f"Missing fresh figure: {name}")
    return {"status": "PASS", "contract_sha256": EXPECTED_CONTRACT_SHA256,
            "comparison_scope": "Numerical equivalence and exact decisions; not byte identity, formal interval certification or experimental validation",
            "csv": csv_results, "json": json_results, "text": text_results,
            "exact_decision_signature_sha256": hashlib.sha256(canonical_signature(a).encode()).hexdigest(),
            "decision_counts": {"robust_targets": 45, "constraint_maxima": 273, "constraint_targets": 546, "mechanisms": 5, "original_targets": 15},
            "runtime_environment": runtime_environment()}
