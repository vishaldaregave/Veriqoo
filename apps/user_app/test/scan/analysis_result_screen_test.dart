import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/result/result_strings.dart';
import 'package:flutter_application_1/features/scan/result/widgets/product_details_panel.dart';
import 'package:flutter_application_1/features/scan/result/widgets/report_finding_tile.dart';
import 'package:flutter_application_1/features/scan/result/widgets/report_qr_sheet.dart';

import 'result_harness.dart';

void main() {
  testWidgets('all-compliant: header, score, summary, no findings',
      (tester) async {
    await pumpReport(tester, analysis: fixtureAllCompliant());

    // Header: "COMPLIANCE REPORT" (app bar + section label) + product name.
    expect(find.text(ResultStrings.reportTitle), findsWidgets);
    expect(find.text('OAT CRUNCH CEREAL'), findsOneWidget);

    // Score dial + three summary chips.
    expect(find.byType(VeriqooScore), findsOneWidget);
    expect(find.text(ResultStrings.summaryVerified), findsOneWidget);
    expect(find.text(ResultStrings.summaryFlagged), findsOneWidget);
    expect(find.text(ResultStrings.summaryMissing), findsOneWidget);

    // Product-details panel present; no findings for a clean report.
    expect(find.byType(ProductDetailsPanel), findsOneWidget);
    expect(find.byType(ReportFindingTile), findsNothing);

    // Action buttons present.
    expect(find.byKey(kReportShareButtonKey), findsOneWidget);
    expect(find.byKey(kReportQrButtonKey), findsOneWidget);
    expect(find.byKey(kReportSaveButtonKey), findsOneWidget);

    expect(tester.takeException(), isNull);
  });

  testWidgets('missing-only: shows "Not detected" on empty fields',
      (tester) async {
    await pumpReport(tester, analysis: fixtureMissingOnly());

    expect(find.byType(ProductDetailsPanel), findsOneWidget);
    // mrp/manufacturer/address/packingDate/customerCare empty → 5 placeholders.
    expect(find.text(ResultStrings.notDetected), findsWidgets);
    // Three missing declarations → three finding tiles.
    expect(find.byType(ReportFindingTile), findsNWidgets(3));

    expect(tester.takeException(), isNull);
  });

  testWidgets('with-issues: one finding tile per possible issue',
      (tester) async {
    await pumpReport(tester, analysis: fixtureWithIssues());

    expect(find.byType(ReportFindingTile), findsNWidgets(3));
    expect(find.byType(VeriqooScore), findsOneWidget);

    expect(tester.takeException(), isNull);
  });

  testWidgets('tapping Share invokes the sharer (no real sheet)',
      (tester) async {
    final sharer = FakeReportSharer();
    await pumpReport(tester, analysis: fixtureWithIssues(), sharer: sharer);

    await tester.ensureVisible(find.byKey(kReportShareButtonKey));
    await tester.tap(find.byKey(kReportShareButtonKey));
    await tester.pump();

    expect(sharer.shareCount, 1);
    expect(sharer.lastPayload, contains('VERIQOO Compliance Report'));
    expect(sharer.lastPayload, contains('Score: 75/100'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('tapping Generate QR opens a modal with a QR image',
      (tester) async {
    await pumpReport(tester, analysis: fixtureAllCompliant());

    await tester.ensureVisible(find.byKey(kReportQrButtonKey));
    await tester.tap(find.byKey(kReportQrButtonKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byKey(kReportQrImageKey), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('tapping a finding action navigates to the evidence route',
      (tester) async {
    await pumpReport(tester, analysis: fixtureWithIssues());

    final action = find.byKey(reportFindingActionKey(1));
    await tester.ensureVisible(action);
    await tester.tap(action);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byKey(kEvidenceRouteKey), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
