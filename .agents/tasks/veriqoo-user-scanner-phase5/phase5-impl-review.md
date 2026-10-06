# user_app scanner rebuilt as a full-screen camera inspection instrument

Phase 5 replaces the old pick-and-analyze scan flow with an immersive camera instrument at `/scan`: a full-bleed preview under the signature `VeriqooScannerOverlay`, a thin custom top bar (back / "VERIQOO SCAN" / flash / gallery), throttled live OCR that paints thin labelled detection boxes, a six-state phase banner with subtle motion, and a numbered multi-image evidence tray. The camera is hidden behind an injectable `ScanCameraController` abstraction so the whole screen can be driven by fakes in hermetic widget tests, and the carried-forward Gemini/RAG analysis pipeline was relocated verbatim into an injectable `ScanAnalysisRunner` that still hands `evidence.first.file` into the unchanged result screen and `SupabaseService`. ML Kit's absence on web is handled by degrading to preview + manual capture + gallery. The design-system contract (barrel import, token extension, `VeriqooIcons` facade, monochrome, reduced-motion) is respected throughout, with documented glyph substitutions where the icon set has gaps.

Watch for: the live-OCR stream path (`supportsLiveOcr = true`) is exercised only by unit tests on the pure mapping/throttle functions — no widget test mounts the screen with a live camera, so the frame → `setLiveOcr` → detection-overlay wiring is unverified end to end (likely). Flash UI state can desync from the hardware if `setFlashMode` throws (confirmed, minor). Scope is clean: no commit was made, `saveInspectionReport` is untouched, and all writes land under `apps/user_app` (confirmed).

**Verdict**: APPROVED

## High-level view

The design hinges on one abstraction: `ScanCameraController`. Every platform- and plugin-specific concern (web detection, NV21/BGRA selection, sensor rotation, torch, stream lifecycle) lives in `CameraPackageController`, while the screen, OCR analyzer, and tests speak only to the interface and a plugin-free `ScanCameraFrame`. That is what makes the screen testable without a device and what keeps the `camera` import out of the analyzer.

The OCR pipeline is split into pure, testable pieces (`buildInputImage`, `mapBlocksToFields`) wrapped by a `ThrottledOcrRunner` that drops in-flight frames and enforces a 350ms floor. The classification is a keyword heuristic — adequate for a live "detected" affordance, not a source of truth, and the real extraction still happens in the carried-forward file-OCR + Gemini path at analyze time.

The phase machine (`nextScanPhase`) is a pure monotonic function that latches mid-pipeline states so a transient detection loss cannot flicker the banner backward. It is wired through `ScanController.advancePhase`, which is the same `scanStateProvider` seam Phase 6 will read for the full evidence list.

Degradation is fail-safe: `initialize()` is contracted never to throw, every plugin call is guarded, and when live OCR is unsupported the screen hides the detection overlay, shows a meta-style "unavailable" note, and keeps capture + gallery working.

Scope discipline holds. The analysis runner reproduces the old `analyzeProduct` logic exactly and returns the unchanged `AnalysisResultArgs`; `SupabaseService.saveInspectionReport` keeps its signature; the result screen is carried forward, not redesigned; and the Phase 5 files are all uncommitted.

<details>
<summary>Issues (6)</summary>

1. **Live-OCR path not widget-tested** (likely) — every `scanner_screen_test` case uses `liveOcr: false`, so the stream → `setLiveOcr` → `DetectionBoxesOverlay` wiring and phase advancement from live detection are never mounted, despite `FakeScanCameraController` already supporting canned `frames`. Add one `liveOcr: true` widget test that replays `sampleOcrResult`-style frames and asserts the overlay + a non-initial phase caption.
2. **Flash UI can desync from hardware** (confirmed) — `_toggleFlash` sets `_flashOn` via `setState` unconditionally, but `CameraPackageController.setFlash` swallows a `setFlashMode` failure, so the toggle can read "FLASH ON" while the torch is off. Have `setFlash` surface success/failure (or re-read `flashOn`) and reflect the actual state.
3. **Evidence thumbnail re-reads bytes every rebuild** (confirmed) — `_EvidenceTile` calls `image.file.readAsBytes()` directly inside `build`, creating a fresh future on each rebuild and re-decoding/flickering the thumbnail. Cache the bytes (e.g. memoize per `XFile` or decode once in a `StatefulWidget`).
4. **Concurrent-capture guard missing** (possible) — the capture button and `+ Add` tile are gated by `_busy` (set only during analyze), not by an in-flight capture, so a fast double-tap can call `takePicture()` twice concurrently; the plugin may throw and surface a snackbar. Add a capture-in-progress flag.
5. **`startImageStream` lacks a post-await mounted recheck** (possible) — in `_initCamera`, `setState` runs after `startImageStream` without re-checking `mounted`, so disposing mid-start could call `setState` on a defunct state. Re-check `mounted` before the final `setState`.
6. **shared_core/admin_web untouched not provable from git** (possible) — the repo reorg left everything untracked, so there is no baseline diff to confirm `packages/shared_core` and `apps/admin_web` were not edited. Verdict relies on the verification attestation plus the fact that all scanner writes are under `apps/user_app`; a reviewer wanting certainty should diff those trees against a known-good copy.

</details>

<details>
<summary>Details</summary>

### Transport abstraction via `ScanCameraController`

The screen never touches the `camera` package. `ScanCameraController` exposes `initialize / isInitialized / supportsLiveOcr / buildPreview / takePicture / startImageStream / stopImageStream / setFlash / flashOn / dispose`, and the only ML-Kit types that leak are the `InputImageFormat` and `InputImageRotation` carried on `ScanCameraFrame`. Everything camera-specific — selecting the rear lens, choosing `ImageFormatGroup.nv21` on Android vs `bgra8888` on iOS, mapping `sensorOrientation` through `InputImageRotationValue.fromRawValue`, wrapping each `CameraImage`'s first plane into a `ScanCameraFrame` — is isolated in `CameraPackageController`. The provider is a factory (`Provider<ScanCameraController Function()>`) so each mount gets a fresh controller and tests override it with `() => FakeScanCameraController(...)`. This is the cleanest part of the change and is what makes the hermetic widget tests possible.

One correctness detail worth calling out: `startImageStream` computes `format` as `kIsWeb || !Platform.isAndroid ? bgra8888 : nv21`, matching the `imageFormatGroup` requested at `initialize`. Because `takePicture` stops the stream before capturing (some platforms forbid a still capture while streaming) and the screen restarts the stream afterward, the stream lifecycle is handled rather than left dangling.

### Live OCR: pure core, throttled shell

`buildInputImage` and `mapBlocksToFields` are pure functions over `ScanCameraFrame` / `RecognizedBlockLite`, which is what lets the per-platform `InputImage` construction and the keyword→label mapping be unit-tested without a camera or a real `TextRecognizer`. `ThrottledOcrRunner.submit` drops a frame while one recognition is in flight and otherwise enforces a 350ms floor via a `Stopwatch` reset in `finally` — squarely in the 300–500ms band the brief asked for, and the drop-while-in-flight behavior means a slow recognizer can't queue a backlog.

The classification is a keyword heuristic (MRP/₹/price, batch/lot, mfg/marketed-by, net/qty/unit tokens, then "first top-most unclaimed block" as product name), each label emitted at most once. This is fine for a live "we see a label" affordance, which is all it drives — the authoritative extraction is the separate file-OCR + Gemini pass at analyze time. The heuristic will mislabel in the field (e.g. any block containing "l" or "g" as a standalone unit token can read as MANDATORY DECLARATION via the regex, and `price` is broad), but since nothing downstream consumes these labels as truth, the blast radius is cosmetic.

The gap is verification: all `scanner_screen_test` cases run with `liveOcr: false`, so the overlay-rendering and `_onFrame → setLiveOcr → advancePhase` wiring is only ever reasoned about, never mounted. `FakeScanCameraController` already replays a canned `frames` list on `startImageStream`, so a `liveOcr: true` test asserting `DetectionBoxesOverlay` appears and the phase caption leaves "POSITION PRODUCT" would close the loop cheaply.

### Phase machine latching

`nextScanPhase` is a pure function that computes a target from `(complete, analyzing, capturing, detectedFieldCount, hasText)` in priority order, then refuses to regress once the current phase is `extractingDeclarations`, `verifyingCompliance`, or `analysisComplete` (unless `complete`/`analyzing` explicitly drive it). That latching is the right call for a live stream: without it, a dropped frame mid-capture would flap the banner between "READING LABEL" and "EXTRACTING DECLARATIONS". The post-analyze teardown path (`setAnalyzing(false)` → `advancePhase(analyzing: false)`) was traced and correctly stays on `analysisComplete` because of the latch, so the terminal state doesn't collapse back to an intermediate caption after navigation.

### Analysis hand-off preserves behavior

`GeminiScanAnalysisRunner.run` reproduces the old `ScanScreen.analyzeProduct` faithfully: per-image `InputImage.fromFilePath` OCR, the same `===== IMAGE n =====` join, `LegalRulesRetrievalService` with failures swallowed to a fallback, `GeminiAIAnalysisService.analyzeProductLabel(combined, legalContext:)`, all three services disposed in `finally`, and an `AnalysisResultArgs(analysis, ocrText: combined, primaryImage: evidence.first.file)` return. The dotenv-first then `String.fromEnvironment` key resolution is kept and guarded against an uninitialized dotenv so tests don't throw. Multi-image evidence is combined into the OCR text, but only the first file is passed as `primaryImage` — exactly the described contract that keeps `SupabaseService` untouched while the extra evidence waits in `scanState` for Phase 6.

### Degradation and failure modes

`initialize()` is contracted never to throw and holds to it: empty `availableCameras()` and any initialization exception both land in a degraded state (`isInitialized`/`supportsLiveOcr` false, preview falls back to a `tokens.bgTrue` placeholder, stream becomes a no-op). `kIsWeb` short-circuits live OCR because ML Kit has no web implementation. The screen honors this by hiding `DetectionBoxesOverlay`, showing the "LIVE DETECTION UNAVAILABLE" meta note, and keeping manual capture + gallery live — the fail-open path the brief required. Capture, gallery, and retake failures each degrade to a floating `SnackBar` (or a silent no-op for retake) rather than a crash.

Two rough edges in the lifecycle. `_toggleFlash` optimistically flips `_flashOn` through `setState`, but `CameraPackageController.setFlash` catches and logs a `setFlashMode` failure without reporting it, so the label can claim "FLASH ON" while the torch never engaged — a user-visible lie, low severity. And the capture affordances are gated only by `_busy`, which is set during analyze, not during an in-flight capture; a rapid double-tap can issue two concurrent `takePicture()` calls, which the plugin may reject into the generic capture snackbar. Neither blocks shipping.

### Evidence tray

The tray is a horizontal `ListView.separated` of 76px tiles plus a trailing `+ ADD` tile, with `01/02/03` badges (`twoDigit`), role labels, a `borderStrong` highlight on the current tile vs `borderHairline` otherwise, and per-tile retake/delete `VeriqooIconButton`s — all keyed for tests. Deletion re-sequences through `_resequence` and clamps `currentIndex`, so the numbering stays dense. The one inefficiency: each tile's thumbnail future is `image.file.readAsBytes()` created inline in `build`, so every rebuild re-reads and re-decodes the bytes and briefly shows the `VeriqooLoading` placeholder again. For a short strip of captures it's tolerable, but caching the decoded bytes would remove the flicker.

### Design-system discipline

The barrel import is used everywhere, tokens come through `Theme.of(context).extension<VeriqooTokens>()!`, icons go through `VeriqooIcons`, and a grep confirms no `lucide` or `google_fonts` imports anywhere in `apps/user_app/lib`. The documented glyph substitutions (gallery→`upload`, add→`camera`, delete→`close`, retake→`history`, flash→text toggle because there is no bolt glyph) are reasonable given the icon set, and each carries an explicit `semanticLabel`. The custom top-bar `Row` is a justified deviation from `VeriqooAppBar` (which exposes a single trailing action and auto-hides back on a non-poppable tab root, while the scanner needs back + flash + gallery) and is built from DS primitives on a `tokens.bg` strip with a hairline. Reduced motion is honored: `ScanPhaseBanner` collapses its `AnimatedSwitcher`/progress to instant under `VeriqooMotion.reduceMotion`, and the detection boxes are static by construction.

### Scope checks

All four blocking gates pass. No commit exists for this phase — the Phase 5 files show as untracked against `HEAD` (last commit is the earlier repo reorganization), so nothing was committed. `saveInspectionReport` in `packages/shared_core` keeps its `{analysis, ocrText, primaryImage, imageUrl, inspectedAt}` signature and the result screen still calls it with the original named arguments. `AnalysisResultScreen`/`AnalysisResultArgs` are carried forward, not redesigned — the runner targets the existing args and route. The caveat is that the repo reorg left the entire tree untracked, so there is no git baseline to *prove* `packages/shared_core` and `apps/admin_web` are byte-for-byte unmodified; the verdict leans on the verification attestation plus the structural fact that every scanner file written is under `apps/user_app`.

### Test coverage

Covered: chrome rendering, initial phase caption, the web/degraded path (no overlay, degrade note, manual capture works), gallery fallback adding a numbered tile, and capture→analyze→result-route navigation — all with `tester.takeException()` asserted null and no real camera or `Supabase.instance` touched (the fakes make that structural). Per the verification doc, the unit suite also covers `nextScanPhase`, the tray callbacks, `mapBlocksToFields` + rect normalization, per-platform `buildInputImage.toJson()`, and the throttle/drop behavior.

Not tested: the live-OCR widget path (stream → overlay → phase), as noted above; the flash-failure desync; and concurrent capture. These are the three behavioral edges most likely to surprise in the field, and none is runtime-verifiable under the `flutter` deny — but the live-OCR widget wiring at least is reachable with the existing fakes.

</details>

<details>
<summary>File map</summary>

New (`apps/user_app/lib/features/scan/`):
- `model/evidence_image.dart` — `EvidenceRole` + `EvidenceImage` (role/sequence/`twoDigit`).
- `model/scan_phase.dart` — `ScanPhase` enum, captions, pure `nextScanPhase` transition.
- `model/detected_field.dart` — `DetectedFieldLabels`, `DetectedField`, `LiveOcrResult`.
- `camera/scan_camera_controller.dart` — injectable controller interface + `ScanCameraFrame` + factory provider.
- `camera/camera_package_controller.dart` — real controller over the `camera` package (degradation, NV21/BGRA, rotation, torch).
- `camera/scan_gallery_picker.dart` — injectable `image_picker` gallery fallback.
- `ocr/live_ocr_analyzer.dart` — `buildInputImage`, `mapBlocksToFields`, `LiveOcrAnalyzer`, `ThrottledOcrRunner`.
- `scan_analysis_runner.dart` — injectable runner reproducing the carried-forward Gemini/RAG pipeline.
- `widgets/detection_boxes.dart` — thin hairline detection-box painter + static overlay.
- `widgets/scan_phase_banner.dart` — phase caption pill with reduced-motion-aware progress tick.
- `widgets/evidence_tray.dart` — numbered thumbnail strip with retake/delete/add.

Modified (`apps/user_app/lib/features/scan/`):
- `scan_providers.dart` — `ScanState`/`ScanController` expanded into the Phase 6 evidence seam (name/type preserved).
- `scan_screen.dart` — rewritten as the full-screen camera instrument wiring all of the above.
- `scan_capture_screen.dart` — renders `const ScanScreen()` so `/scan/capture` is coherent.

New tests (`apps/user_app/test/scan/`):
- `scan_harness.dart` — fakes + `pumpScanner` (no real camera / Supabase / network).
- `scanner_screen_test.dart`, `scan_phase_test.dart`, `evidence_tray_test.dart`, `live_ocr_analyzer_test.dart`.

Verified unchanged: `packages/shared_core` (`saveInspectionReport`), `apps/admin_web/**`, `AnalysisResultScreen`/`AnalysisResultArgs`, `lib/app/router.dart` wiring.

Full change set reviewed by reading the files directly (the repo reorg left the trees untracked, so there is no isolating `git diff`).

</details>
