# Xcode Cloud compiler probe

This optional carrier leaves the GitHub Actions workflow, probe commands, pinned
fixtures and previous evidence unchanged. It does not distribute software.

## One-time setup on a Mac

1. Pull this repository and open `CloudProbeCarrier.xcodeproj` in Xcode 15 or later.
2. Use your active Apple Developer Program account. In Signing & Capabilities,
   select your intended team and configure automatic signing if Xcode requests it.
   No team, signing identity, certificate, entitlement, or profile is committed here.
   The carrier bundle ID is `org.lingol.XcodeCloudProbeCarrier`; change it if your
   team cannot register/use it. Any account/identifier creation is your decision.
3. Report navigator > Cloud > Get Started. Select the shared `CloudProbeCarrier`
   scheme/product. Complete the app-record onboarding if Apple requests it.
4. Authorize Apple's Xcode Cloud GitHub app for **only** `lingol/xcode_version_probe`.
5. Edit the proposed workflow: select **Xcode 27.2 final (27B52)** and a compatible
   macOS from the live Environment picker. If that exact final version is absent,
   stop: this route cannot yet run the requested test. Do not substitute RC/beta.
6. Use one **Build** action, macOS, scheme `CloudProbeCarrier`. Remove Archive/Test
   actions and TestFlight/distribution post-actions. Start the first build manually.
   Avoid automatic push/PR schedules unless you want continuing compute usage.

You do not need Xcode 27.2 installed locally to select that version in Cloud.
Membership includes 25 compute hours/month; check remaining team usage first.
This file is setup guidance, not a claim that onboarding or a build has occurred.

## Results

`ci_scripts/ci_post_clone.sh` uses Cloud's selected Xcode and refuses a build that
does not match `probe/config.json` (`27B52`). It logs OS/architecture, commit,
Xcode/Swift/Clang versions, SDKs, target info and the SHA-256 of swift-frontend,
then calls the unchanged `probe/commands.py` for 92708, 92755 and 92632.

Read the **Post-clone** custom-script log even when the overall build is red:
a regression FAIL or unavailable exact compiler intentionally stops the build.
SKIP is untested, never a passing regression. Results establish behavior, not
exact source ancestry. Carrier build/signing failures are separate from probes.

Arbitrary custom-script files are not normal Cloud downloadable artifacts. The
hook therefore prints a gzip/tar evidence archive as base64 between
`BEGIN_CLOUD_PROBE_EVIDENCE_BASE64` and `END_CLOUD_PROBE_EVIDENCE_BASE64`, with an
`EVIDENCE_SHA256` line. Save the full custom-script log. Decode just those base64
lines into `cloud-probe-evidence.tar.gz`, verify its SHA-256 before extracting,
and retain the log itself. This preserves full probe outputs without uploading
to another service. Log truncation remains possible; verify both markers and hash.

## Validation

This carrier is prepared without a Mac. Static checks and harness checker tests
can run on Linux; opening/building the project and Xcode Cloud onboarding still
require verification in Xcode. The shared scheme is archive-enabled only so
Xcode can discover its framework product, not to request distribution.
