/// Centralized, user-facing copy for the Settings surface and the language
/// selector.
///
/// Every string the Settings screens render lives here as a flat
/// `static const` (matching `auth_strings.dart`) so a later localization phase
/// can migrate copy mechanically. Keep labels short — rows ellipsize and
/// longer translations should degrade gracefully.
abstract final class SettingsStrings {
  const SettingsStrings._();

  // --- Screen ---
  static const String title = 'Settings';

  // --- Section headers (uppercased by VeriqooSectionHeader) ---
  static const String appearanceSection = 'Appearance';
  static const String languageSection = 'Language';
  static const String notificationsSection = 'Notifications';
  static const String privacySection = 'Privacy';

  // --- Appearance (theme mode) ---
  static const String themeDark = 'Dark';
  static const String themeLight = 'Light';
  static const String themeSystem = 'System';

  // --- Language ---
  static const String languageRowLabel = 'App language';
  static const String languageTitle = 'Language';
  static const String languageTodoNote =
      'VERIQOO\'s interface text stays in English for now. Selecting a language '
      'sets your preference and localizes system elements like date pickers; '
      'full translations arrive in a later update.';

  // --- Notification preferences (local/skeleton toggles) ---
  static const String notifyInspections = 'Inspection updates';
  static const String notifyReports = 'Report responses';
  static const String notifyAlerts = 'Compliance alerts';

  // --- Privacy (local/skeleton toggles) ---
  static const String shareDiagnostics = 'Share diagnostics';
  static const String personalizedTips = 'Personalized tips';
}
