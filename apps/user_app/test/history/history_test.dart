import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/history/history_detail_screen.dart';
import 'package:flutter_application_1/features/history/history_screen.dart';
import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/inspections/inspections_repository.dart';
import 'package:flutter_application_1/features/inspections/product_summary.dart';
import 'package:flutter_application_1/features/products/product_detail_screen.dart';
import 'package:flutter_application_1/features/search/search_screen.dart';

import '../home/home_harness.dart';

/// Mounts [child] at [initialLocation] under a minimal router + the VERIQOO
/// dark theme, with the inspections repository overridden by [repo]. Never
/// `pumpAndSettle` (background painters loop forever).
Future<void> _pump(
  WidgetTester tester, {
  required InspectionsRepository repo,
  required String initialLocation,
}) async {
  final router = GoRouter(
    initialLocation: initialLocation,
    routes: <RouteBase>[
      GoRoute(path: AppRoutes.homePath, builder: (_, __) => const Placeholder()),
      GoRoute(path: AppRoutes.scanPath, builder: (_, __) => const Placeholder()),
      GoRoute(
        path: AppRoutes.searchPath,
        builder: (_, __) => const SearchScreen(),
      ),
      GoRoute(
        path: AppRoutes.historyPath,
        builder: (_, __) => const HistoryScreen(),
        routes: <RouteBase>[
          GoRoute(
            path: AppRoutes.historyDetailSegment,
            builder: (_, state) =>
                HistoryDetailScreen(id: state.pathParameters['id'] ?? ''),
          ),
        ],
      ),
      GoRoute(
        path: AppRoutes.productDetailPath,
        builder: (_, state) =>
            ProductDetailScreen(id: state.pathParameters['id'] ?? ''),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [inspectionsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp.router(theme: VeriqooTheme.dark, routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  group('HistoryScreen', () {
    testWidgets('shows the intelligent empty state when there are no records',
        (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(),
        initialLocation: AppRoutes.historyPath,
      );
      expect(find.text(HistoryStrings.emptyTitle), findsOneWidget);
      expect(find.text(HistoryStrings.emptyAction), findsOneWidget);
    });

    testWidgets('renders inspection rows grouped by date', (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: AppRoutes.historyPath,
      );
      expect(find.byType(VeriqooInspectionCard), findsNWidgets(2));
      expect(find.text('Oat Crunch Cereal'), findsOneWidget);
    });

    testWidgets('surfaces an error state when the load fails', (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(fail: true),
        initialLocation: AppRoutes.historyPath,
      );
      expect(find.text(HistoryStrings.errorTitle), findsOneWidget);
    });
  });

  group('SearchScreen', () {
    testWidgets('filters the corpus by typed text', (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: AppRoutes.searchPath,
      );
      await tester.enterText(find.byType(TextField), 'Oat');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('Oat Crunch Cereal'), findsOneWidget);
      expect(find.text('Spring Water 1L'), findsNothing);
    });

    testWidgets('shows the no-results state for an unmatched query',
        (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: AppRoutes.searchPath,
      );
      await tester.enterText(find.byType(TextField), 'zzzzzz');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text(HistoryStrings.noResultsTitle), findsOneWidget);
    });
  });

  group('HistoryDetailScreen', () {
    testWidgets('renders the read-only report for a saved inspection',
        (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: '/history/aaaa1111',
      );
      expect(find.byType(VeriqooScore), findsOneWidget);
      expect(find.text('Oat Crunch Cereal'), findsWidgets);
    });

    testWidgets('shows the not-found state for an unknown id', (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: '/history/does-not-exist',
      );
      expect(find.text(HistoryStrings.notFoundTitle), findsOneWidget);
    });
  });

  group('ProductDetailScreen', () {
    testWidgets('derives a product and lists its inspections', (tester) async {
      final key = productKeyFor('Oat Crunch Cereal');
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: '/products/$key',
      );
      expect(find.text('Oat Crunch Cereal'), findsWidgets);
      expect(find.byType(VeriqooInspectionCard), findsOneWidget);
    });

    testWidgets('shows the not-found state for an unknown product key',
        (tester) async {
      await _pump(
        tester,
        repo: FakeInspectionsRepository(records: sampleRecords()),
        initialLocation: '/products/p-00000000',
      );
      expect(find.text(HistoryStrings.productNotFoundTitle), findsOneWidget);
    });
  });
}
