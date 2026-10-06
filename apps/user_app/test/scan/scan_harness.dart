import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/camera/scan_camera_controller.dart';
import 'package:flutter_application_1/features/scan/camera/scan_gallery_picker.dart';
import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/scan_analysis_runner.dart';
import 'package:flutter_application_1/features/scan/scan_screen.dart';

/// Key for the stand-in `/scan/result` route so navigation is observable.
const Key kScanResultRouteKey = Key('route-scan-result');

/// Key for the stand-in `/scan/processing` route so navigation is observable.
const Key kScanProcessingRouteKey = Key('route-scan-processing');

/// A valid 1×1 transparent PNG so `Image.memory` decodes without throwing.
final Uint8List kPngBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
  '+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC',
);

/// Produces an in-memory [XFile] (never touches the filesystem or a camera).
XFile stubImage([String name = 'evidence.png']) =>
    XFile.fromData(kPngBytes, name: name, mimeType: 'image/png');

/// Controllable [ScanCameraController] that NEVER opens a real camera. Preview
/// is a keyed [Placeholder]; `takePicture` returns an in-memory [XFile]; the
/// image stream replays a canned list of [ScanCameraFrame]s on start.
class FakeScanCameraController implements ScanCameraController {
  FakeScanCameraController({
    this.initialized = true,
    this.liveOcr = false,
    this.frames = const <ScanCameraFrame>[],
    this.failCapture = false,
  });

  bool initialized;
  bool liveOcr;
  bool failCapture;
  final List<ScanCameraFrame> frames;

  bool _flashOn = false;
  int disposeCount = 0;
  int captureCount = 0;

  @override
  bool get isInitialized => initialized;

  @override
  bool get supportsLiveOcr => liveOcr;

  @override
  bool get flashOn => _flashOn;

  @override
  Future<void> initialize() async {}

  @override
  Widget buildPreview() => const Placeholder(key: Key('fake-camera-preview'));

  @override
  Future<XFile> takePicture() async {
    captureCount++;
    if (failCapture) {
      throw StateError('capture failed');
    }
    return stubImage('capture-$captureCount.png');
  }

  @override
  Future<void> startImageStream(
    void Function(ScanCameraFrame frame) onFrame,
  ) async {
    if (!liveOcr) {
      return;
    }
    for (final frame in frames) {
      onFrame(frame);
    }
  }

  @override
  Future<void> stopImageStream() async {}

  @override
  Future<void> setFlash(bool on) async {
    _flashOn = on;
  }

  @override
  Future<void> dispose() async {
    disposeCount++;
  }
}

/// Returns a canned [AnalysisResultArgs]; never hits Gemini / RAG / Supabase.
class FakeScanAnalysisRunner implements ScanAnalysisRunner {
  FakeScanAnalysisRunner({ComplianceAnalysis? analysis}) : _analysis = analysis;

  final ComplianceAnalysis? _analysis;
  int runCount = 0;
  List<EvidenceImage>? lastEvidence;

  @override
  Future<AnalysisResultArgs> run({
    required List<EvidenceImage> evidence,
    required String geminiApiKey,
  }) async {
    runCount++;
    lastEvidence = evidence;
    return AnalysisResultArgs(
      analysis: _analysis ?? sampleAnalysis(),
      ocrText: '===== IMAGE 1 =====\nSAMPLE',
      primaryImage: evidence.isEmpty ? null : evidence.first.file,
    );
  }
}

/// Returns a preset pick result; never opens a real picker.
class FakeScanGalleryPicker implements ScanGalleryPicker {
  FakeScanGalleryPicker({this.result});

  XFile? result;
  int pickCount = 0;

  @override
  Future<XFile?> pick() async {
    pickCount++;
    return result;
  }
}

/// A hand-made compliant analysis for the fake runner.
ComplianceAnalysis sampleAnalysis() => const ComplianceAnalysis(
      productName: 'Oat Crunch Cereal',
      mrp: '₹120',
      netQuantity: '500 g',
      manufacturer: 'Acme Foods',
      address: '12 Mill Road',
      packingDate: '2026-01',
      customerCare: 'care@acme.test',
      missingInformation: <String>[],
      possibleIssues: <ComplianceIssue>[],
    );

/// A canned live-OCR result for stream-driven assertions.
LiveOcrResult sampleOcrResult() => const LiveOcrResult(
      rawText: 'MRP ₹120\nNET QTY 500 g',
      fields: <DetectedField>[
        DetectedField(
          rectNormalized: Rect.fromLTWH(0.1, 0.3, 0.3, 0.07),
          label: DetectedFieldLabels.mrp,
          text: 'MRP ₹120',
        ),
      ],
    );

/// Mounts [ScanScreen] under a minimal router + the dark VERIQOO theme with all
/// scan providers overridden by fakes. Uses fixed pumps (never
/// `pumpAndSettle`, since the scan motif loops forever).
Future<void> pumpScanner(
  WidgetTester tester, {
  required FakeScanCameraController camera,
  FakeScanAnalysisRunner? runner,
  FakeScanGalleryPicker? gallery,
}) async {
  final router = GoRouter(
    initialLocation: AppRoutes.scanPath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.scanPath,
        builder: (_, __) => const ScanScreen(),
        routes: <RouteBase>[
          GoRoute(
            path: AppRoutes.scanProcessingSegment,
            builder: (_, __) => const Placeholder(key: kScanProcessingRouteKey),
          ),
          GoRoute(
            path: AppRoutes.scanResultSegment,
            builder: (_, __) => const Placeholder(key: kScanResultRouteKey),
          ),
        ],
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        scanCameraControllerProvider.overrideWithValue(() => camera),
        scanAnalysisRunnerProvider
            .overrideWithValue(runner ?? FakeScanAnalysisRunner()),
        scanGalleryPickerProvider
            .overrideWithValue(gallery ?? FakeScanGalleryPicker()),
      ],
      child: MaterialApp.router(
        theme: VeriqooTheme.dark,
        routerConfig: router,
      ),
    ),
  );

  // Flush the async camera init, then advance a fixed slice of motion.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}
