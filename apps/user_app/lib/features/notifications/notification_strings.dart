/// Centralized, user-facing copy for the notification center.
///
/// Mirrors the `HistoryStrings` pattern (flat `static const` fields) so copy
/// lives in one place and can later be swapped for an `AppLocalizations`
/// lookup. Category headers are UPPERCASE (they feed `VeriqooSectionHeader`).
abstract final class NotificationStrings {
  const NotificationStrings._();

  // --- Screen ---
  static const String title = 'Notifications';

  // --- Category headers ---
  static const String systemHeader = 'SYSTEM';
  static const String inspectionsHeader = 'INSPECTIONS';
  static const String reportsHeader = 'REPORTS';
  static const String alertsHeader = 'ALERTS';

  // --- Empty state ---
  static const String emptyTitle = 'NO NOTIFICATIONS';
  static const String emptyMessage =
      'Updates about your inspections, reports, and compliance alerts will '
      'appear here.';

  // --- Demo affordance (clearly non-live) ---
  static const String demoToggleLabel = 'Toggle demo notifications';

  // --- Demo items (NON-LIVE sample copy; see demo_notifications.dart) ---
  static const String demoSystemTitle = 'Welcome to VERIQOO';
  static const String demoSystemBody =
      'Scan a product to run your first compliance check.';
  static const String demoInspectionTitle = 'Inspection completed';
  static const String demoInspectionBody =
      'Your product analysis is ready to review.';
  static const String demoReportTitle = 'Report updated';
  static const String demoReportBody =
      'An authority responded to your report.';
  static const String demoAlertTitle = 'Compliance alert';
  static const String demoAlertBody =
      'A product you inspected was flagged for a labeling issue.';
}
