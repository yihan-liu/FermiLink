"""ppg-runkit runs that also record the solver source digests."""
from pathlib import Path

from ppg_runkit.runs import Run as BaseRun, digest, unique_output, validate_run

from . import __version__


class Run(BaseRun):
    def __init__(self, out, command, inputs=(), parameters=None):
        import openbf_walls
        super().__init__(out, command, inputs, parameters, code=openbf_walls)
        source = Path(__file__).parent
        self.manifest["code_version"]["openbf_walls"] = {
            "version": __version__,
            "source_sha256": {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob("*"))
                              if p.is_file() and p.suffix in (".py", ".jl")},
        }
        self._save()


def validate(directory):
    return validate_run(directory)


__all__ = ["Run", "unique_output", "validate"]
