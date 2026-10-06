import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/home/home_strings.dart';

/// The large editorial hero: three stacked Display lines reading
/// `VERIFY / WHAT'S ON / THE LABEL.` with a supporting body line beneath.
///
/// The three lines are scaled together with a single [FittedBox] so they stay
/// uniform and never overflow on narrow screens, and are exposed to screen
/// readers as one combined sentence.
class HomeHero extends StatelessWidget {
  const HomeHero({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final displayStyle = VeriqooType.display.copyWith(color: tokens.textPrimary);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Semantics(
          label: HomeStrings.heroSemantics,
          header: true,
          child: ExcludeSemantics(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(HomeStrings.heroLine1, style: displayStyle, maxLines: 1),
                  Text(HomeStrings.heroLine2, style: displayStyle, maxLines: 1),
                  Text(HomeStrings.heroLine3, style: displayStyle, maxLines: 1),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: VeriqooSpacing.s16),
        Text(
          HomeStrings.supporting,
          style: VeriqooType.bodyL.copyWith(color: tokens.textSecondary),
        ),
      ],
    );
  }
}
