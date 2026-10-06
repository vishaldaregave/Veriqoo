import 'package:flutter/material.dart';

import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// An editorial section header: a small uppercase meta label with an optional
/// trailing [action]. Used to introduce groups of content.
class VeriqooSectionHeader extends StatelessWidget {
  const VeriqooSectionHeader({
    super.key,
    required this.title,
    this.action,
    this.subtitle,
  });

  /// Uppercase meta label.
  final String title;

  /// Optional supporting line beneath the title.
  final String? subtitle;

  /// Optional trailing widget (e.g. a ghost button).
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title.toUpperCase(),
                  style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: VeriqooSpacing.s4),
                  Text(
                    subtitle!,
                    style:
                        VeriqooType.body.copyWith(color: tokens.textPrimary),
                  ),
                ],
              ],
            ),
          ),
          if (action != null) action!,
        ],
      ),
    );
  }
}
