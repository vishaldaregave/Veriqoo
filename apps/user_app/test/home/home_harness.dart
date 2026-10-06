import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/providers/network_provider.dart';
import 'package:flutter_application_1/features/home/home_screen.dart';
import 'package:flutter_application_1/features/home/home_user.dart';
import 'package:flutter_application_1/features/inspections/inspection_detail.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/inspections/inspections_repository.dart';

/// Keys for the stand-in route targets so navigation is observable.
const Key kScanRouteKey = Key('route-scan');
const Key kHistoryRouteKey = Key('route-history');
const Key kHistoryDetailRouteKey = Key('route-history-detail');
const Key kNotificationsRouteKey = Key('route-notifications');
const Key kProfileRouteKey = Key('route-profile');

/// A fully controllable [InspectionsRepository] that NEVER touches
/// `Supabase.instance`. Configure it to drive each UI state:
///
/// * [pending] — futures never complete (loading).
/// * [fail] — futures throw (error / AsyncError).
/// * otherwise — resolves with [records] and [counts].
class FakeInspectionsRepository implements InspectionsRepository {
  FakeInspectionsRepository({
    this.records = const <InspectionRecord>[],
    this.counts = const InspectionSummaryCounts(total: 0, flagged: 0),
    this.pending = false,
    this.fail = false,
  });

  final List<InspectionRecord> records;
  final InspectionSummaryCounts counts;
  final bool pending;
  final bool fail;

  @override
  Future<List<InspectionRecord>> recentInspections({int limit = 5}) {
    if (pending) {
      return Completer<List<InspectionRecord>>().future;
    }
    if (fail) {
      return Future<List<InspectionRecord>>.error(StateError('load failed'));
    }
    return Future<List<InspectionRecord>>.value(
      records.take(limit).toList(growable: false),
    );
  }

  @override
  Future<InspectionSummaryCounts> summaryCounts() {
    if (pending) {
      return Completer<InspectionSummaryCounts>().future;
    }
    if (fail) {
      return Future<InspectionSummaryCounts>.error(StateError('count failed'));
    }
    return Future<InspectionSummaryCounts>.value(counts);
  }

  @override
  Future<List<InspectionRecord>> pagedInspections({
    int offset = 0,
    int limit = 20,
  }) {
    if (pending) {
      return Completer<List<InspectionRecord>>().future;
    }
    if (fail) {
      return Future<List<InspectionRecord>>.error(StateError('load failed'));
    }
    return Future<List<InspectionRecord>>.value(
      records.skip(offset).take(limit).toList(growable: false),
    );
  }

  @override
  Future<List<InspectionRecord>> allInspections({int limit = 200}) {
    if (pending) {
      return Completer<List<InspectionRecord>>().future;
    }
    if (fail) {
      return Future<List<InspectionRecord>>.error(StateError('load failed'));
    }
    return Future<List<InspectionRecord>>.value(
      records.take(limit).toList(growable: false),
    );
  }

  @override
  Future<InspectionDetail?> inspectionById(String id) {
    if (pending) {
      return Completer<InspectionDetail?>().future;
    }
    if (fail) {
      return Future<InspectionDetail?>.error(StateError('load failed'));
    }
    for (final record in records) {
      if (record.id == id || record.displayId == id) {
        return Future<InspectionDetail?>.value(
          InspectionDetail(
            record: record,
            analysis: ComplianceAnalysis(
              productName: record.productName,
              mrp: '',
              netQuantity: '',
              manufacturer: '',
              address: '',
              packingDate: '',
              customerCare: '',
              missingInformation: record.missingInformation,
              possibleIssues: const <ComplianceIssue>[],
            ),
            imageUrl: null,
            ocrText: '',
          ),
        );
      }
    }
    return Future<InspectionDetail?>.value(null);
  }
}

/// A couple of representative records, built through the real mapper.
List<InspectionRecord> sampleRecords() => <InspectionRecord>[
  InspectionRecord.fromMap(const <String, dynamic>{
    'id': 'aaaa1111',
    'product_name': 'Oat Crunch Cereal',
    'inspected_at': '2026-01-04T08:30:00Z',
    'is_compliant': false,
    'possible_issues': <Map<String, dynamic>>[
      <String, dynamic>{'severity': 'high', 'title': 'Missing MRP'},
    ],
    'missing_information': <String>['MRP'],
  }, index: 0),
  InspectionRecord.fromMap(const <String, dynamic>{
    'id': 'bbbb2222',
    'product_name': 'Spring Water 1L',
    'inspected_at': '2026-01-03T12:00:00Z',
    'is_compliant': true,
    'possible_issues': <Map<String, dynamic>>[],
    'missing_information': <String>[],
  }, index: 1),
];

/// Pumps [HomeScreen] inside a minimal router + the VERIQOO dark theme, with
/// the data/user/network providers overridden. Pumps a couple of fixed frames
/// (never `pumpAndSettle`, since the background motion loops forever).
Future<void> pumpHome(
  WidgetTester tester, {
  required InspectionsRepository repo,
  HomeUser? user,
  NetworkStatus network = NetworkStatus.online,
}) async {
  final router = GoRouter(
    initialLocation: AppRoutes.homePath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.homePath,
        builder: (_, __) => const HomeScreen(),
      ),
      GoRoute(
        path: AppRoutes.scanPath,
        builder: (_, __) => const Placeholder(key: kScanRouteKey),
      ),
      GoRoute(
        path: AppRoutes.historyPath,
        builder: (_, __) => const Placeholder(key: kHistoryRouteKey),
        routes: <RouteBase>[
          GoRoute(
            path: AppRoutes.historyDetailSegment,
            builder: (_, __) => const Placeholder(key: kHistoryDetailRouteKey),
          ),
        ],
      ),
      GoRoute(
        path: AppRoutes.notificationsPath,
        builder: (_, __) => const Placeholder(key: kNotificationsRouteKey),
      ),
      GoRoute(
        path: AppRoutes.profilePath,
        builder: (_, __) => const Placeholder(key: kProfileRouteKey),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        inspectionsRepositoryProvider.overrideWithValue(repo),
        currentUserProvider.overrideWithValue(user),
        networkStatusProvider.overrideWith((ref) => network),
      ],
      child: MaterialApp.router(
        theme: VeriqooTheme.dark,
        routerConfig: router,
      ),
    ),
  );

  // Flush the FutureProviders, then advance a fixed slice of entrance motion.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}
