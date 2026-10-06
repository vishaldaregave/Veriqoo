import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/legacy.dart';

/// The grouping a notification belongs to in the notification center.
enum NotificationCategory { system, inspections, reports, alerts }

/// A single in-app notification. Skeleton type for later phases.
@immutable
class AppNotification {
  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.category,
    this.receivedAt,
  });

  final String id;
  final String title;
  final String body;

  /// Which section the notification is grouped under.
  final NotificationCategory category;

  /// When the notification was received, if known.
  final DateTime? receivedAt;
}

/// The LIVE notification list. Skeleton — stays empty until a later phase wires
/// real delivery. The notification center shows the empty state by default;
/// demo data lives separately behind an explicit toggle (see
/// `demo_notifications.dart`) and is never presented as live delivery.
final notificationsProvider =
    StateProvider<List<AppNotification>>((ref) => const <AppNotification>[]);
