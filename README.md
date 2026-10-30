# Xcode compiler probes

The workflow is a stable launcher, not the test implementation.

- **X — compiler:** `probe/config.json` selects `DEVELOPER_DIR` and required Xcode build.
- **Y — commands and checks:** `probe/commands.py` contains executable compiler invocations and result checks.
- **Z — inputs:** `probe/probes/` contains pinned upstream fixtures; `SOURCES.json` records origins and SHA256. When editing a fixture, update its manifest provenance and SHA256 intentionally.
- `probe/run.py` fingerprints the selected tools and delegates to commands.py.

On the free standard `xcode-27` runner, changes under `probe/**` on main automatically run; manual dispatch also works. Changes outside that directory do not run automatically. No secrets, paid larger runner, signing, or repository writes are used by the job. Evidence is uploaded even after failure. Expected regression mismatches intentionally make CI red; read individual outcomes.

## Maintenance

Edit config, commands, or probes and commit to main. The stable launcher runs changes under `probe/**`; no workflow edit is needed for ordinary compiler/probe iteration. Source fixtures are offline and hash-checked. A changed compiler path must refer to a toolchain installed on the selected runner.

Local checker-only validation: `python3 probe/commands.py --self-test`.
On a Mac with the selected Xcode: `python3 probe/run.py`.

## Prior verified behavior

Run 40997201425 / commit ec66cce40d1fbc955effdce71391c98096776d5e used Xcode27B48 / Swift6.4.2 (swiftlang-6.4.2.1.9).
92708 passed the exact weak-capture reproducer; 92755 and 92632 failed their upstream behavior contracts with passing controls. Behavioral tests do not prove exact branch ancestry.
