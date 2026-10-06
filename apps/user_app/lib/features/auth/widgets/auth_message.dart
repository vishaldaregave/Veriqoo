import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

/// Inline status line shared by the auth screens.
///
/// Renders nothing when [message] is null, so screens can bind it directly to a
/// nullable error/notice field. Styled per the VERIQOO error treatment: a small
/// alert glyph plus [VeriqooType.caption] in [VeriqooTokens.textPrimary] (never
/// `textTertiary`, which would fail WCAG for this essential copy).
class AuthMessage extends StatelessWidget {
  const AuthMessage(this.message, {super.key, this.icon = VeriqooIcons.alert});

  /// The message to show, or null to render an empty box.
  final String? message;

  /// Leading glyph (defaults to the alert triangle).
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final message = this.message;
    if (message == null) {
      return const SizedBox.shrink();
    }
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Padding(
      padding: const EdgeInsets.only(top: VeriqooSpacing.s16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: tokens.textPrimary),
          const SizedBox(width: VeriqooSpacing.s8),
          Expanded(
            child: Text(
              message,
              style: VeriqooType.caption.copyWith(
                color: tokens.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
