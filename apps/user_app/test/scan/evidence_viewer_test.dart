import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_args.dart';
import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_screen.dart';
import 'package:flutter_application_1/features/scan/evidence/widgets/evidence_image_view.dart';
import 'package:flutter_application_1/features/scan/result/report_finding.dart';
import 'package:flutter_application_1/features/scan/result/result_strings.dart';
import 'package:flutter_application_1/features/scan/widgets/detection_boxes.dart';

import 'result_harness.dart';

/// A missing-MRP finding that keyword-matches the seeded MRP detection region.
const _mrpFinding = ReportFinding(
  number: 1,
  kind: ReportFindingKind.missingDeclaration,
  title: 'MRP',
  status: VeriqooStatusKind.missing,
  missingField: 'MRP',
);

void main() {
  testWidgets('renders the viewer with an InteractiveViewer + derived boxes',
      (tester) async {
    await pumpEvidence(tester);

    expect(find.byKey(kEvidenceInteractiveViewerKey), findsOneWidget);
    expect(find.byType(DetectionBoxesOverlay), findsOneWidget);
    // Two seeded images → the selector strip is shown.
    expect(find.byKey(evidenceTileKey(0)), findsOneWidget);
    expect(find.byKey(evidenceTileKey(1)), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('focusing a finding zooms the view (transform changes)',
      (tester) async {
    await pumpEvidence(
      tester,
      args: const EvidenceViewerArgs(focusFinding: _mrpFinding),
    );
    // Let the focus animation settle.
    await tester.pump(const Duration(milliseconds: 400));

    final viewer = tester.widget<InteractiveViewer>(
      find.byKey(kEvidenceInteractiveViewerKey),
    );
    final matrix = viewer.transformationController!.value;
    expect(matrix.getMaxScaleOnAxis(), greaterThan(1.0));

    // The DERIVED association is clearly marked.
    expect(find.text(ResultStrings.derivedNote), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('"WHY THIS MATTERS" opens a bottom sheet', (tester) async {
    await pumpEvidence(
      tester,
      args: const EvidenceViewerArgs(focusFinding: _mrpFinding),
    );

    await tester.tap(find.byKey(kEvidenceWhyButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(VeriqooBottomSheet), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('empty evidence shows the empty state', (tester) async {
    await pumpEvidence(tester, seeded: false);

    expect(find.byType(VeriqooEmptyState), findsOneWidget);
    expect(find.text(ResultStrings.evidenceEmptyTitle), findsOneWidget);
    expect(find.byKey(kEvidenceInteractiveViewerKey), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
