import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/home/home_strings.dart';
import 'package:flutter_application_1/features/home/home_user.dart';
import 'package:flutter_application_1/features/inspections/inspections_repository.dart';

import 'home_harness.dart';

void main() {
  testWidgets('LOADING: hero + actions render, no exception', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(pending: true),
    );

    // Hero and both primary actions render regardless of data state.
    expect(find.text(HomeStrings.heroLine1), findsOneWidget);
    expect(find.text(HomeStrings.scanProduct), findsOneWidget);
    expect(find.text(HomeStrings.viewHistory), findsOneWidget);

    // The recent section shows the loading motif while the future is pending.
    expect(find.byType(VeriqooLoading), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('EMPTY: shows the intelligent empty state', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(
        counts: const InspectionSummaryCounts(total: 0, flagged: 0),
      ),
    );

    expect(find.text(HomeStrings.emptyMessage), findsOneWidget);
    expect(find.text(HomeStrings.scanAProduct), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('POPULATED: renders ledger rows and metrics labels', (
    tester,
  ) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(
        records: sampleRecords(),
        counts: const InspectionSummaryCounts(total: 2, flagged: 1),
      ),
    );

    expect(find.byType(VeriqooInspectionCard), findsWidgets);
    expect(find.text(HomeStrings.inspected), findsOneWidget);
    expect(find.text(HomeStrings.flagged), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('GREETING: shows name when present', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(),
      user: const HomeUser(name: 'Ada'),
    );

    expect(find.textContaining('GOOD'), findsOneWidget);
    expect(find.textContaining('Ada'), findsOneWidget);
  });

  testWidgets('GREETING: degrades gracefully with no user', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(),
      user: null,
    );

    // The bare time-of-day prefix still renders.
    expect(find.textContaining('GOOD'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('NAV: SCAN PRODUCT routes to /scan', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(records: sampleRecords()),
    );
    await tester.pump(const Duration(milliseconds: 400)); // finish entrance

    await tester.ensureVisible(find.text(HomeStrings.scanProduct));
    await tester.pump();
    await tester.tap(find.text(HomeStrings.scanProduct));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byKey(kScanRouteKey), findsOneWidget);
  });

  testWidgets('NAV: VIEW HISTORY routes to /history', (tester) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(records: sampleRecords()),
    );
    await tester.pump(const Duration(milliseconds: 400));

    await tester.ensureVisible(find.text(HomeStrings.viewHistory));
    await tester.pump();
    await tester.tap(find.text(HomeStrings.viewHistory));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byKey(kHistoryRouteKey), findsOneWidget);
  });

  testWidgets('ERROR: shows error state as an AsyncError (not uncaught)', (
    tester,
  ) async {
    await pumpHome(
      tester,
      repo: FakeInspectionsRepository(fail: true),
    );
    // Let the error futures settle into AsyncError.
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byType(VeriqooErrorState), findsOneWidget);
    expect(find.text(HomeStrings.errorTitle), findsOneWidget);
    // Hero still renders — a data failure degrades inline.
    expect(find.text(HomeStrings.heroLine1), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
