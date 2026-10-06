import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/home/home_strings.dart';
import 'package:flutter_application_1/features/inspections/inspections_repository.dart';

/// A slim editorial metrics line (NOT floating cards): big mono numbers with
/// uppercase meta labels, separated by a hairline [VeriqooDivider.vertical].
///
/// [counts] is nullable: null renders both values as `'—'` placeholders (used
/// for the loading and inline-error states). A null `flagged` within non-null
/// counts renders only that value as `'—'`. Numbers count up on first build
/// unless reduced motion is active.
class HomeMetrics extends StatelessWidget {
  const HomeMetrics({super.key, required this.counts});

  final InspectionSummaryCounts? counts;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = VeriqooMotion.reduceMotion(context);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        _Metric(
          label: HomeStrings.inspected,
          value: counts?.total,
          reduceMotion: reduceMotion,
        ),
        const SizedBox(width: VeriqooSpacing.s24),
        // A fixed-height hairline avoids IntrinsicHeight (the divider's inner
        // box has no inherent height, which can report an infinite intrinsic).
        const SizedBox(
          height: VeriqooSpacing.s48,
          child: VeriqooDivider.vertical(),
        ),
        const SizedBox(width: VeriqooSpacing.s24),
        _Metric(
          label: HomeStrings.flagged,
          value: counts?.flagged,
          reduceMotion: reduceMotion,
        ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.label,
    required this.value,
    required this.reduceMotion,
  });

  final String label;
  final int? value;
  final bool reduceMotion;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final numberStyle = VeriqooType.mono.copyWith(
      color: tokens.textPrimary,
      fontSize: 36,
      fontWeight: FontWeight.w500,
      height: 1,
    );

    final Widget number;
    final count = value;
    if (count == null) {
      number = Text(HomeStrings.metricUnavailable, style: numberStyle);
    } else {
      number = TweenAnimationBuilder<int>(
        tween: IntTween(begin: 0, end: count),
        duration: reduceMotion ? Duration.zero : VeriqooMotion.base,
        curve: VeriqooMotion.enter,
        builder: (context, animated, _) => Text(
          animated.toString().padLeft(2, '0'),
          style: numberStyle,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        number,
        const SizedBox(height: VeriqooSpacing.s4),
        Text(
          label,
          style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
        ),
      ],
    );
  }
}
