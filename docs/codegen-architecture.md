# Codegen Architecture

`mojo_bindgen` keeps parsed C facts in the IR and derives Mojo-specific choices in a separate analysis layer.

## Flow

`Unit` -> `MojoGenerator.analyze()` -> `AnalyzedUnit` -> `MojoGenerator.render()` -> Mojo source

## Module Responsibilities

- [`mojo_bindgen/ir.py`](../mojo_bindgen/ir.py)
  C-facing facts extracted from clang. This is the source of truth for declarations and types.
- [`mojo_bindgen/codegen/mojo_mapper.py`](../mojo_bindgen/codegen/mojo_mapper.py)
  Pure helpers for identifier sanitization and Mojo type strings (`TypeMapper` / `canonical` / `surface`).
- [`mojo_bindgen/passes/analyze_for_mojo.py`](../mojo_bindgen/passes/analyze_for_mojo.py)
  Unit-level codegen analysis. This decides ordering, import requirements, union strategy, passability, typedef exposure, and function wrapper classification.
- [`mojo_bindgen/codegen/render.py`](../mojo_bindgen/codegen/render.py)
  Pure rendering. This turns `AnalyzedUnit` plus IR declarations into text.
- [`mojo_bindgen/codegen/generator.py`](../mojo_bindgen/codegen/generator.py)
  Public orchestration through `MojoGenerator`.

Parsing lives under [`mojo_bindgen/parsing/`](../mojo_bindgen/parsing/) (frontend, registry, lowering, diagnostics) and produces the `Unit` consumed here.

## IR vs Analysis

Keep data in the IR only when it is true about the parsed C API itself.

Examples that belong in the IR:

- struct size and alignment
- field offsets
- typedef canonical targets
- enum underlying types

Examples that belong in analysis:

- whether a struct is `RegisterPassable`
- whether a union can be emitted as `UnsafeUnion`
- whether a typedef should be skipped because it collides with a struct or enum name
- whether a function gets a wrapper or only a stub comment
- which imports and helpers the generated module needs

The analysis layer intentionally does not store pre-rendered strings like full function signatures or comment blocks. Those belong in the renderer.

## Public Entry Point

Use `MojoGenerator` for higher-level callers:

```python
generator = MojoGenerator(options)
analyzed = generator.analyze(unit)
text = generator.render(analyzed)
```

For one-shot generation:

```python
text = MojoGenerator(options).generate(unit)
```

## Prior Art

This structure follows the same broad separation used by `rust-bindgen`: coarse `ir`, `codegen`, and `options` subsystems, with parsing producing IR and code generation consuming it.

References:

- https://docs.rs/crate/bindgen/latest/source/
- https://docs.rs/bindgen/latest/bindgen/struct.Builder.html
- https://codebrowser.dev/slint/crates/bindgen/ir/mod.rs.html
