import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/core/providers/locale_provider.dart';
import 'package:flutter_application_1/core/widgets/app_background.dart';
import 'package:flutter_application_1/features/settings/settings_strings.dart';

/// The language selector: a routed full screen listing every supported UI
/// language by its endonym, marking the current selection with a check.
///
/// Selecting a language updates [localeProvider] (and therefore
/// `MaterialApp.locale`). TRANSLATION of VERIQOO's own copy is out of scope —
/// a footer note makes that explicit; see the TODO in `locale_provider.dart`.
class LanguageScreen extends ConsumerWidget {
  const LanguageScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final selected = ref.watch(localeProvider);

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: SettingsStrings.languageTitle),
      body: VeriqooBackdrop(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.symmetric(
              horizontal: VeriqooSpacing.s24,
              vertical: VeriqooSpacing.s8,
            ),
            children: [
              for (var i = 0; i < kSupportedLanguages.length; i++) ...[
                if (i > 0) const VeriqooDivider(),
                _LanguageRow(
                  language: kSupportedLanguages[i],
                  selected: kSupportedLanguages[i].locale == selected,
                  onTap: () => ref.read(localeProvider.notifier).state =
                      kSupportedLanguages[i].locale,
                ),
              ],
              const SizedBox(height: VeriqooSpacing.s24),
              Text(
                SettingsStrings.languageTodoNote,
                style: VeriqooType.caption.copyWith(color: tokens.textTertiary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A single language row: endonym (primary), English name (secondary), and a
/// trailing check when it is the active selection.
class _LanguageRow extends StatelessWidget {
  const _LanguageRow({
    required this.language,
    required this.selected,
    required this.onTap,
  });

  final AppLanguage language;
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    language.endonym,
                    style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
                  ),
                  // Only show the English name when it differs from the
                  // endonym (so "English" isn't printed twice).
                  if (language.englishName != language.endonym) ...[
                    const SizedBox(height: VeriqooSpacing.s4),
                    Text(
                      language.englishName,
                      style: VeriqooType.body
                          .copyWith(color: tokens.textSecondary),
                    ),
                  ],
                ],
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
