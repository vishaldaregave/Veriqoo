import 'package:flutter/widgets.dart';

/// VERIQOO motion tokens: durations, curves, and a reduced-motion helper.
///
/// Entrances ease out, positional moves ease in-out, and presses settle
/// without overshoot. All looping or sweeping animation must consult
/// [reduceMotion] and resolve to a static end state when it returns true.
abstract final class VeriqooMotion {
  const VeriqooMotion._();

  static const Duration fast = Duration(milliseconds: 160);
  static const Duration base = Duration(milliseconds: 240);
  static const Duration slow = Duration(milliseconds: 320);
  static const Duration cinematic = Duration(milliseconds: 700);

  /// Entrances (fade/scale in).
  static const Curve enter = Curves.easeOutCubic;

  /// Positional movement between two states.
  static const Curve move = Curves.easeInOutCubic;

  /// Press micro-interaction curve — a no-overshoot stand-in for [pressSpring].
  static const Curve press = Curves.easeOutCubic;

  /// Critically-damped spring for press feedback: it settles on the target
  /// without crossing (overshooting) it.
  static const SpringDescription pressSpring = SpringDescription(
    mass: 1,
    stiffness: 500,
    // ratio 1.0 => critical damping => no overshoot.
    damping: 2 * 22.360679774997898, // 2 * sqrt(stiffness * mass)
  );

  /// Whether animations should be reduced to a static end state.
  ///
  /// Honors the platform "reduce motion" accessibility flag, which Flutter
  /// surfaces through [MediaQueryData.disableAnimations].
  static bool reduceMotion(BuildContext context) {
    return MediaQuery.maybeDisableAnimationsOf(context) ?? false;
  }
}
