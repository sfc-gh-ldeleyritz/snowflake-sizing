"""renderer — deterministic JSON-spec → HTML pipeline.

Public API:
    compile_spec(spec, pricing, template, fonts_css) -> CompileResult
"""
from .compiler import CompileResult, compile_spec

__all__ = ["compile_spec", "CompileResult"]
