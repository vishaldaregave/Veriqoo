import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';
import 'veriqoo_button.dart';

/// A centered error state: an alert glyph, an error [title], optional [message]
/// body, and an optional retry action. Shares the empty-state skeleton but is
/// framed for failures and defaults to a retry button when [onRetry] is set.
class VeriqooErrorState extends StatelessWidget {
  const VeriqooErrorState({
    super.key,
    this.title = 'Something went wrong',
    this.message,
    this.onRetry,
    this.retryLabel = 'Retry',
    this.icon = VeriqooIcons.alert,
  });

  /// Primary error line.
  final String title;

  /// Optional supporting copy.
  final String? message;

  /// Retry handler; when set a secondary retry button is shown.
  final VoidCallback? onRetry;

  /// Retry button label.
  final String retryLabel;

  /// Leading glyph (defaults to the alert icon).
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Semantics(
      label: message == null ? title : '$title. $message',
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(VeriqooSpacing.s32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 40, color: tokens.textPrimary),
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
                  style:
                      VeriqooType.body.copyWith(color: tokens.textSecondary),
                ),
              ],
              if (onRetry != null) ...[
                const SizedBox(height: VeriqooSpacing.s24),
                VeriqooButton(
                  label: retryLabel,
                  variant: VeriqooButtonVariant.secondary,
                  icon: VeriqooIcons.history,
                  onPressed: onRetry,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
