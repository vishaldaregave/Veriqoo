import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/providers/locale_provider.dart';
import 'package:flutter_application_1/core/providers/theme_mode_provider.dart';
import 'package:flutter_application_1/features/auth/auth_actions.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/settings/settings_preferences.dart';
import 'package:flutter_application_1/features/settings/settings_strings.dart';

/// Settings, grouped into editorial sections on hairline dividers:
///
/// * Appearance — the functional 3-way theme switch backed by
///   [themeModeProvider].
/// * Language — a nav row into the language selector showing the current
///   endonym; the selection is held by [localeProvider].
/// * Notifications / Privacy — local toggles backed by
///   [settingsPreferencesProvider] (skeleton state).
/// * Security — biometric setup and sign-out.
///
/// Sign-out routes through [authActionsProvider]; the `onAuthStateChange`
/// listener then flips the router guard to unauthenticated and the redirect
/// returns to `/auth/login` — no manual navigation needed.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final mode = ref.watch(themeModeProvider);
    final locale = ref.watch(localeProvider);
    final prefs = ref.watch(settingsPreferencesProvider);
    final prefsController = ref.read(settingsPreferencesProvider.notifier);

    final currentLanguage = kSupportedLanguages.firstWhere(
      (l) => l.locale == locale,
      orElse: () => kSupportedLanguages.first,
    );

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: SettingsStrings.title),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(VeriqooSpacing.s24),
          children: [
            // --- Appearance ---
            const VeriqooSectionHeader(
              title: SettingsStrings.appearanceSection,
            ),
            _ThemeOption(
              label: SettingsStrings.themeDark,
              selected: mode == ThemeMode.dark,
              onTap: () =>
                  ref.read(themeModeProvider.notifier).state = ThemeMode.dark,
            ),
            const VeriqooDivider(),
            _ThemeOption(
              label: SettingsStrings.themeLight,
              selected: mode == ThemeMode.light,
              onTap: () =>
                  ref.read(themeModeProvider.notifier).state = ThemeMode.light,
            ),
            const VeriqooDivider(),
            _ThemeOption(
              label: SettingsStrings.themeSystem,
              selected: mode == ThemeMode.system,
              onTap: () => ref.read(themeModeProvider.notifier).state =
                  ThemeMode.system,
            ),
            const SizedBox(height: VeriqooSpacing.s24),

            // --- Language ---
            const VeriqooSectionHeader(
              title: SettingsStrings.languageSection,
            ),
            _NavRow(
              leading: VeriqooIcons.language,
              label: SettingsStrings.languageRowLabel,
              trailing: Text(
                currentLanguage.endonym.toUpperCase(),
                style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
              ),
              onTap: () => context.go(AppRoutes.languagePath),
            ),
            const SizedBox(height: VeriqooSpacing.s24),

            // --- Notifications ---
            const VeriqooSectionHeader(
              title: SettingsStrings.notificationsSection,
            ),
            _SwitchRow(
              label: SettingsStrings.notifyInspections,
              value: prefs.notifyInspections,
              onChanged: (_) => prefsController.toggleNotifyInspections(),
            ),
            const VeriqooDivider(),
            _SwitchRow(
              label: SettingsStrings.notifyReports,
              value: prefs.notifyReports,
              onChanged: (_) => prefsController.toggleNotifyReports(),
            ),
            const VeriqooDivider(),
            _SwitchRow(
              label: SettingsStrings.notifyAlerts,
              value: prefs.notifyAlerts,
              onChanged: (_) => prefsController.toggleNotifyAlerts(),
            ),
            const SizedBox(height: VeriqooSpacing.s24),

            // --- Privacy ---
            const VeriqooSectionHeader(
              title: SettingsStrings.privacySection,
            ),
            _SwitchRow(
              label: SettingsStrings.shareDiagnostics,
              value: prefs.shareDiagnostics,
              onChanged: (_) => prefsController.toggleShareDiagnostics(),
            ),
            const VeriqooDivider(),
            _SwitchRow(
              label: SettingsStrings.personalizedTips,
              value: prefs.personalizedTips,
              onChanged: (_) => prefsController.togglePersonalizedTips(),
            ),
            const SizedBox(height: VeriqooSpacing.s24),

            // --- Security ---
            const VeriqooSectionHeader(title: AuthStrings.securitySection),
            _NavRow(
              leading: VeriqooIcons.shield,
              label: AuthStrings.biometricTitle,
              showChevron: true,
              onTap: () => context.go(AppRoutes.biometricSetupPath),
            ),
            const VeriqooDivider(),
            _NavRow(
              leading: VeriqooIcons.logout,
              label: AuthStrings.signOutCta,
              onTap: () => ref.read(authActionsProvider).signOut(),
            ),
          ],
        ),
      ),
    );
  }
}

/// A selectable appearance option: a label with a trailing check when active.
class _ThemeOption extends StatelessWidget {
  const _ThemeOption({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s16),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
              ),
            ),
            if (selected)
              Icon(VeriqooIcons.check, size: 20, color: tokens.textPrimary),
          ],
        ),
      ),
    );
  }
}

/// A tappable settings nav row: leading glyph, label, an optional trailing
/// adornment (e.g. the current language), and an optional trailing chevron.
class _NavRow extends StatelessWidget {
  const _NavRow({
    required this.label,
    required this.leading,
    required this.onTap,
    this.trailing,
    this.showChevron = false,
  });

  final String label;
  final IconData leading;
  final VoidCallback onTap;
  final Widget? trailing;
  final bool showChevron;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s16),
        child: Row(
          children: [
            Icon(leading, size: 20, color: tokens.textPrimary),
            const SizedBox(width: VeriqooSpacing.s16),
            Expanded(
              child: Text(
                label,
                style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
              ),
            ),
            if (trailing != null) ...[
              trailing!,
              const SizedBox(width: VeriqooSpacing.s12),
            ],
            if (showChevron)
              Icon(
                VeriqooIcons.chevronRight,
                size: 20,
                color: tokens.textTertiary,
              ),
          ],
        ),
      ),
    );
  }
}

/// A settings toggle row: a label with a trailing MONOCHROME [Switch] (token
/// colors only — no accent hue).
class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            thumbColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.selected)
                  ? tokens.bg
                  : tokens.textSecondary,
            ),
            trackColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.selected)
                  ? tokens.textPrimary
                  : Colors.transparent,
            ),
            trackOutlineColor:
                WidgetStateProperty.all(tokens.borderStrong),
          ),
        ],
      ),
    );
  }
}
