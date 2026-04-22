"""Compatibility re-export for the analysis-owned generator facade.

New code should import these names from :mod:`mojo_bindgen.analysis`.
"""

from __future__ import annotations

from mojo_bindgen.analysis.orchestrator import MojoGenerator, generate_mojo

__all__ = [
    "MojoGenerator",
    "generate_mojo",
]
