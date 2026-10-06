/// Centralized, localization-ready copy for the Phase 7 HISTORY experience:
/// the inspection ledger, search, inspection detail, and product detail.
///
/// Mirrors the `HomeStrings` / `ResultStrings` pattern (plain `static const`
/// fields) so every user-facing string lives in one place and can later be
/// swapped for an `AppLocalizations` lookup without touching the widgets.
abstract final class HistoryStrings {
  const HistoryStrings._();

  // --- Ledger screen ---------------------------------------------------------
  static const String title = 'INSPECTIONS';

  // Action affordances (announced to screen readers).
  static const String searchAction = 'Search inspections';
  static const String filterAction = 'Filter inspections';
  static const String sortAction = 'Sort inspections';

  // Date-group labels.
  static const String groupToday = 'TODAY';
  static const String groupYesterday = 'YESTERDAY';
  static const String groupUndated = 'UNDATED';

  // Ledger empty state.
  static const String emptyTitle = 'NO INSPECTIONS';
  static const String emptyMessage =
      'Your verification history will appear here after your first product '
      'analysis.';
  static const String emptyAction = 'SCAN A PRODUCT';

  // Ledger error state.
  static const String errorTitle = 'COULD NOT LOAD HISTORY';
  static const String errorMessage =
      'Your inspection history could not be loaded. Check your connection and '
      'try again.';
  static const String retry = 'RETRY';

  // Load-more sentinel.
  static const String loadingMore = 'Loading more';

  // --- Search screen ---------------------------------------------------------
  static const String searchTitle = 'SEARCH';
  static const String searchLabel = 'SEARCH';
  static const String searchHint =
      'Product, inspection ID, manufacturer, date, or issue';
  static const String recentSearches = 'RECENT SEARCHES';
  static const String suggestions = 'SUGGESTIONS';
  static const String clear = 'CLEAR';

  // No-results empty state.
  static const String noResultsTitle = 'NO MATCHES';
  static const String noResultsMessage =
      'No inspections match your search. Try a different product, ID, or '
      'manufacturer.';

  // --- Filter / sort sheet ---------------------------------------------------
  static const String filterTitle = 'FILTER & SORT';
  static const String filterStatus = 'STATUS';
  static const String sortOrder = 'SORT';
  static const String statusAll = 'ALL';
  static const String statusVerified = 'VERIFIED';
  static const String statusFlagged = 'FLAGGED';
  static const String statusMissing = 'MISSING';
  static const String statusViolation = 'VIOLATION';
  static const String sortNewest = 'NEWEST';
  static const String sortOldest = 'OLDEST';
  static const String sortScoreHigh = 'SCORE HIGH→LOW';
  static const String sortScoreLow = 'SCORE LOW→HIGH';
  static const String apply = 'APPLY';
  static const String reset = 'RESET';

  // --- Inspection detail -----------------------------------------------------
  static const String inspectionTitle = 'INSPECTION';
  static const String capturedImage = 'CAPTURED IMAGE';
  static const String imageUnavailable = 'Image unavailable';
  static const String detailErrorTitle = 'COULD NOT LOAD INSPECTION';
  static const String detailErrorMessage =
      'This inspection could not be loaded. Check your connection and try '
      'again.';
  static const String notFoundTitle = 'INSPECTION NOT FOUND';
  static const String notFoundMessage =
      'This inspection is no longer available. It may have been removed.';

  // --- Product detail --------------------------------------------------------
  static const String productTitle = 'PRODUCT';
  static const String inspectionHistory = 'INSPECTION HISTORY';
  static const String latestScore = 'LATEST';
  static const String bestScore = 'BEST';
  static const String productDerivedNote =
      'DERIVED — grouped by product name. VERIQOO has no backend product '
      'record; this view is synthesized from your inspections.';
  static const String productNotFoundTitle = 'PRODUCT NOT FOUND';
  static const String productNotFoundMessage =
      'This product could not be derived from your inspection history.';

  /// Pluralizes an inspection count, e.g. `1 INSPECTION` / `4 INSPECTIONS`.
  static String inspectionsCount(int n) =>
      n == 1 ? '1 INSPECTION' : '$n INSPECTIONS';
}
