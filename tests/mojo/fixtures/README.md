# Independent native reference cases

`inventory.json` records each external-process case and its native TestSuite
function. Fixtures contain frozen Python-reference vectors or independently
authored native runtime cases, with provenance in each fixture. They also contain
external-process recipes; all semantic assertions execute in Mojo. Python only
copies/decompresses inputs and supervises processes.

Read a case with `gzip -dc acceptance/GROUP/CASE.json.gz`. The native preparer
expands `@ROOT@` and `@WORK@`, runs native production passes and writes results;
TestSuite compares those results and external phase outcomes. Runtime numeric
oracles retain their original tolerances and expected source-level rejections
retain their diagnostic checks. Unknown IDs, missing cases and malformed reports
fail the gate.

Debug IR data follows the current schema. Update deliberately with model changes,
without compatibility shims or automatic native-output blessing. Provenance and
migration evidence are in `agent_docs/native_testing.md`.
