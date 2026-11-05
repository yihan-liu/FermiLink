"""Reuse ppg-forward run hashing with explicit arterial-package identity."""
from pathlib import Path
from ppg_forward.manifests import Run as ForwardRun, validate_run, unique_output, digest
from . import __version__


class Run(ForwardRun):
    def __init__(self, out, command, inputs=(), parameters=None):
        super().__init__(out, command, inputs, parameters)
        source = Path(__file__).parent
        self.manifest["code_version"]["arterial_1d"] = {
            "version": __version__,
            "source_sha256": {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob("*"))
                              if p.is_file() and p.suffix in (".py", ".jl")},
        }
        self._save()
