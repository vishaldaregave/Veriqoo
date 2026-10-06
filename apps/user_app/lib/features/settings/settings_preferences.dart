import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Local, in-memory settings toggles for the Notifications and Privacy
/// sections.
///
// TODO: persist these (e.g. secure storage like RecentSearchesStore) and wire
// the notification preferences to real delivery in a later phase. For now they
// are skeleton state so the Settings UI is functional and testable.
@immutable
class SettingsPreferences {
  const SettingsPreferences({
    this.notifyInspections = true,
    this.notifyReports = true,
    this.notifyAlerts = true,
    this.shareDiagnostics = false,
    this.personalizedTips = false,
  });

  final bool notifyInspections;
  final bool notifyReports;
  final bool notifyAlerts;
  final bool shareDiagnostics;
  final bool personalizedTips;

  SettingsPreferences copyWith({
    bool? notifyInspections,
    bool? notifyReports,
    bool? notifyAlerts,
    bool? shareDiagnostics,
    bool? personalizedTips,
  }) {
    return SettingsPreferences(
      notifyInspections: notifyInspections ?? this.notifyInspections,
      notifyReports: notifyReports ?? this.notifyReports,
      notifyAlerts: notifyAlerts ?? this.notifyAlerts,
      shareDiagnostics: shareDiagnostics ?? this.shareDiagnostics,
      personalizedTips: personalizedTips ?? this.personalizedTips,
    );
  }
}

/// Holds the local [SettingsPreferences] and flips individual toggles.
class SettingsPreferencesController extends Notifier<SettingsPreferences> {
  @override
  SettingsPreferences build() => const SettingsPreferences();

  void toggleNotifyInspections() =>
      state = state.copyWith(notifyInspections: !state.notifyInspections);

  void toggleNotifyReports() =>
      state = state.copyWith(notifyReports: !state.notifyReports);

  void toggleNotifyAlerts() =>
      state = state.copyWith(notifyAlerts: !state.notifyAlerts);

  void toggleShareDiagnostics() =>
      state = state.copyWith(shareDiagnostics: !state.shareDiagnostics);

  void togglePersonalizedTips() =>
      state = state.copyWith(personalizedTips: !state.personalizedTips);
}

/// The local settings-preferences store.
final settingsPreferencesProvider =
    NotifierProvider<SettingsPreferencesController, SettingsPreferences>(
  SettingsPreferencesController.new,
);
