"""Compatibility re-export for the analysis-owned generator facade.

New code should import these names from :mod:`mojo_bindgen.analysis`.
"""

from __future__ import annotations

from mojo_bindgen.analysis.orchestrator import (
    GeneratedArtifacts,
    MojoGenerator,
    generate_mojo,
    generate_mojo_artifacts,
)

__all__ = [
    "GeneratedArtifacts",
    "MojoGenerator",
    "generate_mojo",
    "generate_mojo_artifacts",
]
