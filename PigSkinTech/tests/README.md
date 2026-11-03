# Baseline tests

These tests use scripted in-memory connection objects. They never connect to
`PigSkinAI`, initialize LocalDB, run migration, or modify application data.

Run from the application directory with the project virtual environment:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The regression tests verify that a locked account or a changed role cannot
continue to read or edit case data through a cached desktop session. They also
cover authorization and state transitions for cases/support, pre-reply message
limits, automatic support expiry, input validation, EXIF-oriented images,
readiness reporting, startup error recovery, and key UI states.

The suite also uses an isolated fake worker to verify process reuse, startup
and request timeouts, one-time restart after an unexpected exit, and clean
shutdown. The end-to-end workflow smoke chains login, AI case save, first
expert result, second-expert approval and the user's published-result view
using scripted in-memory connections; it never opens LocalDB.

The real Flet render smoke test is separate because it starts a native hidden
Flet process. It replaces LocalDB access with a harmless stub and stops only
the isolated child process after the first page has rendered:

```powershell
..\.venv\Scripts\python.exe -m tests.flet_runtime_smoke
```

The model runtime smoke test verifies hashes/metadata, loads the real
checkpoint in the configured isolated PyTorch interpreter and checks a
ten-class softmax result. Run it separately from the Flet smoke test so two
heavy native runtimes do not compete for memory:

```powershell
..\.venv\Scripts\python.exe -m tests.model_runtime_smoke
```
