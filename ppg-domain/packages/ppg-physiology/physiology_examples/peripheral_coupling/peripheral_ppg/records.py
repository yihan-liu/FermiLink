"""Small, reference-checked JSON research record store."""
import json
import hashlib
from pathlib import Path


def save_record(path, record):
    required = ("question", "hypothesis", "parameters_and_sources", "run_id", "evidence", "conditional_conclusion", "ambiguities", "next_question")
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError("missing record fields: " + ", ".join(missing))
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    manifests = []
    for entry in record["evidence"]:
        evidence = Path(entry)
        if not evidence.is_absolute():
            evidence = target.parent / evidence
        if not evidence.exists():
            raise ValueError(f"evidence does not exist: {entry}")
        if evidence.name == "manifest.json":
            manifests.append((evidence, json.loads(evidence.read_text(encoding="utf-8"))))
    matches = [(p, m) for p, m in manifests if m.get("run_id") == record["run_id"] and m.get("status") in ("complete", "completed")]
    if not matches:
        raise ValueError("evidence must include a completed manifest for run_id")
    manifest_path, manifest = matches[0]
    outputs = manifest.get("outputs")
    if not outputs:
        raise ValueError("run manifest has no declared outputs")
    hashes = outputs if isinstance(outputs, dict) else manifest.get("output_sha256", {})
    for name in outputs:
        artifact = manifest_path.parent / name
        if not artifact.is_file():
            raise ValueError(f"declared run output is missing: {name}")
        if name in hashes and hashlib.sha256(artifact.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f"declared run output checksum mismatch: {name}")
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (target.parent / "index.jsonl").open("a", encoding="utf-8") as index:
        index.write(json.dumps({"record": target.name, "run_id": record["run_id"], "question": record["question"]}, ensure_ascii=False) + "\n")
