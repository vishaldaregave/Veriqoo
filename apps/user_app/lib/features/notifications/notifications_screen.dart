import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/core/widgets/app_background.dart';
import 'package:flutter_application_1/features/notifications/demo_notifications.dart';
import 'package:flutter_application_1/features/notifications/notification_providers.dart';
import 'package:flutter_application_1/features/notifications/notification_strings.dart';

/// The notification center: category-grouped rows (SYSTEM / INSPECTIONS /
/// REPORTS / ALERTS) read from [visibleNotificationsProvider].
///
/// The LIVE source stays empty, so by default this shows the empty state. The
/// app-bar eye action toggles a clearly-labelled DEMO set (see
/// `demo_notifications.dart`) — visible for design/QA, never live delivery.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final visible = ref.watch(visibleNotificationsProvider);

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: VeriqooAppBar(
        title: NotificationStrings.title,
        action: VeriqooIconButton(
          icon: VeriqooIcons.eye,
          semanticLabel: NotificationStrings.demoToggleLabel,
          onPressed: () => ref
              .read(demoNotificationsEnabledProvider.notifier)
              .state = !ref.read(demoNotificationsEnabledProvider),
        ),
      ),
      body: VeriqooBackdrop(
        background: const DataTicker(),
        child: SafeArea(
          child: visible.isEmpty
              ? const VeriqooEmptyState(
                  icon: VeriqooIcons.notifications,
                  title: NotificationStrings.emptyTitle,
                  message: NotificationStrings.emptyMessage,
                )
              : ListView(
                  padding: const EdgeInsets.symmetric(
                    horizontal: VeriqooSpacing.s24,
                    vertical: VeriqooSpacing.s8,
                  ),
                  children: [
                    for (final category in NotificationCategory.values)
                      ..._categorySection(category, visible),
                  ],
                ),
        ),
      ),
    );
  }

  /// Builds the header + rows for [category], or nothing when it has no items.
  List<Widget> _categorySection(
    NotificationCategory category,
    List<AppNotification> all,
  ) {
    final items = all.where((n) => n.category == category).toList();
    if (items.isEmpty) {
      return const <Widget>[];
    }
    return <Widget>[
      VeriqooSectionHeader(title: _headerFor(category)),
      for (var i = 0; i < items.length; i++) ...[
        if (i > 0) const VeriqooDivider(),
        _NotificationTile(item: items[i]),
      ],
      const SizedBox(height: VeriqooSpacing.s24),
    ];
  }

  String _headerFor(NotificationCategory category) {
    switch (category) {
      case NotificationCategory.system:
        return NotificationStrings.systemHeader;
      case NotificationCategory.inspections:
        return NotificationStrings.inspectionsHeader;
      case NotificationCategory.reports:
        return NotificationStrings.reportsHeader;
      case NotificationCategory.alerts:
        return NotificationStrings.alertsHeader;
    }
  }
}

/// A single notification row: a title and a supporting body line.
class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item});

  final AppNotification item;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.title,
            style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
          ),
          const SizedBox(height: VeriqooSpacing.s4),
          Text(
            item.body,
            style: VeriqooType.body.copyWith(color: tokens.textSecondary),
          ),
        ],
      ),
    );
  }
}
