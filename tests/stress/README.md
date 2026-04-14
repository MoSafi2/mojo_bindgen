# Stress Fixtures

Broad regression fixtures live here.

- `normal/`
  Broad headers that are expected to parse, round-trip through IR, and emit
  stable Mojo bindings.
- `weird/`
  Broad headers that stress awkward or mixed-support C constructs. These are
  primarily parser/IR fixtures unless explicit Mojo goldens are added later.
  This includes dedicated fixtures for extension-heavy types and the currently
  supported vs unsupported macro forms.

Use `generate_stress_fixtures.py` to regenerate emitted Mojo and annotated IR
artifacts.
