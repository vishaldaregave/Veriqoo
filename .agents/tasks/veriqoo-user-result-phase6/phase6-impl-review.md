# Phase 6 presentation layer: processing, compliance report, evidence viewer

Phase 6 adds the OCR/AI PROCESSING screen, the premium COMPLIANCE REPORT at `/scan/result`, and an interactive EVIDENCE VIEWER at a new `/scan/evidence` route — all strictly presentation. The analysis call moves out of the scanner and into the rewritten processing screen (D1), the report derives a deterministic 0–100 score from the existing `ComplianceAnalysis` without touching the backend (D2), and findings are tied to evidence on a best-effort basis that is always labelled DERIVED (D4). The only write outside `apps/user_app/**` is six additive glyphs on `VeriqooIcons`, and the `SupabaseService.saveInspectionReport` call is byte-for-byte the same as before. Two dependencies were added (`share_plus`, `qr_flutter`); PDF export was deliberately deferred.

Watch for: nothing blocking. All seven strict scope gates hold (confirmed). Because the entire `apps/` and `packages/` tree is untracked against HEAD, scope was verified by reading files and by a modification-time sweep rather than a git diff — the sweep shows only `veriqoo_icons.dart` touched under `packages/` and zero files touched under `apps/admin_web/` in the Phase 6 window (confirmed). A few cosmetic nits remain (a no-op ternary, a raw-error toast on the Save action, one unused string) — none gate the ship.

**Verdict**: APPROVED

## High-level view

No commits were made: HEAD sits at `origin/main` (`1570fbc`), the index is empty, and every Phase 6 file is untracked. The monorepo as a whole is untracked against HEAD, so a `git diff` surfaces nothing useful; scope was instead established by direct file reads plus a last-write-time sweep of `packages/` and `apps/admin_web/`.

Write scope holds. In the Phase 6 editing window the only file touched under `packages/` is the icon facade, and the change is purely additive — six new `static const IconData` entries (`share`, `qrCode`, `flag`, `eye`, `zoomIn`, `shield`) appended below fifteen untouched existing glyphs. New `static const`s cannot break `admin_web`, which has no files in the window at all.

The persistence contract is untouched. `SupabaseService.saveInspectionReport` keeps its exact signature and is still invoked from a single call site with the same `analysis / ocrText / primaryImage / imageUrl` arguments, lazily constructed inside the Save handler.

The processing screen now drives the real pipeline and funnels every failure into `VeriqooErrorState` — the raw exception never reaches the UI. The compliance score is a pure, documented function of the existing analysis, pinned by unit tests to exact values. Evidence associations are synthesized from approximate live-detection boxes and are always flagged `derived = true`, with a visible "DERIVED" note in the viewer and the explanation sheet.

Design-system discipline is intact: every consumer imports the single barrel, no file in `user_app` imports Lucide directly, icons go through the `VeriqooIcons` facade, and the surfaces are monochrome with hairline rules and reduced-motion handling. Share is isolated behind an injectable `ReportSharer` so tests never open a native sheet, and the QR renders monochrome.

<details>
<summary>Issues (4)</summary>

1. **No-op evidence index** — in `linkFinding`, `final imageIndex = evidenceCount > 0 ? 0 : 0;` evaluates to `0` on both branches, so `evidenceCount` has no effect. Replace with a plain `const imageIndex = 0;` (and drop the now-decorative parameter, or actually clamp against `evidenceCount`) so the intent reads honestly. Non-blocking.
2. **Raw error in Save toast** — `ResultStrings.reportSaveFailedMessage` interpolates `$error` directly into the SnackBar, so a backend/stack message can surface to the user. This is the Save action, not the gated analysis/offline path, but it deserves a friendly fixed string. Non-blocking.
3. **Unused string constant** — `ResultStrings.extractRowPending ('—')` is defined but never referenced (the processing rows use `extractRowReading`). Remove it or use it. Non-blocking.
4. **Success-path navigation inside the catch scope** — the processing screen's `context.pushReplacement` to `/scan/result` sits inside the same `try` whose `catch` sets the error flag, so a (very unlikely) throw from navigation after a successful analysis would render ANALYSIS INTERRUPTED. Consider moving the push past the try. Non-blocking.

</details>

<details>
<summary>Details</summary>

### No commits; the whole tree is untracked

HEAD, `origin/main`, and `origin/HEAD` all point at `1570fbc` ("Organize Veriqoo repository structure"), the staged set is empty, and `git ls-files` reports zero tracked files under both `apps/` and `packages/` (confirmed). Every Phase 6 artifact is therefore untracked/uncommitted, satisfying the no-commits gate.

The side effect is that `git diff main` cannot isolate this phase — it would report the entire monorepo as untracked. Scope was instead verified two ways: reading each created/modified file, and a last-write-time sweep. Using the Phase 6 editing window (2026-10-05, roughly 05:20–06:15), the sweep over `packages/**` returns exactly one source file — `veriqoo_icons.dart` at 05:26 — and the sweep over `apps/admin_web/**` returns nothing (confirmed). That is strong corroboration for the write-scope gates even without a usable diff.

### Write scope: only the icon facade escapes user_app, additively

`veriqoo_icons.dart` keeps all fifteen prior glyphs unchanged and appends six under a "Phase 6 — additive, no removals/renames" comment, each a `static const IconData` mapping to a confirmed `LucideIcons` member. Adding `static const`s to an `abstract final` facade cannot break any existing consumer, so `admin_web` compiles untouched — and the `dart analyze` → "No issues found!" recorded for `shared_core` is consistent with that (per the recorded verification evidence; not re-run here). No file under `packages/shared_core/lib/services/*` is in the window.

### SupabaseService untouched; one unchanged save call

The service file is not in the Phase 6 window, and its method still reads:

```dart
Future<void> saveInspectionReport({
  required ComplianceAnalysis analysis,
  required String ocrText,
  XFile? primaryImage,
  String? imageUrl,
  DateTime? inspectedAt,
}) async
```

There is exactly one call site (`AnalysisResultScreen._saveReport`), passing `analysis / ocrText / primaryImage / imageUrl` and constructing `SupabaseService()` lazily so the screen mounts without `Supabase.initialize` under test (confirmed). The pre-existing optional `inspectedAt` is not newly introduced and not passed. Persistence behavior is identical to before.

### Processing drives the pipeline; failures land in VeriqooErrorState

`ScanScreen._analyze` no longer runs the analysis inline: it guards empty evidence with a SnackBar, sets a `_busy` latch against double-push, sets analyzing, stops the camera stream, and pushes `/scan/processing`. The `scan_analysis_runner` / `AnalysisResultArgs` / `resolveGeminiApiKey` imports it used to need are gone from that file (confirmed).

The rewritten `ScanProcessingScreen` reads `scanState.evidence`, runs `scanAnalysisRunnerProvider`, and on success `advancePhase(complete: true)` then `pushReplacement`s `/scan/result` with the unchanged `AnalysisResultArgs`. Both `on AIAnalysisException` and a catch-all set an error flag that renders a keyed `VeriqooErrorState` (title/message/retry from `ResultStrings`); the raw exception is never surfaced, and `setAnalyzing(false)` plus ticker cancellation run in `finally`. The widget test asserts the error path shows the keyed error state with `tester.takeException()` null and no navigation (confirmed). Empty-evidence on entry also routes to the error state whose retry returns to the scanner.

```
ScanScreen._analyze ──push──▶ /scan/processing ──runner.run()──▶ success ──pushReplacement──▶ /scan/result
                                      │
                                      └── AIAnalysisException | any error ──▶ VeriqooErrorState (keyed, retry=_run)
```

One narrow observation (possible, low severity): the success-path `pushReplacement` sits inside the same `try` as the runner call, so if navigation itself threw after a successful analysis the catch-all would show ANALYSIS INTERRUPTED. In practice `pushReplacement` does not throw here, so this is a style nit rather than a real failure mode.

### Deterministic compliance score as a pure presentation derivation

`ComplianceScore.fromAnalysis` is pure and documents the D2 formula in a doc comment: `base = present/7*100`, minus `6 × missing count`, minus severity-weighted issue penalties (`critical|high=12, medium=8, low=5, else=8`), clamped to 0–100 and rounded. It imports only `foundation` and the existing `ComplianceAnalysis` — no service or widget dependency — so it cannot be mistaken for a backend change. `compliance_score_test.dart` pins the three fixtures to 100 / 11 / 75, asserts determinism, checks case-insensitive severity mapping, and verifies the clamp-to-zero case (confirmed). Summary counts (`verified = present`, `flagged = issues`, `missing = missing`) feed the three status chips.

### Evidence links are always marked DERIVED

Because the backend returns no per-issue bounding boxes, `linkFinding` keyword-matches a finding to a `DetectedFieldLabels` value (`targetFieldLabel`), carries the matching live-detection rect when present, and otherwise falls back to the primary image with no fabricated box. `EvidenceLink.derived` is hard-coded `true` in both branches, each with a `reason` string (confirmed). The viewer paints the live-detection boxes via the reused Phase 5 `DetectionBoxesOverlay`, draws a distinct focus highlight for the linked rect, and renders a visible note — `ResultStrings.derivedNote` = "DERIVED — region inferred from live detection, not an exact backend coordinate." — whenever a finding is focused, repeated inside the "WHY THIS MATTERS" sheet. No synthesized association is presented as an authoritative coordinate.

The index computation here is a no-op: `final imageIndex = evidenceCount > 0 ? 0 : 0;` returns `0` regardless, so `evidenceCount` does nothing (confirmed). Behavior is correct (always the primary image), but the ternary should be simplified so the intent is not misread as index logic.

### Design system through the barrel and VeriqooIcons

Every reviewed file imports `package:shared_core/design_system/design_system.dart`; a grep for deep `design_system/...` imports and for `lucide` across `user_app/**/*.dart` returns nothing (confirmed). Icons are consumed through the `VeriqooIcons` facade (`share`, `qrCode`, `upload`, `eye`, `flag`, `shield`, `scan`, `zoomIn`). Surfaces are monochrome against `VeriqooTokens`, separated by `VeriqooDivider`/hairline borders rather than cards or shadows, with the tertiary tone reserved for meta/DERIVED notes. Reduced motion is honored in both the processing phase ticker (jumps to the final caption) and the evidence zoom (`animateToRect` snaps instead of easing).

### Share isolated behind an injectable sharer; monochrome QR

`ReportSharer` is an abstract one-method seam; `SharePlusReportSharer` wraps a single `SharePlus.instance.share(ShareParams(text: ...))` call (share_plus v13), exposed via `reportSharerProvider` so tests inject a recording fake and never open the OS sheet. `share_plus` is imported only by this service in `lib/` (the other hit is a generated `.dart_tool` registrant) (confirmed). The QR sheet renders `QrImageView` deliberately dark-on-light for scanner polarity, documented as an intentional, still-monochrome exception. The share text and QR payload carry only product name, score, counts, and a derived reference id — no secrets or credentials. The Gemini API key continues to flow through the pre-existing `resolveGeminiApiKey()` into the runner; Phase 6 does not change credential handling.

### Test coverage

The hermetic suite under `apps/user_app/test/scan/` covers the score formula (three fixtures + determinism + clamp), finding ordering/kind/status and `linkFinding` matching/fallback/always-derived, the report render + Share-invokes-fake + QR-modal + finding-navigates, the processing success→result and error→`VeriqooErrorState` paths, and the evidence viewer render/zoom/DERIVED/why-sheet/empty-state; the Phase 5 scanner test was updated to assert the `/scan/processing` handoff (files confirmed present). Not run here by design: `flutter test` and `flutter build web` are denied in this environment and recorded as DEFERRED with verbatim commands. Not tested (runtime-unverified by design): the live Gemini + RAG pipeline, the native share sheet, and the real Supabase save — all stubbed by fakes. The acceptance bar for this environment (`dart pub get` success + `dart analyze` 0 errors on both packages) is recorded in the verification evidence; the code read here is consistent with an analyze-clean result (non-deprecated `withValues`/`Matrix4` APIs, no obvious unused imports), so no spot-check was warranted.

</details>

<details>
<summary>File map</summary>

New (`apps/user_app/lib/features/scan/`):
- `result/result_strings.dart` — centralized, localization-ready copy.
- `result/compliance_score.dart` — deterministic D2 score (pure, documented).
- `result/report_reference.dart` — deterministic id + compact QR payload (web-safe hash).
- `result/report_finding.dart` — findings model + best-effort `linkFinding` (always DERIVED).
- `result/report_share_service.dart` — injectable `ReportSharer` over share_plus.
- `result/widgets/product_details_panel.dart` — hairline detail rows.
- `result/widgets/report_finding_tile.dart` — numbered editorial finding tile.
- `result/widgets/report_qr_sheet.dart` — monochrome QR content.
- `evidence/evidence_viewer_args.dart` — viewer args.
- `evidence/evidence_viewer_screen.dart` — the EVIDENCE VIEWER.
- `evidence/widgets/evidence_image_view.dart` — InteractiveViewer + derived boxes + focus highlight.

Modified (`apps/user_app/`):
- `lib/features/scan/analysis_result_screen.dart` — premium report; args/class name/Save preserved.
- `lib/features/scan/scan_processing_screen.dart` — drives the real pipeline, VeriqooErrorState on failure.
- `lib/features/scan/scan_screen.dart` — `_analyze` hands off to `/scan/processing`.
- `lib/app/routes.dart`, `lib/app/router.dart` — add `/scan/evidence`.
- `pubspec.yaml` (+ `pubspec.lock`) — add `share_plus`, `qr_flutter`.

Modified (additive, `packages/shared_core/`):
- `lib/design_system/foundations/veriqoo_icons.dart` — +`share, qrCode, flag, eye, zoomIn, shield`.

Tests (`apps/user_app/test/scan/`):
- new: `result_harness.dart`, `compliance_score_test.dart`, `report_finding_test.dart`, `analysis_result_screen_test.dart`, `scan_processing_screen_test.dart`, `evidence_viewer_test.dart`.
- modified: `scan_harness.dart` (keyed `/scan/processing`), `scanner_screen_test.dart` (assert handoff).

No usable `git diff` (tree untracked against HEAD `1570fbc`); scope verified by file reads + a last-write-time sweep of `packages/` and `apps/admin_web/`.

</details>
