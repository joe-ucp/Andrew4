"""Hostile regression tests for release integrity and regeneration equivalence.

Run: python code/test_reproduction_contract.py
All mutations use temporary public-package fixtures. No PDE sweep is repeated.
The fixture clone is test data, not asserted to be a fresh scientific rebuild.
"""
from pathlib import Path
from contextlib import contextmanager, redirect_stdout
from decimal import Decimal
import csv
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

import reproduction_contract as rc

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def changed(path, transform):
    original = path.read_bytes()
    try:
        path.write_bytes(transform(original))
        yield
    finally:
        path.write_bytes(original)


def json_edit(function):
    def transform(raw):
        value = json.loads(raw)
        function(value)
        return json.dumps(value, indent=2).encode()
    return transform


def csv_edit(function):
    def transform(raw):
        records = list(csv.reader(io.StringIO(raw.decode())))
        function(records)
        stream = io.StringIO(newline="")
        csv.writer(stream).writerows(records)
        return stream.getvalue().encode()
    return transform


def set_cell(records, field, value, index=1):
    records[index][records[0].index(field)] = str(value)


def refresh_fixture_environment(path):
    """Replace only the environment JSON span in a generated test fixture."""
    raw = path.read_bytes().decode("utf-8")
    marker = '"environment"'
    start = raw.index(":", raw.index(marker) + len(marker)) + 1
    while raw[start].isspace():
        start += 1
    _, end = json.JSONDecoder().raw_decode(raw, start)
    replacement = json.dumps(rc.runtime_environment(), ensure_ascii=True)
    path.write_bytes((raw[:start] + replacement + raw[end:]).encode("utf-8"))


class ReproductionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="islet_reproduction_tests_")
        cls.base = Path(cls.temp.name)
        cls.reference = cls.base / "reference"
        cls.reference.mkdir()
        manifest = json.loads((ROOT / "artifact_manifest.json").read_text())
        names = {row["path"] for row in manifest["artifacts"]}
        names.update(["reproduction_comparison_specification.json", "code/reproduction_contract.py", "code/test_reproduction_contract.py"])
        for name in sorted(names):
            destination = cls.reference / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        manifest["artifacts"] = [{"path": name, "sha256": rc.sha256(cls.reference / name),
                                  "size_bytes": (cls.reference / name).stat().st_size,
                                  "relationship": "temporary test fixture"} for name in sorted(names)]
        (cls.reference / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        cls.generated = cls.base / "generated_fixture"
        shutil.copytree(cls.reference, cls.generated)
        path = cls.generated / "evidence/design_constraints_verification.json"
        value = json.loads(path.read_text())
        value["code_sha256"] = rc.sha256(cls.generated / "code/design_constraints.py")
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        cls.contract = rc.load_contract(cls.reference)
        cls.reference_environment_hashes = {}
        # A copied release is a test fixture, not a PDE rebuild. Refresh only
        # its generated environment objects for the runtime under test; the
        # historical reference objects and bytes stay unchanged.
        for name in ("evidence/numerical_verification.json", "evidence/numerical_summary.txt"):
            cls.reference_environment_hashes[name] = rc.sha256(cls.reference / name)
            refresh_fixture_environment(cls.generated / name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def quiet(self, function, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            return function(*args, **kwargs)

    def compare_csv(self, name):
        return rc.compare_csv(self.reference, self.generated, name, self.contract)

    def test_00_untouched_records_and_full_decisions(self):
        result = self.quiet(rc.compare_reproduction, self.reference, self.generated)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["decision_counts"]["constraint_targets"], 546)

    def test_generated_fixture_runtime_refresh_preserves_reference(self):
        for name, digest in self.reference_environment_hashes.items():
            self.assertEqual(rc.sha256(self.reference / name), digest)
            self.assertEqual((self.reference / name).read_bytes(), (ROOT / name).read_bytes())
            before = rc.read_json(self.reference / name)
            after = rc.read_json(self.generated / name)
            self.assertEqual(after.pop("environment"), rc.runtime_environment())
            before.pop("environment")
            self.assertEqual(before, after)

    def test_wrong_generated_runtime_is_rejected(self):
        for name in self.reference_environment_hashes:
            mutate = lambda x: x["environment"].__setitem__("platform", "deliberately wrong runtime")
            with changed(self.generated / name, json_edit(mutate)):
                with self.assertRaisesRegex(rc.ComparisonError, "does not match actual runtime"):
                    rc.compare_json(self.reference, self.generated, name, self.contract)

    def test_foreign_historical_environment_needs_only_generated_refresh(self):
        historical, current = self.base / "foreign_historical", self.base / "current_runtime"
        for folder in (historical, current):
            (folder / "evidence").mkdir(parents=True)
        for name in self.reference_environment_hashes:
            raw = (self.reference / name).read_bytes()
            mutate = lambda x: x["environment"].__setitem__("platform", "historical foreign platform")
            (historical / name).write_bytes(json_edit(mutate)(raw))
            shutil.copyfile(historical / name, current / name)
            original_digest = rc.sha256(historical / name)
            with self.assertRaisesRegex(rc.ComparisonError, "does not match actual runtime"):
                rc.compare_json(historical, current, name, self.contract)
            refresh_fixture_environment(current / name)
            result = rc.compare_json(historical, current, name, self.contract)
            self.assertEqual(rc.sha256(historical / name), original_digest)
            self.assertEqual(result["validated_metadata"]["/environment"]["reference"]["platform"],
                             "historical foreign platform")
            self.assertEqual(result["validated_metadata"]["/environment"]["generated"], rc.runtime_environment())
            before, after = rc.read_json(historical / name), rc.read_json(current / name)
            before.pop("environment")
            after.pop("environment")
            self.assertEqual(before, after)

    def test_crlf_lf_regenerated_narratives_pass_full_comparison(self):
        # Give each generated narrative the opposite newline convention from
        # its immutable reference, and exercise the complete comparison path.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in self.contract["regenerated_text_exact"]:
                original = (self.reference / name).read_bytes()
                lf = original.replace(b"\r\n", b"\n")
                other = lf if b"\r\n" in original else lf.replace(b"\n", b"\r\n")
                self.assertNotEqual(original, other)
                stack.enter_context(changed(self.generated / name, lambda raw, value=other: value))
            result = self.quiet(rc.compare_reproduction, self.reference, self.generated)
            self.assertEqual(result["status"], "PASS")
            for row in result["text"].values():
                self.assertFalse(row["byte_identical"])
                self.assertNotEqual(row["reference_sha256"], row["generated_sha256"])

    def test_other_narrative_changes_remain_significant(self):
        mutations = {
            "changed content": lambda raw: raw + b"changed content",
            "BOM": lambda raw: b"\xef\xbb\xbf" + raw,
            "lone CR": lambda raw: raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r", 1),
            "trailing space": lambda raw: raw + b" ",
            "leading space": lambda raw: b" " + raw,
            "Unicode content": lambda raw: raw + "\u00e9".encode("utf-8"),
        }
        for name in self.contract["regenerated_text_exact"]:
            for label, mutate in mutations.items():
                with self.subTest(name=name, change=label):
                    with changed(self.generated / name, mutate):
                        with self.assertRaisesRegex(rc.ComparisonError, "Regenerated narrative changed"):
                            rc.compare_regenerated_text(self.reference, self.generated, name, self.contract)

    def test_invalid_utf8_narrative_is_rejected(self):
        for name in self.contract["regenerated_text_exact"]:
            with changed(self.generated / name, lambda raw: raw + b"\xff"):
                with self.assertRaisesRegex(rc.ComparisonError, "Invalid UTF-8"):
                    rc.compare_regenerated_text(self.reference, self.generated, name, self.contract)

    def test_small_actual_scale_drift_is_accepted_and_recorded(self):
        name = "data/robustness_map.csv"
        def perturb(records):
            column = records[0].index("eta")
            records[1][column] = str(Decimal(records[1][column]) + Decimal("5.6e-14"))
        with changed(self.generated / name, csv_edit(perturb)):
            result = self.quiet(rc.compare_transport_inputs, self.reference, self.generated)
            drift = result["tables"][name]["fields_with_nonzero_drift"]["eta"]["maximum_absolute_difference"]
            self.assertAlmostEqual(drift, 5.6e-14, delta=1e-27)
            self.assertNotEqual(result["reference_input_sha256"][name], result["generated_input_sha256"][name])

    def test_beyond_tolerance_fails(self):
        name = "data/robustness_map.csv"
        with changed(self.generated / name, csv_edit(lambda r: set_cell(r, "eta", ".7"))):
            with self.assertRaisesRegex(rc.ComparisonError, "tolerance exceeded"):
                self.compare_csv(name)

    def test_nan_is_not_a_tolerance_value(self):
        name = "data/robustness_map.csv"
        with changed(self.generated / name, csv_edit(lambda r: set_cell(r, "eta", "NaN"))):
            with self.assertRaisesRegex(rc.ComparisonError, "Nonfinite"):
                self.compare_csv(name)

    def test_duplicate_missing_extra_and_blank_csv_rows(self):
        name = "data/robustness_map.csv"
        mutations = [lambda r: r.__setitem__(-1, r[1][:]), lambda r: r.pop(), lambda r: r.append(r[1][:]), lambda r: r.append([])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                with changed(self.generated / name, csv_edit(mutate)):
                    with self.assertRaises(rc.ComparisonError):
                        self.compare_csv(name)

    def test_duplicate_headers_and_extra_columns(self):
        name = "data/robustness_map.csv"
        for mutate in [lambda r: r[0].__setitem__(1, r[0][0]), lambda r: r[1].append("extra")]:
            with changed(self.generated / name, csv_edit(mutate)):
                with self.assertRaises(rc.ComparisonError):
                    self.compare_csv(name)

    def test_exact_selected_thickness_and_category(self):
        name = "data/robustness_targets.csv"
        for field, value in [("thickness_mm", "0.84000000000000000001"), ("status", "claimed new status")]:
            with changed(self.generated / name, csv_edit(lambda r: set_cell(r, field, value))):
                with self.assertRaises(rc.ComparisonError):
                    self.compare_csv(name)

    def test_json_exact_identity_does_not_round_to_float(self):
        name = "evidence/robustness_verification.json"
        raw = (self.generated / name).read_bytes()
        self.assertIn(b'"thickness_mm": 1.0', raw)
        with changed(self.generated / name, lambda b: b.replace(b'"thickness_mm": 1.0', b'"thickness_mm": 1.00000000000000000001', 1)):
            with self.assertRaisesRegex(rc.ComparisonError, "Exact numerical identity"):
                rc.compare_json(self.reference, self.generated, name, self.contract)

    def test_json_bool_integer_and_duplicate_key(self):
        name = "evidence/design_constraints_verification.json"
        with changed(self.generated / name, json_edit(lambda x: x.__setitem__("maximum_rows", True))):
            with self.assertRaisesRegex(rc.ComparisonError, "type mismatch"):
                rc.compare_json(self.reference, self.generated, name, self.contract)
        with changed(self.generated / name, lambda b: b.replace(b'"maximum_rows": 273,', b'"maximum_rows": 273, "maximum_rows": 273,', 1)):
            with self.assertRaisesRegex(rc.ComparisonError, "Duplicate JSON"):
                rc.compare_json(self.reference, self.generated, name, self.contract)

    def test_fraction_domain_applies_even_below_tolerance(self):
        name = "data/delivery_response.csv"
        with changed(self.generated / name, csv_edit(lambda r: set_cell(r, "fixed_pulse_delivered_fraction", "-5e-12"))):
            self.compare_csv(name)
            with self.assertRaisesRegex(rc.ComparisonError, "Fraction outside"):
                rc.scientific_invariants(self.generated, self.contract)

    def test_negative_tail_fails_even_below_tolerance(self):
        name = "data/robustness_map.csv"
        with changed(self.generated / name, csv_edit(lambda r: set_cell(r, "omitted_tail_bound_eta", "-1e-15"))):
            with self.assertRaisesRegex(rc.ComparisonError, "Negative"):
                rc.decision_audit(self.generated, self.contract)

    def test_normalized_pulse_flux_nonnegative(self):
        name = "data/delivery_response.csv"
        with changed(self.generated / name, csv_edit(lambda r: set_cell(r, "external_flux_normalized", "-5e-12"))):
            with self.assertRaisesRegex(rc.ComparisonError, "Fraction outside"):
                rc.scientific_invariants(self.generated, self.contract)

    def test_sub_tolerance_lower_and_upper_crossings_are_exact(self):
        # Synthetic decisions isolate the strict predicate rule; the field-level
        # drift is acceptable, while the decision signature is not equal.
        for field in ["lower", "upper"]:
            a = {"h": Decimal(".6"), "area": Decimal("100"), "eta": Decimal(".8"), "lower": Decimal(".79"), "upper": Decimal(".81")}
            b = dict(a)
            a[field] = Decimal(".8") - Decimal("2e-20")
            b[field] = Decimal(".8") + Decimal("2e-20")
            rc.compare_number(a[field], b[field], "fraction", "synthetic threshold", self.contract)
            sa, _ = rc.select_design([a], Decimal(".8"))
            sb, _ = rc.select_design([b], Decimal(".8"))
            self.assertNotEqual(sa, sb)
        # Specifically prove a cheap competitor crossing blocks a valid design.
        passing = {"h": Decimal(".2"), "area": Decimal("200"), "eta": Decimal(".82"), "lower": Decimal(".81"), "upper": Decimal(".83")}
        before = {"h": Decimal(".3"), "area": Decimal("100"), "eta": Decimal(".79"), "lower": Decimal(".78"), "upper": Decimal(".8") - Decimal("2e-20")}
        after = dict(before, upper=Decimal(".8") + Decimal("2e-20"))
        self.assertEqual(rc.select_design([passing, before], Decimal(".8"))[0]["status"], "selected")
        self.assertEqual(rc.select_design([passing, after], Decimal(".8"))[0]["status"], "unresolved")

    def test_original_bound_guard_and_frozen_spec_are_not_relaxed(self):
        import design_constraints as dc
        for name in ["data/robustness_map.csv", "design_constraints_specification.json"]:
            with changed(self.reference / name, lambda b: b + b"\n "):
                with self.assertRaises(RuntimeError):
                    dc.guarded_spec(self.reference)

    def test_generated_hash_metadata_must_hash_actual_bytes(self):
        name = "evidence/design_constraints_selection_trace.json"
        with changed(self.generated / name, json_edit(lambda x: x.__setitem__("input_map_sha256", "0" * 64))):
            with self.assertRaisesRegex(rc.ComparisonError, "actual generated"):
                rc.compare_json(self.reference, self.generated, name, self.contract)

    def test_manifest_guard_survives_python_optimization(self):
        with changed(self.reference / "README.md", lambda b: b + b"tampered"):
            result = subprocess.run([sys.executable, "-O", str(self.reference / "code/verify_manifest.py")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("PASS:", result.stdout)
            self.assertIn("Size mismatch", result.stderr)

    def test_manifest_duplicates_and_unsafe_paths(self):
        manifest = self.reference / "artifact_manifest.json"
        for mutate in [lambda x: x["artifacts"].append(dict(x["artifacts"][0])), lambda x: x["artifacts"][0].__setitem__("path", "../outside")]:
            with changed(manifest, json_edit(mutate)):
                with self.assertRaises(ValueError):
                    self.quiet(rc.verify_reference, self.reference)

    def test_fresh_output_has_no_inherited_scientific_files(self):
        module_spec = importlib.util.spec_from_file_location("isolated_wrapper_test", self.reference / "reproduce.py")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        target = self.base / "fresh_output"
        copied = module.prepare_output(target, self.contract)
        self.assertTrue(copied)
        for folder in ["data", "evidence", "figures", "manuscript"]:
            self.assertEqual(list((target / folder).iterdir()), [])
        with self.assertRaises(rc.ComparisonError):
            module.output_directory(target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
