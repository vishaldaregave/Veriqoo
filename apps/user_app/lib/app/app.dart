import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/router.dart';
import 'package:flutter_application_1/core/providers/locale_provider.dart';
import 'package:flutter_application_1/core/providers/theme_mode_provider.dart';

/// Root of the VERIQOO user app.
///
/// Supplies both VERIQOO theme schemes and the [themeModeProvider]-driven mode
/// (default dark, honoring the OS when set to system), wires GoRouter via
/// [goRouterProvider], and feeds the [localeProvider] selection into
/// [MaterialApp.locale].
///
/// Note: a non-English selection resolves Material's own localizations (date
/// pickers, tooltips) via [GlobalMaterialLocalizations]; VERIQOO's own UI copy
/// stays English until a localization phase populates ARB files.
class VeriqooApp extends ConsumerWidget {
  const VeriqooApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(goRouterProvider);
    final themeMode = ref.watch(themeModeProvider);
    final locale = ref.watch(localeProvider);

    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'VERIQOO',
      theme: VeriqooTheme.light,
      darkTheme: VeriqooTheme.dark,
      themeMode: themeMode,
      locale: locale,
      supportedLocales: kSupportedLanguages.map((l) => l.locale),
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      routerConfig: router,
    );
  }
}
