#!/usr/bin/env python3
"""Stable entrypoint: select compiler, fingerprint, then execute editable commands."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
os.chdir(REPO)
config = json.loads((ROOT / "config.json").read_text())
os.environ["DEVELOPER_DIR"] = config["developer_dir"]
results = REPO / "results"
results.mkdir(exist_ok=True)


def inventory_xcodes():
    """Record the allocated runner's real installations, not documentation aliases."""
    inventory = []
    seen = set()
    for app in sorted(Path("/Applications").glob("Xcode*.app")):
        real = app.resolve()
        if real in seen:
            continue
        seen.add(real)
        developer = real / "Contents/Developer"
        env = dict(os.environ, DEVELOPER_DIR=str(developer))
        proc = subprocess.run(["xcodebuild", "-version"], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        item = dict(path=str(app), real_path=str(real), exit_code=proc.returncode,
                    version=proc.stdout.strip())
        inventory.append(item)
        print("INSTALLED_XCODE", json.dumps(item), flush=True)
    (results / "installed-xcodes.json").write_text(json.dumps(inventory, indent=2) + "\n")
    return inventory


def main():
    installed = inventory_xcodes()
    matches = [item for item in installed if item["exit_code"] == 0 and
               f"Build version {config['expected_build']}" in item["version"].splitlines()]
    if not matches:
        raise RuntimeError(f"REQUESTED BUILD UNAVAILABLE: {config['expected_build']}; no regression probes executed")
    os.environ["DEVELOPER_DIR"] = str(Path(matches[0]["real_path"]) / "Contents/Developer")
    with (results / "fingerprint.txt").open("w") as evidence:
        def capture(args):
            print("COMMAND", json.dumps(args), flush=True)
            proc = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=120)
            evidence.write("$ " + json.dumps(args) + "\n" + proc.stdout + "\n")
            evidence.flush()
            print(proc.stdout, flush=True)
            if proc.returncode:
                raise RuntimeError(f"Fingerprint command failed: {args!r}, exit {proc.returncode}")
            return proc.stdout

        evidence.write("DEVELOPER_DIR=" + os.environ["DEVELOPER_DIR"] + "\n")
        evidence.write("GITHUB_RUN_ID=" + os.environ.get("GITHUB_RUN_ID", "local") + "\n")
        capture(["date", "-u"])
        capture(["git", "rev-parse", "HEAD"])
        capture(["sw_vers"])
        capture(["uname", "-a"])
        version = capture(["xcodebuild", "-version"])
        if f"Build version {config['expected_build']}" not in version.splitlines():
            raise RuntimeError("Selected Xcode build does not match config.json")
        for tool in ("swiftc", "swift", "clang"):
            capture(["xcrun", "--toolchain", "XcodeDefault", tool, "--version"])
        capture(["xcrun", "--toolchain", "XcodeDefault", "swiftc", "-print-target-info"])
        capture(["xcrun", "--sdk", "macosx", "--show-sdk-path"])
        capture(["xcodebuild", "-showsdks"])
        frontend = capture(["xcrun", "--toolchain", "XcodeDefault", "--find", "swift-frontend"]).strip()
        capture(["shasum", "-a", "256", frontend])
    return subprocess.run([sys.executable, str(ROOT / "commands.py")], timeout=600).returncode


if __name__ == "__main__":
    status = 1
    try:
        status = main()
    except Exception as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr, flush=True)
        (results / "harness-error.txt").write_text(str(exc) + "\n")
    finally:
        summary = Path("probe-results/summary.json")
        text = "## Compiler probes\n\n"
        if summary.exists():
            for item in json.loads(summary.read_text()):
                text += f"- {item['probe']}: **{item['status']}** — {item['detail']}\n"
        else:
            text += "No regression results produced; inspect harness-error/fingerprint. Not a pass.\n"
        text += "\nBehavioral evidence only; no claim of exact source ancestry. SKIP means untested.\n"
        (results / "summary.md").write_text(text)
        if "GITHUB_STEP_SUMMARY" in os.environ:
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as dest:
                dest.write(text)
    sys.exit(status)
