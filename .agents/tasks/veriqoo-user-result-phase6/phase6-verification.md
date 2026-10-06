# Phase 6 Verification — user_app Processing, Compliance Report & Evidence Viewer

Scope: PRESENTATION only. `shared_core` services and the
`SupabaseService.saveInspectionReport` signature are PRESERVED; `apps/admin_web/**`
untouched. No commits. No worktree (work done in the main workspace).

## Acceptance bar — evidence (what was actually run)

Shell `flutter *` is denied in this environment; only `dart` was used.

### apps/user_app
- `dart pub get` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`) → **"Got dependencies!"**
- `dart analyze` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`) → **"No issues found!"**
  (analyzes `lib/` AND `test/`).

### packages/shared_core (icon facade only)
- `dart pub get` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core`) → **"Got dependencies!"**
- `dart analyze` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core`) → **"No issues found!"**
  (confirms `admin_web` is unaffected by the additive icon change — 0 errors).

Baseline before the work was also green on both packages (confirmed at the start).

### Dependencies added (`dart pub add share_plus qr_flutter` in apps/user_app)
Resolved versions:
- `share_plus 13.3.1` (+ `share_plus_platform_interface 7.2.0`)
- `qr_flutter 4.1.0` (+ transitive `qr 3.0.2`)
- (`url_launcher_web` bumped 2.4.1 → 2.4.3 transitively)

No `printing`/`pdf` added — PDF export is DEFERRED (see below).

share_plus is v13 (newer than the v11/12 the plan anticipated); the v13 API is the
same `SharePlus.instance.share(ShareParams(text: ...))` call used by `SharePlusReportSharer`
(verified against the installed package source). Content was rephrased for compliance with
licensing restrictions.

## DEFERRED commands (NOT run — `flutter` is denied here)

Run on a machine where `flutter` is permitted, CWD `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`:

```
flutter test
```

```
flutter build web
```

The hermetic widget/unit tests under `apps/user_app/test/scan/` are WRITTEN and KEPT but
NOT executed here. Runtime-unverified by design (hermetic fakes only): the live/real Gemini+RAG
analysis, the native OS share sheet, and the Supabase save path. PDF export
(`printing`/`pdf`) is a DEFERRED follow-up, not added this phase (keeps the dependency
surface analyze-clean and simple).

## Files created

New (`apps/user_app/lib/features/scan/`):
- `result/result_strings.dart` — centralized, localization-ready copy (`ResultStrings`).
- `result/compliance_score.dart` — deterministic `ComplianceScore` (D2 formula, documented).
- `result/report_reference.dart` — `ReportReference` (deterministic id + compact QR payload).
- `result/report_finding.dart` — `ReportFinding`/`ReportFindingKind`, `EvidenceLink`,
  `linkFinding`, `targetFieldLabel` (best-effort evidence linker).
- `result/report_share_service.dart` — injectable `ReportSharer` + `reportSharerProvider`
  over `share_plus`.
- `result/widgets/product_details_panel.dart` — hairline product-details rows.
- `result/widgets/report_finding_tile.dart` — numbered finding tile (editorial, not red cards).
- `result/widgets/report_qr_sheet.dart` — monochrome `QrImageView` content for the QR modal.
- `evidence/evidence_viewer_args.dart` — `EvidenceViewerArgs`.
- `evidence/evidence_viewer_screen.dart` — the EVIDENCE VIEWER screen.
- `evidence/widgets/evidence_image_view.dart` — `InteractiveViewer` + derived boxes + focus
  highlight, reduced-motion-aware zoom.

New tests (`apps/user_app/test/scan/`):
- `result_harness.dart` — fixtures, `FakeReportSharer`, `ThrowingScanAnalysisRunner`,
  `DeferredScanAnalysisRunner`, `SeededScanController`, `pumpReport`/`pumpEvidence`/`pumpProcessing`.
- `compliance_score_test.dart` — the three fixtures pin the deterministic score (100 / 11 / 75),
  severity-weight mapping, and the clamp-to-0 case.
- `report_finding_test.dart` — ordering/numbering/kind/status + `targetFieldLabel` mapping +
  `linkFinding` match / primary-image fallback / always-DERIVED.
- `analysis_result_screen_test.dart` — report renders for all three fixtures; Share invokes the
  fake sharer; Generate QR opens the QR modal; a finding action navigates to `/scan/evidence`.
- `scan_processing_screen_test.dart` — success renders phase caption + extracted panel then
  navigates to `/scan/result`; error shows the keyed `VeriqooErrorState`, no raw exception.
- `evidence_viewer_test.dart` — viewer renders `InteractiveViewer` + derived boxes; focusing a
  finding zooms (transform scale > 1); DERIVED note shows; "WHY THIS MATTERS" bottom sheet opens;
  empty evidence → `VeriqooEmptyState`.

## Files modified

`apps/user_app/`:
- `lib/features/scan/analysis_result_screen.dart` — premium COMPLIANCE REPORT.
  `AnalysisResultArgs` shape + `AnalysisResultScreen` class name PRESERVED (now `ConsumerWidget`).
  Save behavior UNCHANGED (same `SupabaseService().saveInspectionReport(analysis:, ocrText:,
  primaryImage:, imageUrl:)` call, lazily constructed).
- `lib/features/scan/scan_processing_screen.dart` — rewritten to drive the REAL pipeline (D1).
- `lib/features/scan/scan_screen.dart` — `_analyze` now hands off to `/scan/processing`
  (removed the inline runner call + now-unused imports `scan_analysis_runner.dart` and
  `compliance_analysis.dart`); a `_busy` guard prevents a double-push.
- `lib/app/routes.dart` — added `scanEvidenceSegment/Path/Name`.
- `lib/app/router.dart` — added the `/scan/evidence` child route + imports.
- `pubspec.yaml` (+ `pubspec.lock`) — `share_plus`, `qr_flutter`.
- `test/scan/scan_harness.dart` — added the keyed `/scan/processing` placeholder
  (`kScanProcessingRouteKey`).
- `test/scan/scanner_screen_test.dart` — updated: after capture + Analyze, asserts navigation to
  the keyed `/scan/processing` and that the runner is NOT called by `ScanScreen`.

`packages/shared_core/` (additive ONLY):
- `lib/design_system/foundations/veriqoo_icons.dart` — added `share`, `qrCode`, `flag`, `eye`,
  `zoomIn`, `shield` (`→ LucideIcons.{share,qrCode,flag,eye,zoomIn,shield}`). No
  removals/renames/signature changes; new `static const` cannot break any consumer.

Confirmed unmodified: all other `shared_core` files (especially `lib/services/*` and the
`saveInspectionReport` signature), and all of `apps/admin_web/**`.

## Deterministic compliance score (D2) — the formula, in code

Over the seven mandatory declaration fields `[productName, mrp, netQuantity, manufacturer,
address, packingDate, customerCare]` (N = 7):

- `presentCount` = count of those fields whose `value.trim()` is non-empty.
- `base = (presentCount / 7) * 100`.
- `missingPenalty = 6 * missingInformation.length`.
- `issuePenalty = Σ severityWeight(issue.severity)` over `possibleIssues`, where
  (lower-cased severity) `critical`/`high` → 12, `medium` → 8, `low` → 5, else → 8.
- `score = (base − missingPenalty − issuePenalty).clamp(0, 100).round()`.

Summary counts (D3): `verified = presentCount`, `flagged = possibleIssues.length`,
`missing = missingInformation.length`.

Pinned by `compliance_score_test.dart`:
- all-compliant fixture → **100** (verified 7, flagged 0, missing 0)
- missing-only fixture → **11** (base 2/7·100 ≈ 28.57, − 18; verified 2, missing 3)
- with-issues fixture → **75** (100 − 12 − 8 − 5; verified 7, flagged 3)

This is a pure PRESENTATION derivation — the analysis payload and the persisted report are
unchanged.

## VeriqooIcons additions

`share → LucideIcons.share`, `qrCode → LucideIcons.qrCode`, `flag → LucideIcons.flag`,
`eye → LucideIcons.eye`, `zoomIn → LucideIcons.zoomIn`, `shield → LucideIcons.shield`.
All six glyph names were verified to exist in the installed `lucide_icons_flutter 3.1.21`.

## Evidence linking — how it degrades when coordinates are absent (D4)

The backend returns no per-issue bounding boxes. `linkFinding` therefore synthesizes a
BEST-EFFORT association and ALWAYS marks it `derived = true`:

1. The finding's text (missing-declaration field, or the issue title/description/evidence/rule
   titles) is keyword-matched to a `DetectedFieldLabels` value via `targetFieldLabel`
   (`mrp`/`price` → MRP; `net`/`qty`/`quantity` → MANDATORY DECLARATION;
   `manufactured`/`mfg`/`marketed`/`packed` → MANUFACTURER; `batch`/`lot` → BATCH; else
   → PRODUCT NAME).
2. If a live-detection `DetectedField` with that label exists, its normalized rect is used to
   zoom/highlight (still DERIVED — the live boxes are approximate, not per-image authoritative).
3. If nothing matches, `field` is null and the viewer shows the primary image (index 0) with no
   fabricated box.

The viewer renders a visible "DERIVED — region inferred from live detection, not an exact
backend coordinate." note whenever a finding is in focus, and the same note appears in the
"WHY THIS MATTERS" sheet. No backend-precise bounding boxes are fabricated as authoritative.

## Design decisions (as implemented)

- **D1** — PROCESSING drives the analysis. `ScanScreen._analyze` validates evidence, sets
  analyzing, stops the camera stream, and pushes `/scan/processing`. The processing screen reads
  `scanState.evidence`, runs `scanAnalysisRunnerProvider`, and `pushReplacement`s `/scan/result`
  with the UNCHANGED `AnalysisResultArgs`. The Phase 5 scanner test was updated accordingly.
- **D2/D3** — deterministic score + summary counts (above).
- **D4** — best-effort, always-DERIVED evidence linking (above).
- **D5** — Actions: Share behind the injectable `ReportSharer` (fakeable); QR via
  `qr_flutter`'s `QrImageView` in a `VeriqooModal`; Save keeps the exact existing
  `SupabaseService` call; Report Issue → `/report-issue`. PDF DEFERRED.
- **D6** — additive icon-facade glyphs (above).
- **D7** — `SharePlusReportSharer` wraps the single
  `SharePlus.instance.share(ShareParams(text: ...))` call (share_plus v13 confirmed).
- **D8** — new `/scan/evidence` route (child of `/scan`).
- **D9** — all new user-facing strings centralized in `ResultStrings`.

Additional presentation choices: the QR code is rendered dark-on-light (black modules on a
white quiet zone) regardless of theme so it stays scannable (an inverted light-on-dark code is
not reliably scannable); still strictly monochrome. `ReportReference` uses a web-safe bounded
polynomial hash (mod 2^24) so the id is deterministic across runs and when compiled to JS.

## Verification checklist

- [x] `dart pub get` succeeds (both packages).
- [x] `dart analyze` → "No issues found!" (both packages; user_app includes `test/`).
- [x] Hermetic widget/unit tests written and KEPT (not run; `flutter test` denied).
- [x] No camera/Supabase/network/real-share in tests (fakes + seeded controller + in-memory XFiles).
- [x] `AnalysisResultArgs` shape, `AnalysisResultScreen` name, and the `saveInspectionReport`
      call preserved.
- [x] `apps/admin_web/**` and all `shared_core` files except the icon facade unmodified.
- [x] No commits; no worktree.
