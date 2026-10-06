import 'package:flutter/material.dart';

import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A centered empty-state placeholder: a monoline [icon], a [title], optional
/// [message] body, and an optional [action] widget.
class VeriqooEmptyState extends StatelessWidget {
  const VeriqooEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.action,
  });

  /// Monochrome line icon shown above the title.
  final IconData icon;

  /// Primary line.
  final String title;

  /// Optional supporting copy.
  final String? message;

  /// Optional action (e.g. a VeriqooButton).
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Semantics(
      label: message == null ? title : '$title. $message',
      child: ExcludeSemantics(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(VeriqooSpacing.s32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 40, color: tokens.textTertiary),
                const SizedBox(height: VeriqooSpacing.s16),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
                ),
                if (message != null) ...[
                  const SizedBox(height: VeriqooSpacing.s8),
                  Text(
                    message!,
                    textAlign: TextAlign.center,
                    style: VeriqooType.body
                        .copyWith(color: tokens.textSecondary),
                  ),
                ],
                if (action != null) ...[
                  const SizedBox(height: VeriqooSpacing.s24),
                  action!,
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
