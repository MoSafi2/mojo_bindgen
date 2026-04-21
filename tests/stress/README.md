# Stress Fixtures

Broad regression fixtures live here.

- `normal/`
  Broad headers that are expected to parse, round-trip through IR, and emit
  stable Mojo bindings.
- `weird/`
  Broad headers that stress awkward or mixed-support C constructs. These are
  primarily parser/IR fixtures unless explicit Mojo goldens are added later.
  This includes dedicated fixtures for extension-heavy types and the currently
  supported vs unsupported macro forms. Keep representative working cases in
  `tests/corpus/headers/`; reserve `weird/` for pathological nesting,
  extension-heavy declarations, and edge shapes that may still be partial.

Use `generate_stress_fixtures.py` to regenerate emitted Mojo and annotated IR
artifacts.

Stress Mojo goldens are regenerated in ABI-strict mode
(`MojoEmitOptions(strict_abi=True)`) so the checked-in emitted fixtures remain
stable even though the default product emission policy is now more portable.
