# Phase 5 Verification — user_app Scanner (Full-Screen Camera Inspection Instrument)

Scope: `apps/user_app` only. `packages/shared_core` and `apps/admin_web` were NOT
modified. No commits performed.

## Commands run (CWD `apps/user_app`)

### `dart pub get`
Result: SUCCESS — "Got dependencies!" (exit 0). No new dependencies added in this
step (the `camera: ^0.12.1` dep + native config were already applied in
`phase5-setup.md`); `pub get` only resolved the existing lockfile.

### `dart analyze`
Result: SUCCESS — **"No issues found!"** (0 errors, 0 warnings, 0 infos, exit 0).
This covers `lib/` and `test/` (the `test/` tree is part of the analyzed package).

## Environment constraint honored

Shell `flutter *` is DENIED, so only `dart` was used (`dart pub get`, `dart analyze`).
`flutter build`/`run`/`test` were NOT invoked. Widget/logic tests are written and
KEPT but NOT run here.

## DEFERRED commands (verbatim — NOT run under the `flutter` deny)

Run these on a machine where `flutter` is permitted, with CWD `apps/user_app`:

```
flutter test
```

```
flutter build web
```

Both are deferred solely because of the workspace `flutter *` deny; the code
compiles cleanly under `dart analyze` and the tests are hermetic (no real camera,
no `Supabase.instance`, no network).

## Runtime-unverified: live-stream OCR

The live-stream OCR path is implemented but could NOT be exercised without a device
and `flutter run` (which the `flutter` deny forbids). Specifically unverified at
runtime:

- `CameraPackageController.startImageStream` wrapping each `CameraImage` into a
  platform-agnostic `ScanCameraFrame` (Android: NV21 single plane + sensor-rotation;
  iOS: BGRA8888).
- `LiveOcrAnalyzer.analyze` → `buildInputImage(frame)` → `TextRecognizer.processImage`
  → `mapBlocksToFields` on a real camera stream.
- `ThrottledOcrRunner` behavior against real-time frame cadence (min interval 350ms,
  in-flight drop).

What IS verified without a device (unit tests, kept):
- `buildInputImage(frame).toJson()` asserts `image_format` / `rotation` /
  `bytes_per_row` / `width` / `height` for an Android NV21 frame and an iOS BGRA
  frame — per-platform `InputImage` construction is correct.
- `mapBlocksToFields` keyword → label mapping and 0..1 rect normalization.
- `ThrottledOcrRunner` drops in-flight frames and enforces the min interval.

## Platform-degradation behavior

- On web (`kIsWeb`) or when `availableCameras()` is empty / `CameraController`
  initialization throws, `CameraPackageController` sets `isInitialized`/
  `supportsLiveOcr` to false, `buildPreview()` returns a `tokens.bgTrue` placeholder,
  and `startImageStream` is a no-op. The scanner degrades to preview + manual
  capture + gallery with NO live detection boxes — it never blocks or crashes.
- `ScanScreen` hides the `DetectionBoxesOverlay` when live OCR is unsupported and
  shows a meta-style "LIVE DETECTION UNAVAILABLE ON THIS PLATFORM — CAPTURE MANUALLY"
  note. All plugin calls in the real controller are wrapped in try/catch and log via
  `debugPrint`.

## Camera native-config edits

None in this step. The camera dependency and native config
(`AndroidManifest.xml` CAMERA permission, iOS `NSCameraUsageDescription`, Android
`minSdk` left dynamic) were applied in `phase5-setup.md` and are unchanged here.

## scanState API (Phase 6 evidence-viewer seam)

`lib/features/scan/scan_providers.dart` — provider name/type preserved:
`final scanStateProvider = NotifierProvider<ScanController, ScanState>(ScanController.new);`

`ScanState` (immutable):
- `List<EvidenceImage> evidence` — ordered, role-tagged captured images (the Phase 6
  hand-off). Each `EvidenceImage`: `XFile file`, `EvidenceRole role`, `int sequence`
  (1-based), `String label`, `String get twoDigit` (`01/02/03`).
- `int currentIndex` — highlighted tray tile.
- `String liveOcrText` — latest live-OCR raw text.
- `List<DetectedField> detectedFields` — latest live-OCR label regions
  (`Rect rectNormalized` 0..1, `String label`, `String? text`).
- `ScanPhase phase` — current live-scan phase.
- `bool isAnalyzing`.
- Getters: `XFile? primaryImage` (`evidence.first.file` or null),
  `EvidenceRole nextRole`.

`ScanController` methods:
- `addEvidence(XFile file, {EvidenceRole? role})` — auto-sequences + auto-roles
  front/back/side/additional; selects the new tile.
- `retakeAt(int index, XFile file)` — replaces, preserving role/sequence.
- `deleteAt(int index)` — removes + re-sequences.
- `setCurrent(int index)`.
- `setLiveOcr(String text, List<DetectedField> fields)`.
- `advancePhase({bool? capturing, bool? analyzing, bool complete = false})` —
  delegates to the pure `nextScanPhase(...)`.
- `setAnalyzing(bool value)`.
- `reset()`.

Phase 6 reads `scanState.evidence` (all images, with role/label/sequence) for the
evidence viewer. Phase 5 passes only `evidence.first.file` into the existing
analysis + save pipeline, so `SupabaseService.saveInspectionReport`'s signature is
UNCHANGED (extra evidence lives in `scanState` for Phase 6).

## Hand-off into the existing pipeline (behavior preserved)

`lib/features/scan/scan_analysis_runner.dart` relocates the carried-forward
`ScanScreen.analyzeProduct` logic verbatim into `GeminiScanAnalysisRunner`
(injectable via `scanAnalysisRunnerProvider`): per-image file OCR via
`TextRecognizer` + `InputImage.fromFilePath`, the same `===== IMAGE n =====`
combination, RAG via `LegalRulesRetrievalService` (failures swallowed), Gemini via
`GeminiAIAnalysisService.analyzeProductLabel`, services disposed in `finally`, and
returns the UNCHANGED `AnalysisResultArgs(analysis, ocrText, primaryImage:
evidence.first.file)`. `ScanScreen` routes to `AppRoutes.scanResultPath` →
`AnalysisResultScreen` exactly as before. The result/processing screens are
untouched and remain reachable.

## Design-system discrepancy / workaround notes

1. **Missing glyphs** (`VeriqooIcons` has no flash/gallery/add/delete/retake):
   - Gallery → `VeriqooIcons.upload` (semanticLabel "Open gallery").
   - Add evidence → `VeriqooIcons.camera` ("+ ADD" tile).
   - Delete → `VeriqooIcons.close`; Retake → `VeriqooIcons.history`.
   - Flash → NO bolt glyph; rendered as a meta-style text toggle
     ("FLASH ON" / "FLASH OFF") inside a 44px `GestureDetector` + `Semantics`
     tap target, state shown by filled vs. hairline box border.
2. **Custom scanner top bar vs `VeriqooAppBar`**: `VeriqooAppBar` exposes a single
   trailing action and auto-hides back on a non-poppable tab root, but the scanner
   needs back + flash + gallery over a non-poppable `/scan` root. The top bar is a
   thin custom `Row` of DS primitives (`VeriqooIconButton` back/gallery, text flash
   toggle, centered `VeriqooType.h3` "VERIQOO SCAN") on a `tokens.bg` strip with a
   bottom hairline. `VeriqooAppBar` is retained on the carried-forward
   result/processing routes.
3. **Monochrome / reduced motion**: no lucide/google_fonts imports in `user_app`;
   icons only via `VeriqooIcons`. `textTertiary` restricted to meta/decorative
   (sequence numbers, add label, degrade note, hints). `ScanPhaseBanner` and
   `DetectionBoxesOverlay` consult/avoid motion: the banner collapses its
   `AnimatedSwitcher`/progress tick to an instant state under
   `VeriqooMotion.reduceMotion`, and the detection boxes are static.

## Files created / changed (all under `apps/user_app`)

New (`lib/features/scan/`):
- `model/evidence_image.dart`
- `model/scan_phase.dart`
- `model/detected_field.dart`
- `camera/scan_camera_controller.dart`
- `camera/camera_package_controller.dart`
- `camera/scan_gallery_picker.dart`
- `ocr/live_ocr_analyzer.dart`
- `scan_analysis_runner.dart`
- `widgets/detection_boxes.dart`
- `widgets/scan_phase_banner.dart`
- `widgets/evidence_tray.dart`

Modified (`lib/`):
- `features/scan/scan_providers.dart` (Phase 6 evidence seam)
- `features/scan/scan_screen.dart` (full-screen instrument rewrite)
- `features/scan/scan_capture_screen.dart` (renders `const ScanScreen()`)

Verified-only (no change needed):
- `lib/app/router.dart` — references `ScanScreen`, `ScanCaptureScreen`,
  `AnalysisResultScreen`, `ScanProcessingScreen` unchanged; `/scan`, `/scan/capture`,
  `/scan/processing`, `/scan/result` routes intact.

New tests (`test/scan/`):
- `scan_harness.dart` — fakes (`FakeScanCameraController`, `FakeScanAnalysisRunner`,
  `FakeScanGalleryPicker`) + `pumpScanner` helper; no real camera / Supabase / network.
- `scanner_screen_test.dart` — chrome renders, phase caption, gallery fallback,
  capture→runner→result navigation, web/degraded path.
- `scan_phase_test.dart` — pure `nextScanPhase` transition table + captions.
- `evidence_tray_test.dart` — numbered tiles, highlight, add/retake/delete callbacks.
- `live_ocr_analyzer_test.dart` — `mapBlocksToFields` mapping + normalization,
  per-platform `buildInputImage` construction, `ThrottledOcrRunner` throttle/drop.

Task artifact (outside code tree): this file.

## Unmodified (confirmed)

- All of `packages/shared_core` (design system + `lib/services/*`).
- `apps/admin_web/**`.
- `AnalysisResultScreen` / `AnalysisResultArgs`.
- `SupabaseService.saveInspectionReport` signature.
