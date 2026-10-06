import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/result/result_strings.dart';
import 'package:flutter_application_1/features/scan/scan_processing_screen.dart';

import 'result_harness.dart';
import 'scan_harness.dart';

void main() {
  testWidgets('success: shows phase caption + extracted panel, then '
      'navigates to the result route', (tester) async {
    final runner = DeferredScanAnalysisRunner();
    await pumpProcessing(tester, runner: runner);

    // While the pipeline is pending the processing UI is visible.
    expect(find.byKey(kProcessingPhaseCaptionKey), findsOneWidget);
    expect(find.byKey(kProcessingExtractPanelKey), findsOneWidget);
    // Extracted values come from the seeded live-OCR detected fields.
    expect(find.text('Oat Crunch'), findsOneWidget);
    expect(runner.runCount, 1);

    // Resolve the pipeline → it replaces itself with /scan/result.
    runner.complete(
      AnalysisResultArgs(
        analysis: fixtureAllCompliant(),
        ocrText: 'x',
        primaryImage: stubImage(),
      ),
    );
    await tester.pump(); // resume _run → stop ticker → pushReplacement
    await tester.pump(const Duration(milliseconds: 350)); // settle transition

    expect(find.byKey(kScanResultRouteKey), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('error: shows the VeriqooErrorState, never a raw exception',
      (tester) async {
    await pumpProcessing(tester, runner: const ThrowingScanAnalysisRunner());

    expect(find.byKey(kProcessingErrorStateKey), findsOneWidget);
    expect(find.text(ResultStrings.analysisInterruptedTitle), findsWidgets);
    expect(find.text(ResultStrings.tryAgain), findsOneWidget);
    // Did not navigate away.
    expect(find.byKey(kScanResultRouteKey), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
