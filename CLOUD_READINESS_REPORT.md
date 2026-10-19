# Cloud preparation report — 2026-10-16

Scope: `C:\Users\Admin\Desktop\phishing-detector-mvp-cloud` only.
GitHub repository creation, push and Streamlit deployment were not performed.
No local source/experiment files were deleted. Deployment exclusions use `.gitignore`.

## Status

- Public default: Live URL Analysis and Demo Mode only.
- HTML Upload and Controlled Validation: hidden and blocked in public mode; local code retained.
- Windows Python 3.13.14: imports, frozen model/schema and offline sandboxed Chromium probe PASS.
- PyPI: requested pinned releases have Python 3.13/Linux wheel candidates; no packages changed to unrequested versions.
- Minimal deployment staging: **55 files, approximately 9.93 MiB**; imports,
  13 artifact hashes and real Demo C browser/extractor/inference PASS without
  experimental directories or research imports.
- Linux / Community Cloud install, sandbox, live URL, egress and load checks: PENDING.
- Final combined coverage: **855 PASS, 122 SKIPPED, zero unresolved failures/errors**
  across **977 unique test cases**. This combines the full run and focused final
  rerun, taking the latest result for each case; it is not a claim of one clean
  monolithic 977-case run. Detailed counts are below.

## Changed / new files

| File | Change |
|---|---|
| `cloud_config.py` | New strict environment flag and public/local mode lists |
| `crawler/url_policy.py` | New fail-closed HTTP(S), DNS A/AAAA, IP and exact trusted-origin validator |
| `crawler/egress.py` | New pinned-address HTTP/CONNECT proxy with connection and byte budgets |
| `crawler/runtime.py` | New global thread/process browser gate, fail-fast busy response |
| `crawler/browser_check.py` | New offline sandboxed Chromium/context/cleanup worker |
| `crawler/browser.py` | Proxy launch, network policy propagation and proxy-policy checks |
| `crawler/restricted.py` | Global gate, IPC policy propagation, per-request destination and response-size checks |
| `crawler/restricted_worker.py` | Pass network policy into isolated browser collection |
| `ui/analysis.py` | Public live destination validation, separate trusted fixture entry, blocked public uploads, discard public DOMs after extraction |
| `ui/demo_server.py` | New single-fixture server independent of research modules |
| `ui/demo.py` | Trusted internal demo path; remove import of evaluation routines |
| `ui/inference.py` | Hardcoded frozen model SHA-256 and threshold contract; remove offline-quality import chain |
| `ui/final_app.py` | Public-only mode menu, startup readiness gate; cache successful startup only |
| `ui/research_app.py` | Public-mode guard; local research implementation retained |
| `ui/controlled.py` | Public-mode guard; implementation retained |
| `ui/errors.py` | Public SSRF and browser-busy error messages |
| `cloud_readiness.py` | Imports/model/schema/manifest checks, idempotent Linux browser installation, supervised browser probe |
| `requirements.txt` | Requested exact pins, remove torch, add direct filelock dependency |
| `packages.txt` | Candidate Debian shared libraries for Chromium; target-host validation pending |
| `deployment_manifest.json` | New SHA-256 manifest of ten unchanged output artifacts and three demo fixtures |
| `.gitignore` | Deployment allowlist; exclude venv, sources, datasets, other models, experiments, documents, secrets and caches |
| `tests/test_cloud_security.py` | New URL/DNS/proxy/interception/budget security tests |
| `tests/test_cloud_runtime.py` | New public UI/import isolation, frozen model, readiness and browser-gate tests |
| `tests/test_cloud_browser.py` | Real loopback-only proxy/script, SSRF redirect/fetch and exception-cleanup browser regressions |
| `tests/test_final_system.py` | Local-mode opt-in; keep frozen asset/schema hashes while allowing the three intentionally changed collector source files in historical source baseline |
| `tests/test_ui_helpers.py` | Explicit local-mode opt-in for legacy upload test |
| `cloud_test_policy.py` | Session-wide pytest no-training policy for legacy fitting tests |
| `CLOUD_DEPLOYMENT.md` | Local/cloud instructions, file set, environment flags, browser/security design and pending target-host checks |
| `CLOUD_READINESS_REPORT.md` | This report |

Ignored service artifacts: `.cloud-integrity-before.json`, `.cloud-*-tmp/`,
`.cloud-deployment-stage/`, `.cloud-test-results.xml`. They are not deployment inputs.

## Integrity

Before editing, SHA-256 was recorded for 498 existing files under `output/`,
`data_sources/`, `manifests/`, `reports/`, `robustness/` (excluding bytecode caches).
No frozen provenance was rewritten. The first post-edit comparison found zero changes;
the final comparison is recorded below after tests.

Post full-suite comparison: all 498 recorded protected files still match their
pre-edit SHA-256. No missing or changed files were found.

F02_RF_A08 SHA-256:

```text
8ba5c2743b5f0af05b438bb629ac88dc3daba4914fe20b9bed11bd7630e5e4a0
```

The frozen F02 model was never fitted or saved again. Model class remains exact
RandomForestClassifier, 300 trees, 137 features and threshold 0.5. Schema source
files and feature computations were not edited. Order remains
S0 → S1 → delta → network → derived → temporal.

### Test-policy deviation

The initial trial legacy test run installed the no-fit guard at function scope.
A module-scoped fixture ran before that guard and fitted temporary test estimators,
including a temporary LogisticRegression, into ignored `.cloud-test-tmp/` outputs.
This did not touch the frozen model or Phase 7/10/11 artifacts, but it was a deviation
from the user's broader no-training instruction. The trial was stopped and the
guard corrected to session scope before subsequent full-suite runs. Therefore this
report does **not** claim that no estimator fitting occurred anywhere in the trial.
Fitting-dependent tests in the final run are explicitly SKIPPED, not reported PASS.

## Windows verification

- Working `.venv`, Python 3.13.14, requested dependency versions.
- Imports without public research module imports.
- All manifest files exist and hashes match; model and frozen schema load.
- Offline browser probe launched Chromium 151.0.7922.34 with `chromium_sandbox=True`,
  created a context/page and closed both; no `--no-sandbox` fallback.
- Initial new-test run: 55 PASS. Additional proxy/resource regression tests were
  added afterwards; final results are listed below.
- The sandboxed test runner initially denied pytest temporary-directory access;
  tests/browser verification were rerun outside that runner sandbox. This does
  not disable Chromium's own sandbox.

## Linux / Community Cloud PENDING

- Actual Python 3.13 selection and full dependency install on the target host.
- Actual Debian image, apt package names, Playwright/browser ABI and sandbox support.
- Documentation mismatch: Cloud dependencies docs reference bullseye, Playwright
  lists Debian 12/13. Versions were not changed to hide that uncertainty.
- Browser installation after cold restart, writable cache, RAM/CPU usage.
- Live public URL analysis with HTTPS; no live public site was visited in testing.
- Redirect/subresource/DNS-rebinding/browser-proxy/IPv6/WebRTC checks on target host.
- Multi-session browser gate, hard-timeout/process cleanup and network budgets.

Proxy + CDP is application-level defense; it is not an OS egress firewall or a
guarantee against Chromium exploits. Do not launch publicly if target-host sandbox
or routing checks fail. Use a separately isolated collector where needed.

## Final results

1. Full-suite run: **845 passed, 122 skipped, 1 failed**, 968 collected,
   725.38 seconds. The failure was the historical collector source-code hash
   assertion, not a model/dataset/result mismatch. Frozen baseline was not edited.
2. After adapting that assertion and finishing security/resource regressions:
   **148 passed**, zero failures/errors/skips, 186.45 seconds. This reruns all
   changed cloud modules' tests, Phase 12 inference/UI/demo tests, UI helpers and
   restricted browser tests. It includes the previously failing integrity test
   and all **67 new cloud tests**.
3. Deduplicated latest-case results from both JUnit reports: **977 unique cases**,
   **855 passed**, **122 skipped**, **0 unresolved failures/errors**. Nine cases
   were added after the full run was collected and are included in the focused run.
4. Fitting-dependent skips enforce the no-training rule; they are not counted PASS.
5. Final Windows `cloud_readiness.py`: **ready=true**, imports PASS, 13 frozen
   artifacts/fixtures PASS, model/schema PASS, sandboxed Chromium/context/cleanup PASS.
6. `python -m pip check`: **No broken requirements found** in the working `.venv`.
   A fresh allowlist-only staging copy also completed Demo C with 137 features,
   `restricted-v1`, public DOM retention disabled and no evaluation/research imports.
7. Post-test protected-file comparison: **498 checked, 0 modified/missing**.
   The model SHA-256 remains exactly the digest above. Frozen Phase 7/10/11
   outputs/provenance and datasets were not changed; F02 was not retrained.
8. Linux/Community Cloud: **PENDING**, including apt/ABI, browser sandbox, live
   public HTTPS, target-host proxy/IPv6/WebRTC/rebinding, RAM and restart behavior.

JUnit evidence is retained locally in ignored `.cloud-test-results.xml` and
`.cloud-regression-results.xml`; their combined summary is
`.cloud-combined-test-results.json`. Initial interrupted/sandbox-limited trial
runs are not included in the final deduplicated test summary.
