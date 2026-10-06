# Phase 5 Implementation Plan — user_app Scanner as a Full-Screen Camera Inspection Instrument

Target package: `apps/user_app` (pub name `flutter_application_1`, internal imports
`package:flutter_application_1/...`). **Write scope is `apps/user_app` only.**
`packages/shared_core` and `apps/admin_web` are READ-ONLY — do not edit them.

Design system is consumed through the single barrel
`import 'package:shared_core/design_system/design_system.dart';`. Tokens via
`Theme.of(context).extension<VeriqooTokens>()!`. Theme getters `VeriqooTheme.dark/.light`.

## Environment / verification bar (ABSOLUTE)

- Shell `flutter *` is DENIED. Use `dart` only: `dart pub add`, `dart pub get`, `dart analyze`.
- Acceptance bar for every item: `dart pub get` succeeds AND `dart analyze` reports **0 errors**
  (run with CWD `apps/user_app`).
- Widget tests are WRITTEN AND KEPT but NOT run here. `flutter test` and `flutter build web`
  are recorded as DEFERRED with exact commands in `phase5-verification.md` (final item).
- Live-stream OCR cannot be runtime-exercised under the `flutter` deny — implement correctly
  and flag it runtime-unverified in `phase5-verification.md`.
- No commits.

## Verified design-system facts (read before relying on them)

Confirmed to exist in `packages/shared_core/lib/design_system`:

- `VeriqooScannerOverlay({child, hint, enabled, fields})` — full-bleed `VerificationScan` motif
  (four corner markers + thin sweeping line + optional OCR sample boxes) over an optional preview
  `child`; honors reduced motion internally. Passing `fields: const <ScanField>[]` yields corners
  + scan line only (no sample boxes).
- `VerificationScan` + `ScanField(Rect rect /*normalized 0..1*/, {String? label})` — reused for
  normalized-rect modelling.
- `VeriqooMotion.reduceMotion(BuildContext)` — the reduce-motion helper (reads
  `MediaQuery.maybeDisableAnimationsOf`).
- `VeriqooAppBar({title, action, onBack, showBack, height})`, `VeriqooButton`,
  `VeriqooButton Variant`, `VeriqooIconButton({icon, semanticLabel, onPressed, variant, iconSize, size})`,
  `VeriqooStatus(kind)`, `VeriqooEmptyState`, `VeriqooErrorState`, `VeriqooLoading({message})`.
- `VeriqooTokens`: `bg, bgTrue, surface, surfaceRaised, borderHairline, borderStrong,
  textPrimary, textSecondary, textTertiary, inverseBg, inverseText`.
- `VeriqooType` text styles; `VeriqooSpacing`, `VeriqooRadius`.
- `VeriqooIcons` glyphs available: `home, scan, history, profile, back, close, chevronRight,
  settings, search, check, alert, verified, violation, camera, upload`.

### Discrepancies / decisions (shared_core cannot be edited)

1. **Missing glyphs.** `VeriqooIcons` has no flash, gallery, add, delete, retake, or rotate glyph.
   Chosen monochrome mappings, each with an explicit `semanticLabel`:
   - Gallery action → `VeriqooIcons.upload` (semanticLabel `"Open gallery"`).
   - Add evidence (`+ Add` tile) → `VeriqooIcons.camera` (adding a shot == capturing another).
   - Delete evidence → `VeriqooIcons.close` (the `x` glyph).
   - Retake evidence → `VeriqooIcons.history` (same glyph the DS uses for "retry").
   - Flash toggle → **no bolt glyph**; render a small text toggle (meta-style `FLASH ON` / `FLASH OFF`
     inside a `VeriqooIconButton`-sized tap target built from `GestureDetector` + `Semantics`),
     not a mis-semantic icon. State reflected by filled vs. hairline box border.
2. **Top bar.** `VeriqooAppBar` exposes a single trailing `action` and hides its back affordance when
   `Navigator.canPop(context)` is false — but `/scan` is a bottom-nav tab root (not poppable) and we
   still want back + flash + gallery (two trailing actions). Decision: the scanner top bar is a thin
   custom `Row` composed of DS primitives (`VeriqooIconButton` for back/gallery, the text flash toggle,
   centered `VeriqooType.h3` title `"VERIQOO SCAN"`) sitting on a `tokens.bg` strip with a bottom
   `borderHairline`. `VeriqooAppBar` is retained on the carried-forward result/processing routes.
   This deviation is documented in `phase5-verification.md`.
3. **Monochrome / reduced motion.** No lucide/google_fonts imports in `apps/user_app`; icons only via
   `VeriqooIcons`. `textTertiary` restricted to meta/decorative (sequence numbers, hints). All custom
   motion consults `VeriqooMotion.reduceMotion` and resolves to a static state when true.

## Verified camera / ML Kit APIs (pinned versions)

- `camera 0.12.1`: `availableCameras()`, `CameraController(CameraDescription, ResolutionPreset,
  {bool enableAudio = true, ImageFormatGroup? imageFormatGroup})`, `.initialize()`,
  `.startImageStream((CameraImage) {})`, `.stopImageStream()`, `.takePicture() -> XFile`,
  `.setFlashMode(FlashMode)`, `CameraPreview(controller)`. `ImageFormatGroup` has
  `nv21, yuv420, bgra8888, jpeg, unknown`. `CameraDescription.sensorOrientation` + `.lensDirection`.
- `google_mlkit_commons 0.12.0` (via `google_mlkit_text_recognition 0.16.0`):
  `InputImage.fromFilePath(path)` and `InputImage.fromBytes({required Uint8List bytes,
  required InputImageMetadata metadata})`. `InputImageMetadata({required Size size,
  required InputImageRotation rotation, required InputImageFormat format, required int bytesPerRow})`.
  `InputImageFormat` includes `nv21` and `bgra8888`; `InputImageRotationValue.fromRawValue(int)`.
  Decision: request `ImageFormatGroup.nv21` on Android so the stream delivers a single NV21 plane that
  maps directly (no manual YUV→NV21 repack); `ImageFormatGroup.bgra8888` on iOS.

---

# Implementation Plan

- [ ] 1. Add the evidence + scan-phase domain models.
      Create `EvidenceRole { front, back, side, additional }` with a `label` extension
      (`Front` / `Back` / `Side` / `+ Add`), and `EvidenceImage` (immutable: `XFile file`,
      `EvidenceRole role`, `int sequence`, `String label`, plus `twoDigit` getter for `01/02/03`).
      Create `ScanPhase { positionProduct, productDetected, readingLabel, extractingDeclarations,
      verifyingCompliance, analysisComplete }` with a `label`/`caption` extension (uppercase copy:
      "POSITION PRODUCT", "PRODUCT DETECTED", "READING LABEL", "EXTRACTING DECLARATIONS",
      "VERIFYING COMPLIANCE", "ANALYSIS COMPLETE") and a pure transition function
      `ScanPhase nextScanPhase(ScanPhase current, {required int detectedFieldCount,
      required bool hasText, required bool capturing, required bool analyzing, required bool complete})`.
      Files: `lib/features/scan/model/evidence_image.dart`, `lib/features/scan/model/scan_phase.dart`
      Verify: `dart analyze` (CWD `apps/user_app`) → `No issues found!` (0 errors).

- [ ] 2. Add the detection-result model.
      Create `DetectedField` (immutable: `Rect rectNormalized` in 0..1, `String label` matching the
      five target labels `PRODUCT NAME` / `MRP` / `BATCH` / `MANUFACTURER` / `MANDATORY DECLARATION`,
      and optional `String text`) and `LiveOcrResult` (immutable: `String rawText`,
      `List<DetectedField> fields`). Keep it camera/ML-Kit-type-free so it is pure and testable.
      Files: `lib/features/scan/model/detected_field.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 3. Expand `scanStateProvider` into the Phase 6 evidence seam.
      Rewrite `ScanState` to hold: `List<EvidenceImage> evidence`, `int currentIndex`,
      `String liveOcrText`, `List<DetectedField> detectedFields`, `ScanPhase phase`,
      `bool isAnalyzing`; add getters `primaryImage` (`evidence.first.file` or null) and
      `nextRole`. Rewrite `ScanController` (keep `scanStateProvider` name + type) with:
      `addEvidence(XFile, {EvidenceRole? role})` (auto-sequences + auto-roles front/back/side/additional),
      `retakeAt(int, XFile)`, `deleteAt(int)` (re-sequences), `setCurrent(int)`,
      `setLiveOcr(String text, List<DetectedField> fields)`, `advancePhase(...)` (delegates to
      `nextScanPhase`), `setAnalyzing(bool)`, and `reset()`. Preserve the existing public name
      `scanStateProvider` so the router/tests stay stable. Document in the file header that this is the
      Phase 6 evidence-viewer hand-off.
      Files: `lib/features/scan/scan_providers.dart` (modify)
      Verify: `dart analyze` → 0 errors.

- [ ] 4. Define the injectable camera abstraction + platform-agnostic frame.
      Create `abstract class ScanCameraController` with: `Future<void> initialize()`,
      `bool get isInitialized`, `bool get supportsLiveOcr`, `Widget buildPreview()`,
      `Future<XFile> takePicture()`, `Future<void> startImageStream(void Function(ScanCameraFrame))`,
      `Future<void> stopImageStream()`, `Future<void> setFlash(bool on)`, `bool get flashOn`,
      `Future<void> dispose()`. Create `ScanCameraFrame` (immutable, camera-package-free:
      `Uint8List bytes`, `int width`, `int height`, `InputImageFormat format`,
      `InputImageRotation rotation`, `int bytesPerRow`) — this is the ONLY ML-Kit type leaked, so the
      analyzer and tests need no `camera` import. Provide
      `final scanCameraControllerProvider = Provider<ScanCameraController Function()>(...)` returning a
      factory (so a fresh controller per screen mount) that tests override with a fake.
      Files: `lib/features/scan/camera/scan_camera_controller.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 5. Implement the real camera controller over the `camera` package.
      Create `CameraPackageController implements ScanCameraController`: on `initialize()`, if `kIsWeb`
      set `supportsLiveOcr = false`; otherwise `availableCameras()` → pick rear
      (`CameraLensDirection.back`, fallback first) → `CameraController(desc, ResolutionPreset.high,
      enableAudio: false, imageFormatGroup: Platform.isAndroid ? ImageFormatGroup.nv21 :
      ImageFormatGroup.bgra8888)` → `.initialize()`. `buildPreview()` returns `CameraPreview` when
      initialized else a `ColoredBox(tokens.bgTrue)` placeholder. `startImageStream` wraps each
      `CameraImage` into a `ScanCameraFrame`: `bytes = image.planes.first.bytes`,
      `bytesPerRow = image.planes.first.bytesPerRow`, `size = (image.width,image.height)`,
      `format = Platform.isAndroid ? InputImageFormat.nv21 : InputImageFormat.bgra8888`,
      `rotation = InputImageRotationValue.fromRawValue(desc.sensorOrientation) ?? rotation0deg`.
      `startImageStream` is a no-op when `!supportsLiveOcr`. `setFlash` → `setFlashMode(on ? torch :
      off)`. Guard all plugin calls in try/catch so a camera failure degrades (never crashes).
      Files: `lib/features/scan/camera/camera_package_controller.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 6. Implement the throttled live-OCR analyzer with per-platform `InputImage` construction.
      Create `LiveOcrAnalyzer`: ctor takes an injectable `TextRecognizer` (default
      `TextRecognizer()`); expose a top-level/static pure `InputImage buildInputImage(ScanCameraFrame)`
      using `InputImage.fromBytes` with `InputImageMetadata(size, rotation, format, bytesPerRow)` from
      the frame; `Future<LiveOcrResult?> analyze(ScanCameraFrame)` runs recognition and maps blocks →
      `DetectedField`s via `mapBlocksToFields(List<RecognizedBlockLite>)` (pure keyword heuristic:
      MRP/₹/"M.R.P" → MRP, "batch"/"lot"/"B.No" → BATCH, "mfg"/"manufactured by"/"marketed by" →
      MANUFACTURER, "net"/"qty"/"g"/"ml" + declaration keywords → MANDATORY DECLARATION, first large
      top block → PRODUCT NAME), each rect normalized by frame width/height. Add a `ThrottledOcrRunner`
      that drops frames while a recognition is in flight AND enforces a min interval
      (`const Duration(milliseconds: 350)`, within the 300–500ms band) via a stopwatch; expose it so the
      screen feeds frames and receives at most one in-flight result. Factor the block→field mapping and
      normalization as pure functions so they unit-test without ML Kit. Provide
      `scanLiveOcrAnalyzerProvider` (overridable in tests).
      Files: `lib/features/scan/ocr/live_ocr_analyzer.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 7. Relocate the analysis pipeline into an injectable runner (behavior-preserving).
      Create `abstract class ScanAnalysisRunner { Future<AnalysisResultArgs> run(
      {required List<EvidenceImage> evidence, required String geminiApiKey}); }` and
      `GeminiScanAnalysisRunner implements ScanAnalysisRunner` that reproduces today's
      `ScanScreen.analyzeProduct` EXACTLY: per-image file OCR via `TextRecognizer` +
      `InputImage.fromFilePath`, combine into the same `===== IMAGE n =====` format, retrieve legal
      context via `LegalRulesRetrievalService` (swallow failures, fall back), analyze via
      `GeminiAIAnalysisService.analyzeProductLabel(combined, legalContext:)`, dispose both services in a
      `finally`, and return `AnalysisResultArgs(analysis:, ocrText: combined, primaryImage:
      evidence.first.file)`. Keep the dotenv-first/`String.fromEnvironment` key resolution. Add
      `scanAnalysisRunnerProvider` (overridable in tests). Do NOT touch `scan_screen.dart` yet so the app
      stays buildable. `AnalysisResultArgs` and the result screen are unchanged; `SupabaseService`
      signature stays as-is (primary image passed; extra evidence lives in `scanState` for Phase 6).
      Files: `lib/features/scan/scan_analysis_runner.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 8. Add an injectable gallery picker (image_picker fallback).
      Create `abstract class ScanGalleryPicker { Future<XFile?> pick(); }` and
      `ImagePickerGallery implements ScanGalleryPicker` wrapping
      `ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 85)`; provide
      `scanGalleryPickerProvider` so the gallery-fallback path is driven by a fake in tests (never opens
      a real picker).
      Files: `lib/features/scan/camera/scan_gallery_picker.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 9. Build the live detection-box overlay painter.
      Create `DetectionBoxesPainter extends CustomPainter` that draws thin (1px) hairline rectangles
      from `List<DetectedField>` (normalized rects scaled to paint size) in `tokens.textPrimary`, with a
      tiny 9px letter-spaced `VeriqooType.meta` label (field name) above each box — matching the DS
      `VerificationScan` box styling, NOT a thick rectangle. Wrap it in a small
      `DetectionBoxesOverlay` widget that reads the fields and is reduced-motion safe (static boxes).
      Files: `lib/features/scan/widgets/detection_boxes.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 10. Build the scan-phase banner (subtle motion, no spinner).
      Create `ScanPhaseBanner` — a compact bottom-aligned pill showing the current `ScanPhase.caption`
      in `VeriqooType.meta` on `tokens.surfaceRaised` @ ~0.85 with a `borderHairline`, plus a 1px
      progress tick/underline that advances with phase ordinal. Transition between captions with a short
      `AnimatedSwitcher` (`VeriqooMotion.base`) that collapses to an instant swap when
      `VeriqooMotion.reduceMotion(context)` is true. No `CircularProgressIndicator`.
      Files: `lib/features/scan/widgets/scan_phase_banner.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 11. Build the evidence tray.
      Create `EvidenceTray` — a horizontal `ListView` (height ~96) of thumbnail tiles from
      `scanState.evidence`: each tile shows the image (`FutureBuilder<Uint8List>` + `Image.memory`,
      `VeriqooLoading` while decoding), a `01/02/03` sequence number (`VeriqooType.meta`,
      `textTertiary`), and its role label; the `currentIndex` tile gets a `borderStrong` highlight,
      others `borderHairline`. Tapping a tile → `setCurrent`. Each tile carries small retake
      (`VeriqooIcons.history`) and delete (`VeriqooIcons.close`) `VeriqooIconButton`s. A trailing
      `+ Add` tile (`VeriqooIcons.camera`, label "+ ADD") triggers capture of the next role. Expose
      `onRetake(index)`, `onDelete(index)`, `onAdd()`, `onSelect(index)` callbacks so the screen owns the
      camera/picker side effects. Give the tray and tiles stable `Key`s for tests.
      Files: `lib/features/scan/widgets/evidence_tray.dart`
      Verify: `dart analyze` → 0 errors.

- [ ] 12. Rewrite `ScanScreen` as the full-screen camera inspection instrument (wires items 3–11).
      Convert to a `ConsumerStatefulWidget` that, on init, builds a `ScanCameraController` from
      `scanCameraControllerProvider` and `initialize()`s it; when `supportsLiveOcr`, starts the image
      stream feeding frames through the item-6 throttle into `LiveOcrAnalyzer`, writing results to
      `scanStateProvider.setLiveOcr(...)` and driving `advancePhase(...)`. Layout, bottom→top:
      full-bleed `VeriqooScannerOverlay(child: controller.buildPreview(), fields: const <ScanField>[],
      hint: scanState.phase.caption)` with a `DetectionBoxesOverlay` and `ScanPhaseBanner` stacked over
      it; a custom top bar `Row` (back → `context.canPop() ? pop : go(home)`; title "VERIQOO SCAN";
      flash text-toggle → `controller.setFlash`; gallery `VeriqooIcons.upload` → `scanGalleryPicker` →
      `addEvidence`); the `EvidenceTray` pinned above a primary capture control
      (`VeriqooIconButton`/`VeriqooButton`, `VeriqooIcons.camera`) that calls `takePicture` →
      `addEvidence`. Capture-finish/Analyze: `setAnalyzing(true)` → `advancePhase` to
      `verifyingCompliance` → `scanAnalysisRunnerProvider.run(evidence: scanState.evidence, ...)` →
      `advancePhase(analysisComplete)` → `router.push(AppRoutes.scanResultPath, extra: args)` (unchanged
      result route + `SupabaseService` behavior), with the existing `AIAnalysisException`/generic
      `SnackBar` handling preserved. On web/unsupported, skip the stream + boxes and keep preview +
      manual capture + gallery working (`VeriqooEmptyState`/hint explains live detection is unavailable).
      Dispose the controller, recognizer, and stream in `dispose()`. Attach stable `Key`s used by tests.
      Files: `lib/features/scan/scan_screen.dart` (rewrite)
      Verify: `dart analyze` → 0 errors.

- [ ] 13. Make `/scan/capture` coherent and confirm routing.
      Point `ScanCaptureScreen` at the same scanner experience (render `const ScanScreen()` so a pushed
      `/scan/capture` shows the identical instrument with a real back affordance) and keep the `/scan`
      tab-root builder on `ScanScreen`. No change to `AppRoutes`; confirm `scan_screen.dart`,
      `scan_capture_screen.dart`, and `router.dart` still reference existing names. The carried-forward
      `/scan/result` + `/scan/processing` routes stay intact and reachable end-to-end.
      Files: `lib/features/scan/scan_capture_screen.dart` (modify), `lib/app/router.dart` (verify;
      modify only if an import/name drifted)
      Verify: `dart analyze` → 0 errors.

- [ ] 14. Write the hermetic test harness (no real camera, no `Supabase.instance`, no network).
      Create `FakeScanCameraController` (configurable `isInitialized`, `supportsLiveOcr`,
      `flashOn`; `buildPreview()` returns a keyed `Placeholder`; `takePicture()` returns a stub `XFile`
      from an in-memory temp path/bytes; `startImageStream` can replay a canned `ScanCameraFrame` list),
      `FakeScanAnalysisRunner` (returns a canned `AnalysisResultArgs` built from a hand-made
      `ComplianceAnalysis`, never hits Gemini/RAG), `FakeScanGalleryPicker` (returns a preset `XFile?`),
      and `FakeLiveOcrAnalyzer` (returns a canned `LiveOcrResult`). Add a `pumpScanner` helper that
      mounts `ScanScreen` under a minimal `GoRouter` (`/scan` + a keyed `/scan/result` placeholder) and
      `MaterialApp.router(theme: VeriqooTheme.dark)` with all four providers overridden; use fixed
      `pump`s (never `pumpAndSettle`, since the scan motif loops).
      Files: `apps/user_app/test/scan/scan_harness.dart`
      Verify: `dart analyze test` → 0 errors (compiles). (`flutter test` deferred — see item 16.)

- [ ] 15. Write the hermetic widget + unit tests (kept, not run here).
      `scanner_screen_test.dart`: renders `VeriqooScannerOverlay`, the "VERIQOO SCAN" title, flash toggle
      and gallery control, and `EvidenceTray`; the `ScanPhaseBanner` renders a phase caption; the gallery
      fallback path (tap gallery → fake picker → tray shows one numbered tile); capture → fake runner →
      navigates to the keyed `/scan/result` placeholder; the web/degraded path
      (`supportsLiveOcr = false` → no `DetectionBoxesOverlay`, preview + capture still function);
      `tester.takeException()` is null throughout and no real camera/Supabase is touched.
      `scan_phase_test.dart`: pure `nextScanPhase` transition table (position→detected→reading→
      extracting→verifying→complete). `evidence_tray_test.dart`: numbered tiles render, current tile
      highlighted, add/retake/delete callbacks fire. `live_ocr_analyzer_test.dart`: `mapBlocksToFields`
      keyword→label mapping + rect normalization, and `buildInputImage(frame).toJson()` asserts
      `image_format`/`rotation`/`bytes_per_row`/`width`/`height` for an Android NV21 frame and an iOS
      BGRA frame (per-platform construction verified without a camera).
      Files: `apps/user_app/test/scan/scanner_screen_test.dart`,
      `apps/user_app/test/scan/scan_phase_test.dart`,
      `apps/user_app/test/scan/evidence_tray_test.dart`,
      `apps/user_app/test/scan/live_ocr_analyzer_test.dart`
      Verify: `dart analyze` (CWD `apps/user_app`, which includes `test/`) → 0 errors.

- [ ] 16. Record the verification + deferred-command report.
      Write `phase5-verification.md` capturing: `dart pub get` success and `dart analyze` "No issues
      found!"; the DEFERRED commands verbatim — `flutter test` (CWD `apps/user_app`) and
      `flutter build web` (CWD `apps/user_app`) — stating they were NOT run under the `flutter` deny;
      the runtime-unverified note that live-stream OCR (`startImageStream` → per-platform `InputImage`
      → field mapping/throttle) is implemented but could not be exercised without a device/`flutter run`;
      and the DS discrepancy/workaround notes (missing glyphs, custom scanner top bar vs `VeriqooAppBar`).
      Files: `.agents/tasks/veriqoo-user-scanner-phase5/phase5-verification.md` (task artifact, outside
      the write scope's code tree — allowed)
      Verify: `dart pub get` (CWD `apps/user_app`) → "Got dependencies!"; `dart analyze` (CWD
      `apps/user_app`) → "No issues found!" (0 errors). Confirm `packages/shared_core` and
      `apps/admin_web` are unmodified.

## File set summary

New (`apps/user_app/lib/features/scan/`):
- `model/evidence_image.dart`, `model/scan_phase.dart`, `model/detected_field.dart`
- `camera/scan_camera_controller.dart`, `camera/camera_package_controller.dart`,
  `camera/scan_gallery_picker.dart`
- `ocr/live_ocr_analyzer.dart`
- `scan_analysis_runner.dart`
- `widgets/detection_boxes.dart`, `widgets/scan_phase_banner.dart`, `widgets/evidence_tray.dart`

Modified (`apps/user_app/`):
- `lib/features/scan/scan_providers.dart` (Phase 6 evidence seam)
- `lib/features/scan/scan_screen.dart` (full-screen instrument rewrite)
- `lib/features/scan/scan_capture_screen.dart` (coherent `/scan/capture`)
- `lib/app/router.dart` (verify only; edit only on import/name drift)

New tests (`apps/user_app/test/scan/`):
- `scan_harness.dart`, `scanner_screen_test.dart`, `scan_phase_test.dart`,
  `evidence_tray_test.dart`, `live_ocr_analyzer_test.dart`

Task artifact (outside code tree):
- `.agents/tasks/veriqoo-user-scanner-phase5/phase5-verification.md`

Unchanged (do not edit): all of `packages/shared_core` (design system + `lib/services/*`),
`apps/admin_web/**`, `AnalysisResultScreen`/`AnalysisResultArgs`, and `SupabaseService.saveInspectionReport`.
