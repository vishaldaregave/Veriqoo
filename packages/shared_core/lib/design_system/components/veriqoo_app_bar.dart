import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';
import 'veriqoo_icon_button.dart';

/// VERIQOO top app bar: an optional left back affordance, a centered title,
/// and an optional right action. The back button is **auto-hidden** when
/// `Navigator.canPop(context)` is false, so a root screen shows no back arrow
/// without the caller branching.
///
/// Implements [PreferredSizeWidget] so it can be used directly as a
/// `Scaffold.appBar`.
class VeriqooAppBar extends StatelessWidget implements PreferredSizeWidget {
  const VeriqooAppBar({
    super.key,
    required this.title,
    this.action,
    this.onBack,
    this.showBack = true,
    this.height = 56,
  });

  /// Centered title text.
  final String title;

  /// Optional trailing action (e.g. a [VeriqooIconButton]).
  final Widget? action;

  /// Back handler. Defaults to `Navigator.maybePop` when omitted.
  final VoidCallback? onBack;

  /// When false the back affordance is never shown even if the route can pop.
  final bool showBack;

  /// Bar height.
  final double height;

  @override
  Size get preferredSize => Size.fromHeight(height);

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final canPop = Navigator.canPop(context);
    final showBackButton = showBack && canPop;

    return SafeArea(
      bottom: false,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: tokens.bg,
          border: Border(
            bottom: BorderSide(color: tokens.borderHairline, width: 1),
          ),
        ),
        padding: const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s8),
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Centered title.
            Center(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s48),
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
                ),
              ),
            ),
            // Leading back affordance.
            if (showBackButton)
              Align(
                alignment: Alignment.centerLeft,
                child: VeriqooIconButton(
                  icon: VeriqooIcons.back,
                  semanticLabel: 'Back',
                  onPressed: onBack ?? () => Navigator.maybePop(context),
                ),
              ),
            // Trailing action.
            if (action != null)
              Align(
                alignment: Alignment.centerRight,
                child: action,
              ),
          ],
        ),
      ),
    );
  }
}
