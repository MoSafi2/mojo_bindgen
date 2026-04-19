# Contributing

## Development environment

This repository targets **Python 3.14+** and a **system libclang** compatible with the [`libclang`](https://pypi.org/project/libclang/) Python bindings.

### Pixi (recommended for Modular/Mojo work)

The [Pixi](https://pixi.sh) workspace is currently locked for **linux-64** only. On other platforms, use a plain virtualenv and `pip install -e ".[dev]"` instead.

`pixi install` uses the **default** environment, which includes the `dev` feature (Jupyter, pytest, Ruff, Pyright, build, …). For a minimal install (Mojo, Python, and editable `mojo-bindgen` only), use `pixi install -e install` and `pixi shell -e install`.

```bash
pixi install
pixi shell
pixi run lint
pixi run format
pixi run typecheck
pixi run test
```

### Virtualenv (any supported OS)

Install Clang and libclang using your OS package manager (see [README.md](README.md)), then:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -m "not e2e"
```

Set `LIBCLANG_PATH` if the shared library is not on the default loader path.

## Checks before you push

- `ruff check mojo_bindgen tests` and `ruff format mojo_bindgen tests`
- `pyright mojo_bindgen` (parsing code under `mojo_bindgen/parsing/` is excluded; libclang has no usable stubs)
- `pytest -m "not e2e"` for fast feedback

End-to-end tests (`tests/e2e/`) need a C toolchain, Mojo, and more setup; see [tests/e2e/README.md](tests/e2e/README.md).

## Releases

1. Update [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]` with a dated section for the new version, then set the version in [pyproject.toml](pyproject.toml).
2. Commit, tag `vX.Y.Z`, and push the tag. The [release workflow](.github/workflows/release.yml) builds sdist/wheel, uploads them as a **GitHub Actions artifact** named `dist`, and **publishes to PyPI** using [trusted publishing](https://docs.pypi.org/trusted-publishers/).

Semantic versioning applies to the **documented public API**: CLI behavior, `mojo_bindgen` exports (`MojoGenerator`, `MojoEmitOptions`, `generate_mojo`, `__version__`), and the parse → IR → generate flow described in the README. Internal modules may change between minor releases.

## Pull requests

Keep changes focused. If you add user-visible behavior, update the README or CHANGELOG as appropriate.
