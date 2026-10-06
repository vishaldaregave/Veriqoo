import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

/// A page backdrop that paints the token background, an optional monochrome
/// [background] effect painter below the content, and the [child] on top.
///
/// Keeps placeholder screens looking intentional (a faint technical effect)
/// without each screen re-implementing the stack. The painter is wrapped in an
/// [IgnorePointer] so it never intercepts touches.
class VeriqooBackdrop extends StatelessWidget {
  const VeriqooBackdrop({
    super.key,
    required this.child,
    this.background,
  });

  /// Foreground content.
  final Widget child;

  /// Optional background effect (e.g. [InspectionGrid], [TechnicalCoordinates]).
  final Widget? background;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Stack(
      children: [
        Positioned.fill(child: ColoredBox(color: tokens.bg)),
        if (background != null)
          Positioned.fill(child: IgnorePointer(child: background!)),
        child,
      ],
    );
  }
}
