import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/notifications/demo_notifications.dart';
import 'package:flutter_application_1/features/notifications/notification_strings.dart';
import 'package:flutter_application_1/features/notifications/notifications_screen.dart';

/// Mounts [NotificationsScreen] under the VERIQOO dark theme. Never
/// `pumpAndSettle` — the DataTicker backdrop loops forever.
Future<void> _pumpNotifications(
  WidgetTester tester, {
  bool demoEnabled = false,
}) async {
  await tester.binding.setSurfaceSize(const Size(600, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        if (demoEnabled)
          demoNotificationsEnabledProvider.overrideWith((ref) => true),
      ],
      child: const MaterialApp(
        home: NotificationsScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  group('NotificationsScreen', () {
    testWidgets('shows the empty state by default (live empty, demo off)',
        (tester) async {
      await _pumpNotifications(tester);

      expect(find.text(NotificationStrings.emptyTitle), findsOneWidget);
      // No category sections when there is nothing to show.
      expect(find.text(NotificationStrings.systemHeader), findsNothing);
      expect(find.text(NotificationStrings.inspectionsHeader), findsNothing);
      expect(find.text(NotificationStrings.reportsHeader), findsNothing);
      expect(find.text(NotificationStrings.alertsHeader), findsNothing);
    });

    testWidgets('renders category groups when the demo set is enabled',
        (tester) async {
      await _pumpNotifications(tester, demoEnabled: true);

      expect(find.text(NotificationStrings.emptyTitle), findsNothing);
      expect(find.text(NotificationStrings.systemHeader), findsOneWidget);
      expect(find.text(NotificationStrings.inspectionsHeader), findsOneWidget);
      expect(find.text(NotificationStrings.reportsHeader), findsOneWidget);
      expect(find.text(NotificationStrings.alertsHeader), findsOneWidget);
      expect(find.text(NotificationStrings.demoInspectionTitle), findsOneWidget);
      expect(find.text(NotificationStrings.demoReportTitle), findsOneWidget);
    });

    testWidgets('the eye action toggles the demo set into view',
        (tester) async {
      await _pumpNotifications(tester);

      // Starts empty.
      expect(find.text(NotificationStrings.emptyTitle), findsOneWidget);

      await tester.tap(find.byType(VeriqooIconButton));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text(NotificationStrings.emptyTitle), findsNothing);
      expect(find.text(NotificationStrings.systemHeader), findsOneWidget);
      expect(find.text(NotificationStrings.demoInspectionTitle), findsOneWidget);
    });
  });
}
