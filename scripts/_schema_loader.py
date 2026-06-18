"""Stdlib-only loader for framework/sizing_spec_schema.json.

Single source of truth for required-field lists and enum sets used by both
scripts/spec-validate.py and hooks/validate-sizing-json.py. Eliminates the
hand-copied constant lists that were called out as a drift risk in the
v1.7.0 CHANGELOG.

The loader exposes both low-level path navigation (`get(*path)`) and named
accessors that match the constant names previously hard-coded in the two
validators. Each accessor calls `_assert(...)` against an expected minimum
size so that schema breakage is caught at script startup rather than
producing silent false-passes.
"""
from __future__ import annotations

import json
import pathlib

# Locate the schema relative to this file: scripts/_schema_loader.py →
# plugin_root/scripts/.. → plugin_root/framework/sizing_spec_schema.json
_THIS_DIR = pathlib.Path(__file__).resolve().parent
_SCHEMA_PATH = _THIS_DIR.parent / "framework" / "sizing_spec_schema.json"


class SchemaLoadError(RuntimeError):
    pass


def _assert(name: str, value, predicate, expected: str) -> None:
    if not predicate(value):
        raise SchemaLoadError(
            f"Schema invariant failed for {name}: expected {expected}, got {value!r}. "
            f"sizing_spec_schema.json may have drifted from validator expectations."
        )


class SchemaLoader:
    def __init__(self, schema_path: pathlib.Path = _SCHEMA_PATH):
        self.path = schema_path
        try:
            self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SchemaLoadError(f"Schema not found at {schema_path}") from exc
        except json.JSONDecodeError as exc:
            raise SchemaLoadError(f"Schema is not valid JSON: {exc}") from exc

    def get(self, *path):
        """Navigate by keys, e.g. .get('properties', 'meta', 'required')."""
        cur = self.schema
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                raise SchemaLoadError(
                    f"Schema path not found: {' → '.join(path)} (failed at '{k}')"
                )
            cur = cur[k]
        return cur

    # ── Required-field accessors ────────────────────────────────────────── #

    def required_top_level(self) -> list:
        out = self.get("required")
        _assert("required_top_level", out, lambda x: len(x) >= 7, "≥7 entries")
        return out

    def required_meta(self) -> list:
        out = self.get("properties", "meta", "required")
        _assert("required_meta", out, lambda x: len(x) >= 12, "≥12 entries")
        return out

    def required_workload(self) -> list:
        out = self.get("properties", "workloads", "items", "required")
        _assert("required_workload", out, lambda x: len(x) >= 12, "≥12 entries")
        return out

    def required_ai_cortex(self) -> list:
        out = self.get("properties", "ai_cortex", "required")
        # Trimmed from 12 -> 9 in v1.8: document_ai,
        # ai_parse_document_layout, ai_parse_document_ocr are now optional in
        # the schema (the HTML template uses optional chaining for them).
        # Keeping them out of `required` lets a sizing omit those keys when
        # the customer doesn't use Document AI without breaking validation.
        _assert("required_ai_cortex", out, lambda x: len(x) == 9, "exactly 9 entries")
        return out

    def required_cortex_functions(self) -> list:
        out = self.get(
            "properties", "ai_cortex", "properties", "cortex_functions", "required"
        )
        _assert(
            "required_cortex_functions", out, lambda x: len(x) == 6, "exactly 6 entries"
        )
        return out

    def required_serverless(self) -> list:
        return self.get("properties", "serverless", "required")

    def required_confirm_required_item(self) -> list:
        return self.get(
            "properties", "confirm_required", "items", "required"
        )

    # ── Enum accessors ──────────────────────────────────────────────────── #

    def valid_editions(self) -> set:
        return set(self.get("properties", "meta", "properties", "edition", "enum"))

    def valid_clouds(self) -> set:
        return set(self.get("properties", "meta", "properties", "cloud", "enum"))

    def valid_ramp_curves(self) -> set:
        # Validator scripts also accept 'manual' (used as a Birdbox flat-line
        # signal in build-spec phase). The schema's #/definitions/ramp_curve
        # enum covers the five named curves; the spec validators tolerate
        # 'manual' as a sixth.
        return set(self.get("definitions", "ramp_curve", "enum"))

    def valid_wh_sizes(self) -> set:
        return set(self.get("definitions", "wh_size_abbreviated", "enum"))

    def valid_wh_sizes_full(self) -> set:
        return set(self.get("definitions", "wh_size_full", "enum"))

    def valid_sources(self) -> set:
        return set(self.get("definitions", "source_field", "enum"))


# Module-level singleton: import once, share across validator + hook.
SCHEMA = SchemaLoader()
