# Python reference implementation

This is the retained Python generator before the 0.4 native cutover. It is a
separate, opt-in project, not part of the installed mojo-bindgen distribution.
Its original `mojo_bindgen` import namespace and CLI run inside this environment.

From the repository root:

```sh
pixi install --manifest-path legacy/python/pixi.toml --locked
pixi run --manifest-path legacy/python/pixi.toml --locked test
pixi run --manifest-path legacy/python/pixi.toml --locked parity
pixi run --manifest-path legacy/python/pixi.toml --locked mojo-bindgen --help
```

Headers, source goldens and runtime fixtures remain shared under the repository's
`tests/` directory. The parity suite also needs the native SDK and example-library
environments. This project's Python environment must remain separate from the CLI
facade's environment. Reference maintenance is opt-in; new generation features
belong in Mojo.
