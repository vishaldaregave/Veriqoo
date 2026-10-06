import 'package:flutter/material.dart';

import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A VERIQOO modal bottom sheet surface.
///
/// Renders on [VeriqooTokens.surfaceRaised] with md-radius top corners, a drag
/// handle, an optional [title], and the provided content. Use [VeriqooBottomSheet.show]
/// to present it.
class VeriqooBottomSheet extends StatelessWidget {
  const VeriqooBottomSheet({
    super.key,
    required this.child,
    this.title,
  });

  /// Sheet body.
  final Widget child;

  /// Optional title shown above the content.
  final String? title;

  /// Presents [child] as a VERIQOO bottom sheet and resolves with the value
  /// passed to `Navigator.pop`.
  static Future<T?> show<T>(
    BuildContext context, {
    required Widget child,
    String? title,
    bool isScrollControlled = false,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: isScrollControlled,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (_) => VeriqooBottomSheet(title: title, child: child),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return SafeArea(
      top: false,
      child: Container(
        width: double.infinity,
        decoration: BoxDecoration(
          color: tokens.surfaceRaised,
          borderRadius: VeriqooRadius.top(VeriqooRadius.md),
          border: Border.all(color: tokens.borderHairline, width: 1),
        ),
        padding: const EdgeInsets.fromLTRB(
          VeriqooSpacing.s24,
          VeriqooSpacing.s12,
          VeriqooSpacing.s24,
          VeriqooSpacing.s24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Drag handle.
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: tokens.borderStrong,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            if (title != null) ...[
              const SizedBox(height: VeriqooSpacing.s16),
              Text(
                title!,
                style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
              ),
            ],
            const SizedBox(height: VeriqooSpacing.s16),
            Flexible(child: child),
          ],
        ),
      ),
    );
  }
}
