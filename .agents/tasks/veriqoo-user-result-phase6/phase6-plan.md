# Phase 6 Implementation Plan — user_app OCR/AI Processing, Compliance Report & Evidence Viewer

Target package: `apps/user_app` (pub name `flutter_application_1`, internal imports
`package:flutter_application_1/...`). Design system consumed through the single barrel
`import 'package:shared_core/design_system/design_system.dart';`. Tokens via
`Theme.of(context).extension<VeriqooTokens>()!`; theme getters `VeriqooTheme.dark/.light`.

**Write scope.** Primary: `apps/user_app/**`. ALSO ALLOWED (additive only): new glyph
mappings in `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\design_system\foundations\veriqoo_icons.dart`
(the sole lucide importer). No other `shared_core` file may change (especially
`lib/services/*`), and `apps/admin_web/**` must not be touched. `shared_core` and the
`SupabaseService.saveInspectionReport` signature are PRESERVED — this phase changes
PRESENTATION only.

## Environment / verification bar (ABSOLUTE)

- Shell `flutter *` is DENIED. Use `dart` ONLY: `dart pub add`, `dart pub get`, `dart analyze`.
  Do NOT run `flutter build/test/run`.
- Acceptance bar for every item: `dart pub get` succeeds AND `dart analyze` reports
  **0 errors**, run on EVERY package modified (always `apps/user_app`; additionally
  `packages/shared_core` for the icon-facade item).
- Baseline confirmed green on 2026-… before this plan: `apps/user_app` and
  `packages/shared_core` both report `dart pub get` → "Got dependencies!" and
  `dart analyze` → "No issues found!" (Dart SDK 3.13.3, flutter_lints 5.0.0).
- Widget/unit tests are WRITTEN AND KEPT under `apps/user_app/test/` but NOT run here.
  `flutter test` and `flutter build web` are recorded DEFERRED with exact commands in the
  final verification item.
- No commits. No worktree (work in the main workspace).

## Carried-forward facts verified in the codebase (read before relying on them)

- `ComplianceAnalysis` (`packages/shared_core/lib/services/compliance_analysis.dart`):
  fields `productName, mrp, netQuantity, manufacturer, address, packingDate, customerCare`
  (all `String`), `missingInformation` (`List<String>`), `possibleIssues`
  (`List<ComplianceIssue>`), plus `bool get isCompliant`. `ComplianceIssue`:
  `title, description, severity` (free `String`), `ruleNumbers/ruleTitles` (`List<String>`),
  `legalBasis?`, `ocrEvidence?`, `verificationStatus` (`LegalVerificationStatus` enum:
  `legallyVerified, possibleConcern, cannotDetermine, generalObservation`).
- Scan session seam (`apps/user_app/lib/features/scan/scan_providers.dart`): app-scoped
  `final scanStateProvider = NotifierProvider<ScanController, ScanState>(ScanController.new);`.
  `ScanState` holds `List<EvidenceImage> evidence`, `int currentIndex`, `String liveOcrText`,
  `List<DetectedField> detectedFields`, `ScanPhase phase`, `bool isAnalyzing`; getters
  `XFile? primaryImage`, `EvidenceRole nextRole`. Controller: `addEvidence`, `retakeAt`,
  `deleteAt`, `setCurrent`, `setLiveOcr`, `advancePhase`, `setAnalyzing`, `reset`.
- `EvidenceImage` (`.../scan/model/evidence_image.dart`): `XFile file`, `EvidenceRole role`,
  `int sequence`, `String label`, `String get twoDigit` (`01/02/03`).
- `DetectedField` (`.../scan/model/detected_field.dart`): `Rect rectNormalized` (0..1),
  `String label` (one of `DetectedFieldLabels`: `PRODUCT NAME, MRP, BATCH, MANUFACTURER,
  MANDATORY DECLARATION`), `String? text`. `== / hashCode` implemented.
- Analysis pipeline (`.../scan/scan_analysis_runner.dart`): injectable
  `abstract ScanAnalysisRunner.run({required List<EvidenceImage> evidence,
  required String geminiApiKey}) -> Future<AnalysisResultArgs>`; production
  `GeminiScanAnalysisRunner` does per-image file OCR → `===== IMAGE n =====` combine →
  `LegalRulesRetrievalService` RAG (failures swallowed) → `GeminiAIAnalysisService` →
  `ComplianceAnalysis`. `final scanAnalysisRunnerProvider = Provider<ScanAnalysisRunner>(...)`;
  `String resolveGeminiApiKey()` resolves dotenv-first then `String.fromEnvironment`.
- Result route contract (`.../scan/analysis_result_screen.dart` +
  `.../app/router.dart`): `/scan/result` builds `AnalysisResultScreen(args: state.extra as
  AnalysisResultArgs)`. `AnalysisResultArgs { ComplianceAnalysis analysis; String ocrText;
  XFile? primaryImage; String? imageUrl; }`. `_saveReport` constructs `SupabaseService()`
  lazily and calls `saveInspectionReport(analysis:, ocrText:, primaryImage:, imageUrl:)`.
  KEEP `AnalysisResultArgs` and the class name `AnalysisResultScreen` (router + tests depend
  on both).
- Routes (`.../app/routes.dart`): `scanPath '/scan'`; children `scanCaptureSegment 'capture'`,
  `scanProcessingSegment 'processing'` (`scanProcessingPath '/scan/processing'`),
  `scanResultSegment 'result'` (`scanResultPath '/scan/result'`). `reportIssuePath
  '/report-issue'` exists (ReportIssueScreen is a Phase 9 placeholder) — Report Issue just
  navigates there.
- Design system APIs verified: `VeriqooScore({required int value, int maxValue=100,
  double size=120, double strokeWidth=6, Duration duration, String? caption})` (radial +
  count-up, reduced-motion aware); `VeriqooStatus({required VeriqooStatusKind kind,
  double markerSize=16, bool showLabel=true})` with kinds `verified/flag/missing/violation`
  (labels VERIFIED / FLAG / NOT DETECTED / VIOLATION); `VeriqooSectionHeader({required String
  title, String? subtitle, Widget? action})`; `VeriqooDivider()` / `.vertical()`;
  `VeriqooAppBar({required String title, Widget? action, VoidCallback? onBack, bool
  showBack=true})` (auto-hides back when not poppable); `VeriqooButton({required String label,
  VoidCallback? onPressed, VeriqooButtonVariant variant, VeriqooButtonSize size, IconData?
  icon, bool loading, bool expand, String? semanticLabel})`; `VeriqooIconButton({required
  IconData icon, required String semanticLabel, VoidCallback? onPressed, variant, double
  iconSize=20, double size=44})`; `VeriqooBottomSheet.show<T>(context, {required Widget child,
  String? title, bool isScrollControlled})`; `VeriqooModal.show<T>(context, {required String
  title, required Widget child, List<Widget> actions, bool showClose, bool
  barrierDismissible})`; `VeriqooLoading({String message, Size size})`;
  `VeriqooEmptyState({required IconData icon, required String title, String? message, Widget?
  action})`; `VeriqooErrorState({String title, String? message, VoidCallback? onRetry, String
  retryLabel, IconData icon})`; `VerificationScan({Widget? child, List<ScanField> fields, bool
  enabled, bool loop, ...})` + `ScanField(Rect rect, {String? label})`; `OCROverlay` (a
  decorative `BackgroundEffect`, NOT data-parameterized); `VeriqooMotion.reduceMotion(context)`,
  `VeriqooMotion.base/fast/cinematic`, `VeriqooType.{display,h1,h2,h3,bodyL,body,caption,meta,
  mono}`, `VeriqooSpacing.sNN`, `VeriqooRadius.{smAll,mdAll,top()}`.
- `VeriqooIcons` currently exposes: `home, scan, history, profile, back, close, chevronRight,
  settings, search, check, alert, verified, violation, camera, upload`. It LACKS share, qr,
  flag, view/eye, zoom. The lucide package (`lucide_icons_flutter 3.1.21`, already the sole
  importer) DOES define `share`, `qrCode`, `flag`, `eye`, `zoomIn`, `shield` — confirmed.
- Phase 5 scan widgets reused as-is: `DetectionBoxesOverlay` / `DetectionBoxesPainter`
  (`.../scan/widgets/detection_boxes.dart`) paint thin hairline rects from a
  `List<DetectedField>` (normalized 0..1) — reused for the evidence viewer's derived boxes.
- Test harness pattern (`apps/user_app/test/scan/scan_harness.dart`): in-memory `XFile` via
  `XFile.fromData(kPngBytes, ...)`; fakes override `scanCameraControllerProvider`,
  `scanAnalysisRunnerProvider`, `scanGalleryPickerProvider`; mounts under a minimal `GoRouter`
  + `MaterialApp.router(theme: VeriqooTheme.dark)`; uses fixed `pump`s (never
  `pumpAndSettle`, because the scan motif loops). Reuse this pattern.

## Design decisions (presentation-layer; the task spec is the approved design)

- **D1 — Processing drives the analysis.** The analysis call is relocated OUT of
  `ScanScreen._analyze` INTO the rewritten `ScanProcessingScreen`. `ScanScreen` now validates
  evidence, sets analyzing, stops the stream, and `push`es `/scan/processing`; the processing
  screen reads `scanState.evidence`, runs `scanAnalysisRunnerProvider`, and
  `pushReplacement`s `/scan/result` with the UNCHANGED `AnalysisResultArgs`. Rationale: the
  deliverable requires the processing screen to drive the real pipeline and then transition to
  the result. The Phase 5 `scanner_screen_test` navigation expectation is updated accordingly
  (it now asserts navigation to a keyed `/scan/processing`; the runner is exercised by the new
  processing test). The pipeline, result route, args, and `SupabaseService` behavior are
  otherwise unchanged.
- **D2 — Deterministic compliance score (0–100), documented in code.** Over the 7 mandatory
  declaration fields `[productName, mrp, netQuantity, manufacturer, address, packingDate,
  customerCare]` (N=7): `base = (presentCount / 7) * 100` where present = `value.trim()` is
  non-empty; `missingPenalty = 6 * missingInformation.length`; `issuePenalty = Σ severity
  weight per possibleIssue` with `high|critical=12, medium=8, low=5, default=8`
  (severity string lower-cased); `score = (base − missingPenalty − issuePenalty).clamp(0,100)
  .round()`. Pure, presentation-layer derivation (NOT a backend change). Determinism verified
  by the unit test on the three fixtures (all-compliant → 100; missing-only → reduced;
  with-issues → reduced).
- **D3 — Summary counts.** `verified = presentCount` (fields detected), `flagged =
  possibleIssues.length`, `missing = missingInformation.length`, rendered with `VeriqooStatus`
  kinds `verified` / `flag` / `missing`.
- **D4 — Evidence linking is best-effort and marked DERIVED.** `scanState.detectedFields`
  come from the live-OCR stream (approximate, not per-image authoritative). A finding is
  linked to an evidence image/field by keyword/field-name matching against `DetectedFieldLabels`;
  when matched, the field's normalized rect is highlighted; when not, the whole image is shown.
  Every synthesized association is flagged "DERIVED" in the UI. No backend-precise bounding
  boxes are fabricated as authoritative.
- **D5 — Actions.** Share is isolated behind an injectable `ReportSharer` (over `share_plus`)
  so widget tests never open a real share sheet; QR via `qr_flutter`'s `QrImageView` inside a
  `VeriqooModal`; Save keeps the EXACT existing `SupabaseService().saveInspectionReport(...)`
  call (lazy construct; not exercised in hermetic tests); Report Issue navigates to
  `/report-issue`. A downloadable PDF (`printing`/`pdf`) is DEFERRED as a follow-up (NOT added)
  to keep the dependency surface analyze-clean and simple.
- **D6 — Icon facade additions (additive only):** `share` (→ `LucideIcons.share`), `qrCode`,
  `flag`, `eye`, `zoomIn`, `shield`. No removals/renames/signature changes.
- **D7 — share_plus API.** share_plus 11/12 uses `SharePlus.instance.share(ShareParams(text:
  ...))`. The `ReportSharer` concrete impl wraps exactly this one call; after `dart pub add`,
  confirm the resolved major version and use `ShareParams` (v10+). (Content was rephrased for
  compliance with licensing restrictions.)
- **D8 — New route `/scan/evidence`** (child of `/scan`) for the Evidence Viewer, reached from
  each finding's "View evidence"/"Inspect" and from a report-level "VIEW EVIDENCE" action.
- **D9 — Copy centralization.** All new user-facing strings live in `ResultStrings`
  (`static const`) mirroring `HomeStrings`, ready for later localization.

---

# Implementation Plan

- [ ] 1. Add the `share_plus` and `qr_flutter` dependencies (no PDF deps).
      Run `dart pub add share_plus qr_flutter` in `apps/user_app`; let pub resolve compatible
      versions (expected `qr_flutter ^4.1`, `share_plus` 11/12). Do NOT add `printing`/`pdf`
      (PDF deferred per D5). No code uses them yet, so analysis stays green.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\pubspec.yaml` (+ `pubspec.lock`).
      Verify: `dart pub get` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`) → "Got
      dependencies!"; `dart analyze` (same CWD) → "No issues found!".

- [ ] 2. Extend the `VeriqooIcons` facade additively with the glyphs this phase needs.
      Add `static const IconData share = LucideIcons.share; qrCode = LucideIcons.qrCode;
      flag = LucideIcons.flag; eye = LucideIcons.eye; zoomIn = LucideIcons.zoomIn; shield =
      LucideIcons.shield;` to the existing abstract final `VeriqooIcons`. Additive ONLY — no
      removals/renames. This is the only `shared_core` edit permitted; it keeps `admin_web`
      unaffected (new static consts cannot break consumers).
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\design_system\foundations\veriqoo_icons.dart`
      Verify: `dart pub get` + `dart analyze` (CWD `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core`)
      → "No issues found!" (0 errors, so `admin_web` is unaffected); then `dart analyze`
      (CWD `apps\user_app`) → "No issues found!".

- [ ] 3. Add the result domain layer: centralized copy, the deterministic score, and the
      report reference.
      `ResultStrings` — `static const` copy for the processing, report, and evidence screens
      (headers "COMPLIANCE REPORT"/"ANALYZING"/"EVIDENCE", phase captions, section titles,
      action labels, "Not detected", finding labels "MISSING DECLARATION"/"POTENTIAL
      VIOLATION", "View evidence"/"Inspect", "WHY THIS MATTERS", the error copy "ANALYSIS
      INTERRUPTED" / "… TRY AGAIN", "DERIVED" note). `ComplianceScore` — immutable
      `{int score, int verified, int flagged, int missing, int mandatoryTotal}` with factory
      `ComplianceScore.fromAnalysis(ComplianceAnalysis)` implementing the D2 formula (document
      the formula in a doc comment). `ReportReference` — immutable `{String id, String
      qrPayload}` with `ReportReference.fromAnalysis(ComplianceAnalysis, ComplianceScore)`:
      `id` is a deterministic `'VQ-' + <6 hex of a stable hash of
      productName+mrp+netQuantity+manufacturer>`; `qrPayload` a compact
      `VERIQOO|{id}|{productName}|score={score}|v={verified}|f={flagged}|m={missing}` string.
      All three are pure (no Flutter widget imports beyond `meta`/`foundation`).
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\result_strings.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\compliance_score.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\report_reference.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 4. Add the findings model + best-effort evidence linker (pure, testable).
      `enum ReportFindingKind { missingDeclaration, potentialViolation }`. `ReportFinding`
      immutable `{int number, ReportFindingKind kind, String title, String? detail,
      VeriqooStatusKind status, ComplianceIssue? issue, String? missingField}`. Static
      `List<ReportFinding> ReportFinding.fromAnalysis(ComplianceAnalysis)`: emit each
      `missingInformation` entry first as `missingDeclaration` (status
      `VeriqooStatusKind.missing`), then each `possibleIssue` as `potentialViolation`
      (status `violation` when `verificationStatus == legallyVerified`, else `flag`),
      numbered 1-based across the combined list. `EvidenceLink` immutable `{int imageIndex,
      DetectedField? field, bool derived, String? reason}` with pure
      `EvidenceLink linkFinding(ReportFinding, {required List<DetectedField> detectedFields,
      required int evidenceCount})`: keyword-match the finding's `missingField`/issue text to a
      `DetectedFieldLabels` value (mrp/price→MRP, net|qty|quantity→MANDATORY DECLARATION,
      manufactured|mfg|marketed|packed→MANUFACTURER, batch|lot→BATCH, else PRODUCT NAME); if a
      matching `DetectedField` exists use its rect (`derived=true`), else `field=null,
      imageIndex=0, derived=true`. Keep it `shared_core`-import-light (only
      `VeriqooStatusKind` from the barrel + the scan models).
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\report_finding.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 5. Add the injectable report sharer over `share_plus`.
      `abstract class ReportSharer { Future<void> share(String text); }` and
      `SharePlusReportSharer implements ReportSharer` whose `share` makes the single call
      `SharePlus.instance.share(ShareParams(text: text))` (per D7; confirm the resolved
      share_plus major and use `ShareParams`). Provide
      `final reportSharerProvider = Provider<ReportSharer>((ref) => SharePlusReportSharer());`
      so widget tests override it with a fake that records the payload (never opens a share
      sheet).
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\report_share_service.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 6. Build the evidence image view widget (InteractiveViewer + derived overlays).
      `EvidenceViewerArgs` immutable `{int initialImageIndex, ReportFinding? focusFinding}`
      (default `initialImageIndex: 0`, `focusFinding: null`). `EvidenceImageView` — a
      `StatefulWidget` that renders one `EvidenceImage` via `FutureBuilder<Uint8List>` +
      `Image.memory` (VeriqooLoading while decoding) wrapped in an `InteractiveViewer`
      (own `TransformationController`), with a stacked `DetectionBoxesOverlay(fields:
      detectedFields)` for the DERIVED boxes and a thin focus-highlight (reuse
      `DetectionBoxesPainter` styling or a small `CustomPainter`) for an optional focused
      normalized `Rect`. Expose `focusRect` + an `animateToRect(Rect?)` that sets the
      controller matrix to zoom/pan to the rect, jumping instantly when
      `VeriqooMotion.reduceMotion(context)` is true (else `VeriqooMotion.base`). Give the
      InteractiveViewer and the "why this matters" trigger stable `Key`s for tests
      (`kEvidenceInteractiveViewerKey`, `kEvidenceWhyButtonKey`).
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\evidence\evidence_viewer_args.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\evidence\widgets\evidence_image_view.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 7. Build the Evidence Viewer screen.
      `EvidenceViewerScreen extends ConsumerStatefulWidget` taking `EvidenceViewerArgs`. Reads
      `scanState.evidence`; when empty renders `VeriqooEmptyState(icon: VeriqooIcons.scan,
      ...)`. Otherwise: `VeriqooAppBar(title: ResultStrings.evidenceTitle)`; a selected image
      shown via `EvidenceImageView`; when `evidence.length > 1` a thin selector strip (reuse
      the tray thumbnail style or a simple `Row` of numbered tiles) switching the current
      image; computes `EvidenceLink` for `focusFinding` via `linkFinding(...)` and, after first
      layout, calls `animateToRect(link.field?.rectNormalized)` to zoom to the region and shows
      the "DERIVED" meta note when `link.derived`. A "WHY THIS MATTERS" affordance opens
      `VeriqooBottomSheet.show(context, title: ResultStrings.whyThisMatters, child: ...)` with a
      plain-language explanation built from the finding (issue `description`/`legalBasis`/
      `ruleTitles`, or a mapping for missing declarations in `ResultStrings`). Monochrome,
      hairlines, reduced-motion aware; `textTertiary` only for the DERIVED/meta note.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\evidence\evidence_viewer_screen.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 8. Wire the `/scan/evidence` route.
      Add to `AppRoutes`: `scanEvidenceSegment = 'evidence'`, `scanEvidencePath =
      '/scan/evidence'`, `scanEvidenceName = 'scanEvidence'`. In `router.dart`, add a child
      `GoRoute` under the existing `/scan` branch (sibling of `capture`/`processing`/`result`)
      building `EvidenceViewerScreen(args: state.extra as EvidenceViewerArgs? ?? const
      EvidenceViewerArgs())`. Add the `EvidenceViewerScreen` import. Leave all existing routes
      intact.
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\app\routes.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\app\router.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 9. Build the report sub-widgets: product-details panel, finding tile, QR sheet.
      `ProductDetailsPanel` — six sharp HAIRLINE rows (MRP, Net Quantity, Manufacturer,
      Address, Packing Date, Customer Care) using `VeriqooDivider` between rows, label in
      `VeriqooType.meta`/`textSecondary` and value in `VeriqooType.body`
      (`VeriqooType.mono` for MRP), showing `ResultStrings.notDetected` in `textTertiary`
      when empty. NOT rounded cards. `ReportFindingTile` — one numbered finding: big mono
      `01`/`02` ordinal (`textTertiary`), the kind label ("MISSING DECLARATION" / "POTENTIAL
      VIOLATION") in `VeriqooType.meta`, `VeriqooStatus(kind: finding.status)`, title/detail in
      strong `VeriqooType.body`, and a trailing `VeriqooButton(variant: ghost)` "View evidence"
      (missing) / "Inspect" (violation) that invokes an `onInspect` callback; thin
      `VeriqooDivider`s, NOT red cards. `ReportQrSheet` — content for a `VeriqooModal` wrapping
      `QrImageView(data: payload, size: ..., backgroundColor:/eyeStyle: monochrome)` plus the
      reference id in `VeriqooType.mono`. Stable `Key`s on each finding tile's action and on
      the QR widget for tests.
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\widgets\product_details_panel.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\widgets\report_finding_tile.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\result\widgets\report_qr_sheet.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 10. Rewrite the COMPLIANCE REPORT screen (`AnalysisResultScreen`), preserving the args +
      class name + Save behavior.
      Keep `class AnalysisResultArgs {...}` and `class AnalysisResultScreen extends
      ConsumerWidget` (convert from `StatelessWidget` to `ConsumerWidget` to read
      `reportSharerProvider` and `scanStateProvider`). Compose, top→bottom, inside a
      `Scaffold(backgroundColor: tokens.bg)` + `VeriqooAppBar(title:
      ResultStrings.reportTitle)` + scrollable body: (a) header — "COMPLIANCE REPORT" label,
      product name (`analysis.productName` or `ResultStrings.unknownProduct`), meta line
      `${reference.id} · ${formattedDate}` in `VeriqooType.mono`/`textTertiary`; (b) a large
      centered `VeriqooScore(value: score.score, caption: 'SCORE', size: 160)` (count-up on
      load); (c) the summary row — three `VeriqooStatus` chips with counts
      (`verified`/`flag`/`missing`); (d) `VeriqooSectionHeader(title: 'Product details')` +
      `ProductDetailsPanel`; (e) `VeriqooSectionHeader(title: 'Findings')` + a
      `ReportFindingTile` per `ReportFinding.fromAnalysis(analysis)`, each `onInspect` →
      `context.push(AppRoutes.scanEvidencePath, extra: EvidenceViewerArgs(initialImageIndex:
      link.imageIndex, focusFinding: finding))` using `linkFinding(..., detectedFields:
      scanState.detectedFields, evidenceCount: scanState.evidence.length)`; when there are no
      findings show a compliant confirmation line; (f) an actions block — `VeriqooButton`s
      Share (`VeriqooIcons.share` → `ref.read(reportSharerProvider).share(reference.qrPayload
      / or a richer summary)`), Generate QR (`VeriqooIcons.qrCode` →
      `VeriqooModal.show(..., child: ReportQrSheet(payload: reference.qrPayload, id:
      reference.id))`), Save (`VeriqooIcons.upload` → the UNCHANGED `_saveReport` that calls
      `SupabaseService().saveInspectionReport(analysis:, ocrText: args.ocrText, primaryImage:
      args.primaryImage, imageUrl: args.imageUrl)`), Report Issue (`VeriqooIcons.flag` →
      `context.push(AppRoutes.reportIssuePath)`), and a "VIEW EVIDENCE"
      (`VeriqooIcons.eye`) → `context.push(AppRoutes.scanEvidencePath, extra: const
      EvidenceViewerArgs())`. Monochrome; hairlines over shadows; copy from `ResultStrings`.
      Compute `score`/`reference`/`findings` once at the top of `build`.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\analysis_result_screen.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 11. Rewrite the PROCESSING screen (`ScanProcessingScreen`) to drive the real analysis.
      Convert to `ConsumerStatefulWidget`. On `initState`, schedule (post-frame) `_run()`:
      read `evidence = ref.read(scanStateProvider).evidence`; if empty, show the error state
      with a back-to-scan action; else `ref.read(scanStateProvider.notifier).setAnalyzing(true)`,
      start a local reduced-motion-aware phase ticker stepping the displayed `ScanPhase`
      `readingLabel → extractingDeclarations → verifyingCompliance` (a `Timer.periodic` of
      ~1.1s, cancelled on completion/dispose; under reduced motion jump straight to
      `verifyingCompliance`), then `await ref.read(scanAnalysisRunnerProvider).run(evidence:
      evidence, geminiApiKey: resolveGeminiApiKey())`; on success
      `controller.advancePhase(complete: true)` and
      `context.pushReplacement(AppRoutes.scanResultPath, extra: args)`; on
      `AIAnalysisException` or any error, `setState` an error flag (never surface the raw
      exception). Layout: `Scaffold(bg)` + `VeriqooAppBar(title: ResultStrings.processingTitle)`
      + body = when error, `VeriqooErrorState(title: ResultStrings.analysisInterruptedTitle,
      message: ResultStrings.analysisInterruptedMessage, onRetry: _run)`; else a column with a
      bounded `VerificationScan` scanning hero (NO `CircularProgressIndicator`), the current
      phase caption (large, animated-switch, reduced-motion safe), and a structured
      EXTRACTED-TEXT technical panel of labelled rows PRODUCT / MRP / NET QUANTITY /
      MANUFACTURER populated from `scanState.detectedFields` (matched by `DetectedFieldLabels`)
      and `scanState.liveOcrText`, showing a "READING…"/"—" placeholder per row until present.
      Always `setAnalyzing(false)` and cancel the ticker in a `finally`/`dispose`. Stable
      `Key`s: `kProcessingPhaseCaptionKey`, `kProcessingExtractPanelKey`,
      `kProcessingErrorStateKey`.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\scan_processing_screen.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 12. Rewire `ScanScreen._analyze` to navigate into the processing screen (D1).
      Replace the inline `scanAnalysisRunnerProvider.run(...)` + `push(scanResultPath)` block in
      `_analyze` with: keep the empty-evidence guard SnackBar; then
      `controller.setAnalyzing(true)`, `await _camera.stopImageStream()`, and
      `router.push(AppRoutes.scanProcessingPath)`. Remove the now-unused
      `scanAnalysisRunnerProvider` / `AnalysisResultArgs` / `resolveGeminiApiKey` imports from
      `scan_screen.dart` if they become unused (and the `_busy` handling that wrapped the inline
      run — keep a brief guard so double-taps don't double-push). All other Phase 5 scanner
      behavior (capture, tray, flash, gallery, detection boxes, degrade note) is unchanged.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\scan_screen.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 13. Extend the hermetic test harness (fixtures + fakes + seeding) and update the scanner
      harness route map.
      In a new `result_harness.dart`: three `ComplianceAnalysis` fixtures —
      `fixtureAllCompliant()` (all 7 fields present, no missing, no issues),
      `fixtureMissingOnly()` (some fields empty + non-empty `missingInformation`, no issues),
      `fixtureWithIssues()` (all fields present, `possibleIssues` with mixed severity +
      `verificationStatus`); a `FakeReportSharer implements ReportSharer` recording the last
      payload; a `SeededScanController extends ScanController` whose `build()` returns a
      `ScanState` pre-populated with a fake evidence list + sample `detectedFields` (so the
      processing/evidence screens see evidence without a camera); `pumpReport(tester, {analysis,
      sharer})` mounting `AnalysisResultScreen(args: AnalysisResultArgs(analysis:, ocrText:
      'OCR', primaryImage: stubImage()))` under a `GoRouter` with keyed `/scan/evidence` +
      `/report-issue` placeholders and `MaterialApp.router(theme: VeriqooTheme.dark)`,
      overriding `reportSharerProvider` and `scanStateProvider` (seeded); and `pumpEvidence(...)`
      / `pumpProcessing(...)` helpers using the seeded controller and an overridden
      `scanAnalysisRunnerProvider`. Update `scan_harness.dart`'s `pumpScanner` router to add a
      keyed `/scan/processing` placeholder (`kScanProcessingRouteKey`) alongside the existing
      `/scan/result` one. Reuse `stubImage()`/`kPngBytes`. Use fixed `pump`s only.
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\result_harness.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\scan_harness.dart` (modify)
      Verify: `dart analyze` (CWD `apps\user_app`, which includes `test/`) → "No issues found!".

- [ ] 14. Write the pure unit tests (kept, not run here).
      `compliance_score_test.dart`: assert `ComplianceScore.fromAnalysis` on the three fixtures
      yields the exact deterministic ints from the D2 formula (all-compliant → 100; the
      missing-only and with-issues fixtures → their computed reduced values) and that
      `verified/flagged/missing` counts match. `report_finding_test.dart`:
      `ReportFinding.fromAnalysis` ordering/numbering/kind/status (missing first, then issues;
      `legallyVerified` → `violation` else `flag`) and `linkFinding` keyword→label matching,
      `derived == true` always, and the `field == null, imageIndex == 0` fallback when nothing
      matches.
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\compliance_score_test.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\report_finding_test.dart`
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 15. Write the widget tests (kept, not run here) and update the Phase 5 scanner test.
      `analysis_result_screen_test.dart`: for each of the three fixtures the report renders —
      "COMPLIANCE REPORT" header + product name, a `VeriqooScore`, the three `VeriqooStatus`
      summary chips, the `ProductDetailsPanel` ("Not detected" on empties for the missing-only
      fixture), a `ReportFindingTile` per finding (none for all-compliant), and the action
      buttons; tapping Share invokes `FakeReportSharer` (records payload, no real sheet);
      tapping Generate QR opens the modal with a `QrImageView`; tapping a finding's
      "View evidence"/"Inspect" navigates to the keyed `/scan/evidence`; `tester.takeException()`
      is null and Supabase/network are never touched (Save not tapped).
      `scan_processing_screen_test.dart`: with the seeded controller + a `FakeScanAnalysisRunner`
      (success) the screen renders the phase caption + extracted-text panel and, after fixed
      pumps, navigates to the keyed `/scan/result`; with a runner that throws
      `AIAnalysisException` it shows the `VeriqooErrorState` (keyed) and never a raw exception.
      `evidence_viewer_test.dart`: with the seeded evidence set the viewer renders an
      `InteractiveViewer` + derived boxes, focusing a finding changes the transform
      (tap-to-zoom), the DERIVED note shows, and the "WHY THIS MATTERS" `VeriqooBottomSheet`
      opens; empty evidence shows `VeriqooEmptyState`. Update `scanner_screen_test.dart`: after
      capture + Analyze, assert navigation to the keyed `/scan/processing` (the runner is no
      longer called by `ScanScreen`). All use fixed `pump`s, never `pumpAndSettle`.
      Files:
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\analysis_result_screen_test.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\scan_processing_screen_test.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\evidence_viewer_test.dart`,
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\test\scan\scanner_screen_test.dart` (modify)
      Verify: `dart analyze` (CWD `apps\user_app`) → "No issues found!".

- [ ] 16. Record the verification + deferred-command report and confirm no out-of-scope drift.
      Write `phase6-verification.md` capturing: `dart pub get` success and `dart analyze`
      "No issues found!" for `apps/user_app` AND `packages/shared_core` (icon facade); the
      added deps (`share_plus`, `qr_flutter`) and resolved versions; the design decisions
      D1–D9 (especially the processing-drives-analysis rewrite and the scanner-test navigation
      update, the deterministic score formula, best-effort DERIVED evidence linking, and PDF
      DEFERRED); and the DEFERRED commands verbatim — `flutter test` (CWD
      `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`) and `flutter build web` (same CWD) — stated
      as NOT run under the `flutter` deny, with the note that live/real analysis, the native
      share sheet, and Supabase save are runtime-unverified by design (hermetic fakes only).
      Confirm `apps/admin_web/**` and all `shared_core` files except the icon facade are
      unmodified.
      Files: `c:\WorkSpace\Ajinkya\Veriqoo\.agents\tasks\veriqoo-user-result-phase6\phase6-verification.md`
      Verify: `dart pub get` + `dart analyze` (CWD `apps\user_app`) → "No issues found!";
      `dart analyze` (CWD `packages\shared_core`) → "No issues found!".

## File-set summary

New (`c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\lib\features\scan\`):
- `result\result_strings.dart`, `result\compliance_score.dart`, `result\report_reference.dart`
- `result\report_finding.dart`, `result\report_share_service.dart`
- `result\widgets\product_details_panel.dart`, `result\widgets\report_finding_tile.dart`,
  `result\widgets\report_qr_sheet.dart`
- `evidence\evidence_viewer_args.dart`, `evidence\evidence_viewer_screen.dart`,
  `evidence\widgets\evidence_image_view.dart`

Modified (`apps\user_app\`):
- `lib\features\scan\analysis_result_screen.dart` (premium report; args + class name + Save
  preserved)
- `lib\features\scan\scan_processing_screen.dart` (drives the real analysis)
- `lib\features\scan\scan_screen.dart` (`_analyze` → navigate to `/scan/processing`)
- `lib\app\routes.dart`, `lib\app\router.dart` (add `/scan/evidence`)
- `pubspec.yaml` (+ `pubspec.lock`) (`share_plus`, `qr_flutter`)

Modified (additive, `packages\shared_core\`):
- `lib\design_system\foundations\veriqoo_icons.dart` (+ `share, qrCode, flag, eye, zoomIn,
  shield`)

New / modified tests (`apps\user_app\test\scan\`):
- `result_harness.dart` (new), `compliance_score_test.dart` (new),
  `report_finding_test.dart` (new), `analysis_result_screen_test.dart` (new),
  `scan_processing_screen_test.dart` (new), `evidence_viewer_test.dart` (new),
  `scan_harness.dart` (modify: keyed `/scan/processing`), `scanner_screen_test.dart`
  (modify: assert `/scan/processing` navigation)

Task artifacts (outside the code tree):
- `.agents\tasks\veriqoo-user-result-phase6\phase6-plan.md` (this file)
- `.agents\tasks\veriqoo-user-result-phase6\phase6-verification.md` (final item)

Unchanged (do NOT edit): all of `packages\shared_core` except the icon facade (especially
`lib\services\*` and `SupabaseService.saveInspectionReport`), `apps\admin_web\**`,
`AnalysisResultArgs`'s shape, and the `/scan/result` route contract.

## DEFERRED (record verbatim; NOT run under the `flutter` deny)

Run on a machine where `flutter` is permitted, CWD `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`:

```
flutter test
```

```
flutter build web
```

PDF export (`printing`/`pdf`) is a DEFERRED follow-up (not added this phase).
