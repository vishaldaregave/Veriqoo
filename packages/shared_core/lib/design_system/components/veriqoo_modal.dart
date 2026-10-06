import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_elevation.dart';
import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';
import 'veriqoo_icon_button.dart';

/// A centered VERIQOO dialog on [VeriqooTokens.surfaceRaised] with md radius
/// and the single permitted [VeriqooElevation.softShadow]. Provides a title,
/// optional close affordance, content, and an actions row. Use
/// [VeriqooModal.show] to present it.
class VeriqooModal extends StatelessWidget {
  const VeriqooModal({
    super.key,
    required this.title,
    required this.child,
    this.actions = const <Widget>[],
    this.showClose = true,
  });

  /// Dialog title.
  final String title;

  /// Dialog body.
  final Widget child;

  /// Trailing action buttons (laid out at the end).
  final List<Widget> actions;

  /// Whether to show the top-right close button.
  final bool showClose;

  /// Presents [child] as a VERIQOO modal dialog.
  static Future<T?> show<T>(
    BuildContext context, {
    required String title,
    required Widget child,
    List<Widget> actions = const <Widget>[],
    bool showClose = true,
    bool barrierDismissible = true,
  }) {
    return showDialog<T>(
      context: context,
      barrierDismissible: barrierDismissible,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (_) => VeriqooModal(
        title: title,
        actions: actions,
        showClose: showClose,
        child: child,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(VeriqooSpacing.s24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Material(
            color: Colors.transparent,
            child: Container(
              decoration: BoxDecoration(
                color: tokens.surfaceRaised,
                borderRadius: VeriqooRadius.mdAll,
                border: Border.all(color: tokens.borderHairline, width: 1),
                boxShadow: VeriqooElevation.softShadow,
              ),
              padding: const EdgeInsets.all(VeriqooSpacing.s24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: VeriqooType.h3
                              .copyWith(color: tokens.textPrimary),
                        ),
                      ),
                      if (showClose)
                        VeriqooIconButton(
                          icon: VeriqooIcons.close,
                          semanticLabel: 'Close',
                          iconSize: 18,
                          onPressed: () => Navigator.of(context).maybePop(),
                        ),
                    ],
                  ),
                  const SizedBox(height: VeriqooSpacing.s16),
                  Flexible(child: child),
                  if (actions.isNotEmpty) ...[
                    const SizedBox(height: VeriqooSpacing.s24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        for (var i = 0; i < actions.length; i++) ...[
                          if (i > 0) const SizedBox(width: VeriqooSpacing.s12),
                          actions[i],
                        ],
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
