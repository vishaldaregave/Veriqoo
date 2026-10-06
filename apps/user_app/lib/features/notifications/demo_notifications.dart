/// NON-LIVE demo notification data for the notification center.
///
/// IMPORTANT: this is sample content for design/QA ONLY. It is NEVER delivered
/// or presented as a real notification. The live source
/// ([notificationsProvider]) stays empty until a later phase wires real
/// delivery; this demo set surfaces ONLY when the explicit, clearly-labelled
/// [demoNotificationsEnabledProvider] toggle is turned on (default OFF).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import 'package:flutter_application_1/features/notifications/notification_providers.dart';
import 'package:flutter_application_1/features/notifications/notification_strings.dart';

/// A fixed sample set spanning all four categories. Clearly demo — not live.
const List<AppNotification> kDemoNotifications = <AppNotification>[
  AppNotification(
    id: 'demo-system-1',
    title: NotificationStrings.demoSystemTitle,
    body: NotificationStrings.demoSystemBody,
    category: NotificationCategory.system,
  ),
  AppNotification(
    id: 'demo-inspection-1',
    title: NotificationStrings.demoInspectionTitle,
    body: NotificationStrings.demoInspectionBody,
    category: NotificationCategory.inspections,
  ),
  AppNotification(
    id: 'demo-report-1',
    title: NotificationStrings.demoReportTitle,
    body: NotificationStrings.demoReportBody,
    category: NotificationCategory.reports,
  ),
  AppNotification(
    id: 'demo-alert-1',
    title: NotificationStrings.demoAlertTitle,
    body: NotificationStrings.demoAlertBody,
    category: NotificationCategory.alerts,
  ),
];

/// Whether the clearly-labelled demo set is shown. Default FALSE, so the
/// notification center shows the empty state until a reviewer explicitly flips
/// this. NEVER treat an enabled value as real delivery.
final demoNotificationsEnabledProvider = StateProvider<bool>((ref) => false);

/// The list the notification center renders: the demo set when the demo toggle
/// is on, otherwise the (empty) live [notificationsProvider].
final visibleNotificationsProvider = Provider<List<AppNotification>>((ref) {
  return ref.watch(demoNotificationsEnabledProvider)
      ? kDemoNotifications
      : ref.watch(notificationsProvider);
});
