import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_args.dart';
import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_screen.dart';
import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/result/report_share_service.dart';
import 'package:flutter_application_1/features/scan/scan_analysis_runner.dart';
import 'package:flutter_application_1/features/scan/scan_processing_screen.dart';
import 'package:flutter_application_1/features/scan/scan_providers.dart';

import 'scan_harness.dart';

/// Keyed stand-in routes so navigation out of the report is observable.
const Key kEvidenceRouteKey = Key('route-scan-evidence');
const Key kReportIssueRouteKey = Key('route-report-issue');

// --- ComplianceAnalysis fixtures --------------------------------------------

/// All seven mandatory fields present, nothing missing, no issues → score 100.
ComplianceAnalysis fixtureAllCompliant() => const ComplianceAnalysis(
      productName: 'Oat Crunch Cereal',
      mrp: '₹120',
      netQuantity: '500 g',
      manufacturer: 'Acme Foods',
      address: '12 Mill Road, Pune',
      packingDate: '2026-01',
      customerCare: 'care@acme.test',
      missingInformation: <String>[],
      possibleIssues: <ComplianceIssue>[],
    );

/// Two fields present (product name + net quantity), three missing
/// declarations, no issues. presentCount=2 → base≈28.57, −18 → score 11.
ComplianceAnalysis fixtureMissingOnly() => const ComplianceAnalysis(
      productName: 'Masala Mix',
      mrp: '',
      netQuantity: '200 g',
      manufacturer: '',
      address: '',
      packingDate: '',
      customerCare: '',
      missingInformation: <String>[
        'MRP',
        'Manufacturer address',
        'Customer care details',
      ],
      possibleIssues: <ComplianceIssue>[],
    );

/// All fields present but three mixed-severity issues (high+medium+low → −25)
/// with differing verification statuses → score 75.
ComplianceAnalysis fixtureWithIssues() => const ComplianceAnalysis(
      productName: 'Trail Mix',
      mrp: '₹250',
      netQuantity: '1 kg',
      manufacturer: 'Nguni Foods',
      address: '9 Hill Street',
      packingDate: '2026-02',
      customerCare: '1800-000-000',
      missingInformation: <String>[],
      possibleIssues: <ComplianceIssue>[
        ComplianceIssue(
          title: 'MRP not prominent',
          description: 'The MRP declaration is not legibly displayed.',
          severity: 'high',
          ruleNumbers: <String>['18'],
          ruleTitles: <String>['Display of MRP'],
          legalBasis: 'LMPC Rules, 2011',
          verificationStatus: LegalVerificationStatus.legallyVerified,
        ),
        ComplianceIssue(
          title: 'Font size concern',
          description: 'Declaration font may be below the required height.',
          severity: 'medium',
          verificationStatus: LegalVerificationStatus.possibleConcern,
        ),
        ComplianceIssue(
          title: 'Minor spacing',
          description: 'Spacing between declarations is tight.',
          severity: 'low',
          verificationStatus: LegalVerificationStatus.generalObservation,
        ),
      ],
    );

// --- Fakes ------------------------------------------------------------------

/// Records the last shared payload instead of opening the OS share sheet.
class FakeReportSharer implements ReportSharer {
  int shareCount = 0;
  String? lastPayload;

  @override
  Future<void> share(String text) async {
    shareCount++;
    lastPayload = text;
  }
}

/// A runner that always fails with [AIAnalysisException] (error-path tests).
class ThrowingScanAnalysisRunner implements ScanAnalysisRunner {
  const ThrowingScanAnalysisRunner();

  @override
  Future<AnalysisResultArgs> run({
    required List<EvidenceImage> evidence,
    required String geminiApiKey,
  }) async {
    throw const AIAnalysisException('ANALYSIS INTERRUPTED');
  }
}

/// A runner whose [run] future stays pending until [complete] is called, so a
/// test can observe the processing UI before the pipeline resolves.
class DeferredScanAnalysisRunner implements ScanAnalysisRunner {
  final Completer<AnalysisResultArgs> _completer =
      Completer<AnalysisResultArgs>();
  List<EvidenceImage>? lastEvidence;
  int runCount = 0;

  void complete(AnalysisResultArgs args) => _completer.complete(args);

  @override
  Future<AnalysisResultArgs> run({
    required List<EvidenceImage> evidence,
    required String geminiApiKey,
  }) {
    runCount++;
    lastEvidence = evidence;
    return _completer.future;
  }
}

/// A [ScanController] seeded with in-memory evidence + sample detected fields so
/// the processing/evidence screens see a session without a real camera.
class SeededScanController extends ScanController {
  @override
  ScanState build() {
    return ScanState(
      evidence: <EvidenceImage>[
        EvidenceImage(
          file: stubImage('front.png'),
          role: EvidenceRole.front,
          sequence: 1,
          label: 'Front',
        ),
        EvidenceImage(
          file: stubImage('back.png'),
          role: EvidenceRole.back,
          sequence: 2,
          label: 'Back',
        ),
      ],
      liveOcrText: 'MRP ₹120\nNET QTY 500 g\nAcme Foods',
      detectedFields: const <DetectedField>[
        DetectedField(
          rectNormalized: Rect.fromLTWH(0.1, 0.1, 0.4, 0.08),
          label: DetectedFieldLabels.productName,
          text: 'Oat Crunch',
        ),
        DetectedField(
          rectNormalized: Rect.fromLTWH(0.1, 0.3, 0.3, 0.07),
          label: DetectedFieldLabels.mrp,
          text: 'MRP ₹120',
        ),
        DetectedField(
          rectNormalized: Rect.fromLTWH(0.1, 0.5, 0.6, 0.07),
          label: DetectedFieldLabels.manufacturer,
          text: 'Acme Foods',
        ),
        DetectedField(
          rectNormalized: Rect.fromLTWH(0.1, 0.7, 0.5, 0.07),
          label: DetectedFieldLabels.mandatoryDeclaration,
          text: 'NET QTY 500 g',
        ),
      ],
    );
  }
}

// --- Pump helpers -----------------------------------------------------------

/// Mounts [AnalysisResultScreen] for [analysis] under a minimal router with
/// keyed `/scan/evidence` + `/report-issue` placeholders, overriding
/// [reportSharerProvider] (recording fake) and [scanStateProvider] (seeded).
Future<void> pumpReport(
  WidgetTester tester, {
  required ComplianceAnalysis analysis,
  FakeReportSharer? sharer,
}) async {
  final router = GoRouter(
    initialLocation: AppRoutes.scanResultPath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.scanResultPath,
        builder: (_, __) => AnalysisResultScreen(
          args: AnalysisResultArgs(
            analysis: analysis,
            ocrText: 'OCR',
            primaryImage: stubImage(),
          ),
        ),
      ),
      GoRoute(
        path: AppRoutes.scanEvidencePath,
        builder: (_, __) => const Placeholder(key: kEvidenceRouteKey),
      ),
      GoRoute(
        path: AppRoutes.reportIssuePath,
        builder: (_, __) => const Placeholder(key: kReportIssueRouteKey),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        reportSharerProvider.overrideWithValue(sharer ?? FakeReportSharer()),
        scanStateProvider.overrideWith(SeededScanController.new),
      ],
      child: MaterialApp.router(theme: VeriqooTheme.dark, routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

/// Mounts [EvidenceViewerScreen] with the seeded (or empty) scan session.
Future<void> pumpEvidence(
  WidgetTester tester, {
  EvidenceViewerArgs args = const EvidenceViewerArgs(),
  bool seeded = true,
}) async {
  final router = GoRouter(
    initialLocation: AppRoutes.scanEvidencePath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.scanEvidencePath,
        builder: (_, __) => EvidenceViewerScreen(args: args),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        if (seeded) scanStateProvider.overrideWith(SeededScanController.new),
      ],
      child: MaterialApp.router(theme: VeriqooTheme.dark, routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

/// Mounts [ScanProcessingScreen] with the seeded session + an injected [runner]
/// and a keyed `/scan/result` placeholder so navigation is observable.
Future<void> pumpProcessing(
  WidgetTester tester, {
  required ScanAnalysisRunner runner,
  bool seeded = true,
}) async {
  final router = GoRouter(
    initialLocation: AppRoutes.scanProcessingPath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.scanProcessingPath,
        builder: (_, __) => const ScanProcessingScreen(),
      ),
      GoRoute(
        path: AppRoutes.scanResultPath,
        builder: (_, __) => const Placeholder(key: kScanResultRouteKey),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        if (seeded) scanStateProvider.overrideWith(SeededScanController.new),
        scanAnalysisRunnerProvider.overrideWithValue(runner),
      ],
      child: MaterialApp.router(theme: VeriqooTheme.dark, routerConfig: router),
    ),
  );
  // Mount + post-frame _run; drain microtasks so the fake pipeline resolves.
  await tester.pump();
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}
