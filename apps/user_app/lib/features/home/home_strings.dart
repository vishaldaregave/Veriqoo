/// Every user-facing string on the Home screen, centralized as `static const`
/// so a later phase can lift them into a localization layer without touching
/// widget code.
abstract final class HomeStrings {
  const HomeStrings._();

  // Wordmark.
  static const String wordmark = 'VERIQOO';

  // Time-of-day greeting prefixes (meta style, already uppercase).
  static const String goodMorning = 'GOOD MORNING';
  static const String goodAfternoon = 'GOOD AFTERNOON';
  static const String goodEvening = 'GOOD EVENING';

  // Editorial hero — three stacked display lines + a combined a11y string.
  static const String heroLine1 = 'VERIFY';
  static const String heroLine2 = "WHAT'S ON";
  static const String heroLine3 = 'THE LABEL.';
  static const String heroSemantics = "Verify what's on the label.";

  // Supporting line beneath the hero.
  static const String supporting =
      'Scan packaged products and check mandatory declarations with '
      'AI-powered compliance analysis.';

  // Call-to-action labels.
  static const String scanProduct = 'SCAN PRODUCT';
  static const String viewHistory = 'VIEW HISTORY';
  static const String scanAProduct = 'SCAN A PRODUCT';
  static const String viewAll = 'View all';

  // Metrics line.
  static const String inspected = 'INSPECTED';
  static const String flagged = 'FLAGGED';

  // Recent section.
  static const String recentInspections = 'RECENT INSPECTIONS';

  // Empty state.
  static const String emptyTitle = 'No inspections yet';
  static const String emptyMessage =
      'Your verification history will appear here after your first product '
      'analysis.';

  // Error state.
  static const String errorTitle = 'Could not load inspections';
  static const String errorMessage =
      'We could not reach your inspection records. Check your connection and '
      'try again.';

  // Online/offline indicator (shape + label, never color alone).
  static const String statusOnline = 'ONLINE';
  static const String statusOffline = 'OFFLINE';
  static const String statusUnknown = '—';
  static const String connectionStatusLabel = 'Connection status';

  // Icon-button accessibility labels.
  static const String notificationsLabel = 'Notifications';
  static const String profileLabel = 'Profile';

  // Metrics placeholder when a count is unavailable.
  static const String metricUnavailable = '—';
}
