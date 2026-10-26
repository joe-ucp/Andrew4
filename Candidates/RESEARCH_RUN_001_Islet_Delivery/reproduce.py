"""Verify supplied bytes, rebuild separately, and compare scientific results.

No network is used. Supplied release files remain unchanged; actual regenerated
values and a machine-readable comparison report are retained in a new directory.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))
from reproduction_contract import compare_reproduction, read_json, require, sha256, verify_reference


def output_directory(requested):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = (ROOT / "_reproduced" / f"{stamp}_{uuid.uuid4().hex[:8]}") if requested is None else Path(requested).expanduser().resolve()
    require(not target.exists(), f"Output directory must not exist: {target}")
    require(target != ROOT and not ROOT.is_relative_to(target), "Output cannot be the reference release or its ancestor")
    if target.is_relative_to(ROOT):
        require(target.relative_to(ROOT).parts[0] == "_reproduced", "Output inside the release must be under _reproduced")
    return target


def prepare_output(target, contract):
    manifest = read_json(ROOT / "artifact_manifest.json")
    declared = {r["path"] for r in manifest["artifacts"]}
    copied = {name for name in declared if name.startswith("code/") and name.endswith(".py") and len(Path(name).parts) == 2}
    copied.update(["model_specification.json", "robustness_specification.json", "design_constraints_specification.json", "reproduction_comparison_specification.json"])
    require(copied <= declared, "A required reproduction input is absent from the verified manifest")
    target.mkdir(parents=True, exist_ok=False)
    for folder in ["code", "logs", *contract["isolation"]["required_output_directories"]]:
        (target / folder).mkdir(exist_ok=True)
    for name in sorted(copied):
        shutil.copyfile(ROOT / name, target / name)
        require(sha256(ROOT / name) == sha256(target / name), f"Input copy mismatch: {name}")
    # No derived table, evidence, figure, narrative or document is copied.
    return {name: sha256(target / name) for name in sorted(copied)}


def run_script(target, name, arguments=()):
    log = target / "logs" / f"{Path(name).stem}.log"
    print(f"Rebuilding {name}; log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run([sys.executable, "-B", str(target / "code" / name), *map(str, arguments)], cwd=target, stdout=stream, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"Rebuild failed in {name}; see {log}")


def build_manuscript(target, contract):
    run_script(target, "build_manuscript.py")
    compiler = shutil.which("pdflatex")
    require(compiler is not None, "pdflatex is required for --manuscript; numerical comparison remains archived")
    tex_output = target / "logs" / "tex"
    tex_output.mkdir()
    for pass_number in (1, 2):
        log = target / "logs" / f"pdflatex_{pass_number}.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([compiler, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(tex_output), "paper.tex"], cwd=target / "manuscript", stdout=stream, stderr=subprocess.STDOUT)
        require(result.returncode == 0, f"LaTeX compilation failed; see {log}")
    shutil.copyfile(tex_output / "paper.pdf", target / "manuscript/paper.pdf")
    for name in contract["optional_manuscript_outputs"]:
        require((target / name).is_file() and (target / name).stat().st_size > 0, f"Missing fresh manuscript output: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", action="store_true", help="Also build Word, TeX and PDF in isolated output; requires document packages and pdflatex")
    parser.add_argument("--output", type=Path, help="New output directory, relative to cwd; default _reproduced/<unique>")
    args = parser.parse_args()
    # No output directory or solver is started before exact release integrity.
    contract = verify_reference(ROOT)
    original_manifest_hash = sha256(ROOT / "artifact_manifest.json")
    target = output_directory(args.output)
    copied = prepare_output(target, contract)
    report = {"status": "IN_PROGRESS", "reference_release": str(ROOT), "reference_manifest_sha256": original_manifest_hash,
              "output_directory": str(target), "copied_immutable_input_sha256": copied,
              "reference_policy": "Exact supplied bytes first; generated output compared separately; no reference-value substitution"}
    report_path = target / "reproduction_report.json"
    try:
        for script in ["reproduce.py", "source_accounting.py", "robustness.py"]:
            run_script(target, script)
        run_script(target, "design_constraints.py", ["--reference-release", ROOT])
        for script in ["revision_figures.py", "design_figures.py", "compose_paper.py"]:
            run_script(target, script)
        report["numerical_comparison"] = compare_reproduction(ROOT, target)
        if args.manuscript:
            build_manuscript(target, contract)
        for name, digest in copied.items():
            require(sha256(target / name) == digest, f"Isolated immutable input changed: {name}")
        require(sha256(ROOT / "artifact_manifest.json") == original_manifest_hash, "Reference manifest changed during reproduction")
        verify_reference(ROOT)
        report["generated_artifact_sha256"] = {f.relative_to(target).as_posix(): sha256(f) for f in sorted(target.rglob("*")) if f.is_file() and not f.is_relative_to(target / "logs") and f != report_path}
        report["reference_release_reverified_unchanged"] = True
        report["manuscript_rebuilt"] = bool(args.manuscript)
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"PASS: numerical equivalence and exact decisions; supplied release unchanged. Output: {target}")
    print(f"Comparison report: {report_path}")


if __name__ == "__main__":
    main()
