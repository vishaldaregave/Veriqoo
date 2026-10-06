import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/scan_screen.dart';
import 'package:flutter_application_1/features/scan/widgets/evidence_tray.dart';
import 'package:flutter_application_1/features/scan/widgets/scan_phase_banner.dart';

import 'scan_harness.dart';

void main() {
  testWidgets('renders the scanner instrument chrome', (tester) async {
    final camera = FakeScanCameraController(liveOcr: false);
    await pumpScanner(tester, camera: camera);

    expect(find.byType(VeriqooScannerOverlay), findsOneWidget);
    expect(find.text('VERIQOO SCAN'), findsOneWidget);
    expect(find.byKey(kScanFlashToggleKey), findsOneWidget);
    expect(find.byKey(kScanGalleryButtonKey), findsOneWidget);
    expect(find.byKey(kScanBackButtonKey), findsOneWidget);
    expect(find.byType(EvidenceTray), findsOneWidget);
    expect(find.byType(ScanPhaseBanner), findsOneWidget);
    // Uses the fake preview, never a real camera.
    expect(find.byKey(const Key('fake-camera-preview')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('phase banner shows the initial caption', (tester) async {
    final camera = FakeScanCameraController(liveOcr: false);
    await pumpScanner(tester, camera: camera);

    // Caption appears in the overlay hint and the banner.
    expect(find.text('POSITION PRODUCT'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('web/degraded path: no detection overlay, capture still works',
      (tester) async {
    final camera = FakeScanCameraController(liveOcr: false);
    final runner = FakeScanAnalysisRunner();
    await pumpScanner(tester, camera: camera, runner: runner);

    // No live detection overlay when the platform does not support live OCR.
    expect(find.byKey(kScanDetectionOverlayKey), findsNothing);
    // The degrade note is shown.
    expect(
      find.textContaining('LIVE DETECTION UNAVAILABLE'),
      findsOneWidget,
    );

    // Manual capture still functions.
    await tester.tap(find.byKey(kScanCaptureButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));
    expect(camera.captureCount, 1);
    expect(find.text('01'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('gallery fallback: pick adds one numbered tile', (tester) async {
    final camera = FakeScanCameraController(liveOcr: false);
    final gallery = FakeScanGalleryPicker(result: stubImage('from-gallery.png'));
    await pumpScanner(tester, camera: camera, gallery: gallery);

    await tester.tap(find.byKey(kScanGalleryButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(gallery.pickCount, 1);
    expect(find.text('01'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('capture → analyze → navigates to the processing route',
      (tester) async {
    final camera = FakeScanCameraController(liveOcr: false);
    // Phase 6 (D1): the scanner hands off to /scan/processing, which now drives
    // the analysis — the runner is no longer invoked by ScanScreen itself.
    final runner = FakeScanAnalysisRunner();
    await pumpScanner(tester, camera: camera, runner: runner);

    // Capture one image so Analyze is enabled.
    await tester.tap(find.byKey(kScanCaptureButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    await tester.tap(find.byKey(kScanAnalyzeButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));

    // ScanScreen navigates to processing without running the analysis.
    expect(runner.runCount, 0);
    expect(find.byKey(kScanProcessingRouteKey), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
