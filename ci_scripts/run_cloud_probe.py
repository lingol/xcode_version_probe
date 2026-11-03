#!/usr/bin/env python3
"""Use Cloud's selected Xcode, require the pinned final build, preserve log evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import base64

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
OUT = ROOT / "cloud-probe-results"
OUT.mkdir(exist_ok=True)


def capture(args):
    print("COMMAND", json.dumps(args), flush=True)
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=120)
    print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n", flush=True)
    with (OUT / "fingerprint.txt").open("a") as log:
        log.write("$ " + json.dumps(args) + "\n" + proc.stdout + "\n")
    if proc.returncode:
        raise RuntimeError(f"Fingerprint command failed ({proc.returncode}): {args!r}")
    return proc.stdout


def main():
    expected = json.loads((ROOT / "probe/config.json").read_text())["expected_build"]
    print("EXPECTED_XCODE_BUILD", expected, flush=True)
    for args in (["date", "-u"], ["git", "rev-parse", "HEAD"],
                 ["sw_vers"], ["uname", "-a"], ["xcode-select", "-p"]):
        capture(args)
    version = capture(["xcodebuild", "-version"])
    # Cloud's Environment picker owns toolchain selection, never an /Applications guess.
    if f"Build version {expected}" not in version.splitlines():
        raise RuntimeError(f"REQUESTED BUILD UNAVAILABLE: {expected}; no regression probes executed")
    for tool in ("swiftc", "swift", "clang"):
        capture(["xcrun", "--toolchain", "XcodeDefault", tool, "--version"])
    capture(["xcrun", "--toolchain", "XcodeDefault", "swiftc", "-print-target-info"])
    capture(["xcrun", "--sdk", "macosx", "--show-sdk-path"])
    capture(["xcodebuild", "-showsdks"])
    frontend = capture(["xcrun", "--toolchain", "XcodeDefault", "--find", "swift-frontend"]).strip()
    capture(["shasum", "-a", "256", frontend])
    # Same unchanged, offline, hash-checked three-probe implementation as GitHub Actions.
    return subprocess.run([sys.executable, "-u", "probe/commands.py"], timeout=600).returncode


def emit_evidence():
    summary = ROOT / "probe-results/summary.json"
    if summary.exists():
        print("PROBE_SUMMARY", summary.read_text(), flush=True)
    else:
        print("NO REGRESSION RESULTS: this is not a pass.", flush=True)
    print("Behavioral evidence only, not source ancestry. SKIP means untested.", flush=True)
    # Cloud does not retain arbitrary script files as artifacts. Include a lossless
    # archive in the hook log, without an external upload or any credentials.
    archive = ROOT / "cloud-probe-evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for name in ("cloud-probe-results", "probe-results", "probe/config.json", "probe/probes/SOURCES.json"):
            if (ROOT / name).exists():
                tf.add(ROOT / name, arcname=name)
    data = archive.read_bytes()
    print("EVIDENCE_SHA256", hashlib.sha256(data).hexdigest(), flush=True)
    print("BEGIN_CLOUD_PROBE_EVIDENCE_BASE64", flush=True)
    print(base64.encodebytes(data).decode("ascii"), end="", flush=True)
    print("END_CLOUD_PROBE_EVIDENCE_BASE64", flush=True)


if __name__ == "__main__":
    status = 1
    try:
        status = main()
    except Exception as exc:
        print("HARNESS ERROR:", exc, flush=True)
        (OUT / "harness-error.txt").write_text(str(exc) + "\n")
    finally:
        emit_evidence()
    sys.exit(status)
