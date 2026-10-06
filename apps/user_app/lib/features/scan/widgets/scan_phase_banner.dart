import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/model/scan_phase.dart';

/// A compact bottom pill showing the current [ScanPhase] caption with a 1px
/// progress tick that advances with the phase ordinal. Subtle motion only — no
/// `CircularProgressIndicator`. Collapses to an instant swap under reduced
/// motion.
class ScanPhaseBanner extends StatelessWidget {
  const ScanPhaseBanner({super.key, required this.phase});

  final ScanPhase phase;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final reduceMotion = VeriqooMotion.reduceMotion(context);
    // Fraction of the phase machine completed (0..1).
    final progress =
        (phase.index + 1) / ScanPhase.values.length;

    return Semantics(
      liveRegion: true,
      label: phase.caption,
      child: ExcludeSemantics(
        child: Container(
          decoration: BoxDecoration(
            color: tokens.surfaceRaised.withValues(alpha: 0.85),
            border: Border.all(color: tokens.borderHairline, width: 1),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: VeriqooSpacing.s16,
                  vertical: VeriqooSpacing.s8,
                ),
                child: AnimatedSwitcher(
                  duration: reduceMotion ? Duration.zero : VeriqooMotion.base,
                  switchInCurve: VeriqooMotion.enter,
                  child: Text(
                    phase.caption,
                    key: ValueKey<ScanPhase>(phase),
                    textAlign: TextAlign.center,
                    style:
                        VeriqooType.meta.copyWith(color: tokens.textPrimary),
                  ),
                ),
              ),
              // 1px progress tick that advances with the phase ordinal.
              SizedBox(
                height: 1,
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final width = constraints.maxWidth * progress;
                    final bar = Align(
                      alignment: Alignment.centerLeft,
                      child: SizedBox(
                        width: width,
                        child: ColoredBox(color: tokens.textPrimary),
                      ),
                    );
                    if (reduceMotion) {
                      return bar;
                    }
                    return AnimatedContainer(
                      duration: VeriqooMotion.base,
                      curve: VeriqooMotion.move,
                      alignment: Alignment.centerLeft,
                      width: width,
                      child: ColoredBox(color: tokens.textPrimary),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
