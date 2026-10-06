import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/legacy.dart';

/// A supported UI language: its [locale], the English name used in secondary
/// text, and the [endonym] (the language's own name) shown as the primary
/// label in the selector.
@immutable
class AppLanguage {
  const AppLanguage({
    required this.locale,
    required this.englishName,
    required this.endonym,
  });

  final Locale locale;
  final String englishName;
  final String endonym;
}

/// The languages VERIQOO offers in the selector, in display order. English is
/// first (the default). Endonyms are each language's own name.
///
// TODO(localization): persist the selection (e.g. secure storage, mirroring
// RecentSearchesStore) and populate ARB files. UI copy stays English until a
// localization phase lands — selecting a non-English language only changes
// Material's own localizations (date pickers, etc.), not VERIQOO's strings.
const List<AppLanguage> kSupportedLanguages = <AppLanguage>[
  AppLanguage(locale: Locale('en'), englishName: 'English', endonym: 'English'),
  AppLanguage(locale: Locale('hi'), englishName: 'Hindi', endonym: 'हिन्दी'),
  AppLanguage(locale: Locale('mr'), englishName: 'Marathi', endonym: 'मराठी'),
  AppLanguage(locale: Locale('bn'), englishName: 'Bengali', endonym: 'বাংলা'),
  AppLanguage(locale: Locale('ta'), englishName: 'Tamil', endonym: 'தமிழ்'),
  AppLanguage(locale: Locale('te'), englishName: 'Telugu', endonym: 'తెలుగు'),
  AppLanguage(locale: Locale('gu'), englishName: 'Gujarati', endonym: 'ગુજરાતી'),
  AppLanguage(locale: Locale('kn'), englishName: 'Kannada', endonym: 'ಕನ್ನಡ'),
  AppLanguage(
    locale: Locale('ml'),
    englishName: 'Malayalam',
    endonym: 'മലയാളം',
  ),
  AppLanguage(locale: Locale('pa'), englishName: 'Punjabi', endonym: 'ਪੰਜਾਬੀ'),
];

/// The selected UI locale. Defaults to English (the first supported language).
///
/// Non-persisted, mirroring [themeModeProvider] — the established app-wide
/// preference pattern. See the TODO above for the persistence follow-up.
final localeProvider = StateProvider<Locale>(
  (ref) => kSupportedLanguages.first.locale,
);
