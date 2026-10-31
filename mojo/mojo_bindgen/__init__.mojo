"""Native recursive IR backend; header parsing remains in the Python implementation."""
from .ir import CType, MojoType, CConstExpr, MojoConstExpr, Unit, MojoModule, TargetABI
from .analysis.mojo.type_mapping import MapTypePass, map_type
from .analysis.facts.target import TargetQueries
from .analysis.type_walk import validate_type_tree
from .analysis.pipeline import AnalysisOrchestrator, AnalysisArtifacts
from .analysis.mojo.mojo_emit_options import MojoEmitOptions
from .codegen.mojo_ir_printer import MojoIRPrinter, MojoIRPrintOptions, render_mojo_module
from .layout_tests.generator import render_layout_test_module
from .orchestrator import BackendResult, generate_from_unit
