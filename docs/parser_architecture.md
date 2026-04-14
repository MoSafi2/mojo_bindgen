# Parser Architecture

The `mojo_bindgen.parsing` package is organized as a staged pipeline that turns
one C header into one `Unit`.

## Pipeline

1. `parser.py`
   Owns the public facade. Validates inputs, runs the pipeline, and returns the
   final `Unit`.
2. `frontend.py`
   Owns libclang translation-unit creation, path resolution, compile-arg
   normalization, and frontend diagnostic collection.
3. `index.py`
   Owns declaration identities, forward-declaration to definition mapping,
   source-order top-level cursors, and anonymous record identity policy.
4. Lowering modules (`lowering/`)
   Convert clang nodes into IR while keeping responsibilities separate:
   - `lowering/primitive.py`: primitive typing and literal ABI probing
   - `lowering/type_lowering.py`: `cx.Type -> ir.Type`
   - `lowering/record_lowering.py`: struct/union and field lowering
   - `lowering/decl_lowering.py`: top-level decl assembly
   - `lowering/const_expr.py`: supported constant-expression parsing for macros/globals
5. `diagnostics.py`
   Owns parser-stage diagnostic accumulation and conversion to `IRDiagnostic`.

## Flow

```text
parser config
  -> frontend
  -> declaration index
  -> lowerers
  -> top-level declaration lowering
  -> macro collection
  -> Unit assembly
```

## Inputs and Outputs

- `parser.py`
  Input: parser arguments
  Output: `Unit`
- `frontend.py`
  Input: parser config
  Output: `TranslationUnit`, frontend diagnostics
- `index.py`
  Input: `TranslationUnit`
  Output: stable declaration metadata and ordered top-level cursors
- `lowering/type_lowering.py`
  Input: `cx.Type`, semantic context
  Output: `ir.Type`
- `lowering/record_lowering.py`
  Input: record cursor
  Output: `Struct` and nested record definitions
- `lowering/decl_lowering.py`
  Input: top-level cursor
  Output: `Decl` or `list[Decl]`
- `lowering/const_expr.py`
  Input: token stream or macro/initializer cursor
  Output: parsed const-expression payload
- `diagnostics.py`
  Input: frontend and lowering diagnostics
  Output: normalized `IRDiagnostic` list

## Separation of Concerns Rules

- `frontend.py` must not build IR declarations.
- `index.py` must not lower clang nodes to IR.
- `lowering/type_lowering.py` must not assemble top-level declarations.
- `lowering/record_lowering.py` must own record traversal and field policy only.
- `lowering/decl_lowering.py` must delegate type/record/const-expr details to narrower collaborators.
- `lowering/const_expr.py` must depend only on a small literal-typing interface.
- diagnostics must flow through `diagnostics.py`, not ad hoc mutable lists.

## Extending the Parser

- Add new top-level declaration behavior in `lowering/decl_lowering.py`.
- Add new record/field behavior in `lowering/record_lowering.py`.
- Add new type semantics in `lowering/type_lowering.py`.
- Add new literal typing policy in `lowering/primitive.py`.
- Do not add new parser logic to `parser.py` unless it is orchestration logic.
