import 'package:flutter/material.dart';

import 'veriqoo_colors.dart';

/// Semantic design tokens for VERIQOO, delivered as a [ThemeExtension] so any
/// widget can resolve them with
/// `Theme.of(context).extension<VeriqooTokens>()!` and switch between the dark
/// (primary) and light schemes with no per-widget branching.
///
/// All eleven semantic colors are composed from the monochrome
/// [VeriqooColors] ramp — there is no accent hue, and status is never encoded
/// by color alone.
///
/// ## WCAG contrast guidance
/// The exact token hex values are mandated by the design spec. Computed
/// contrast against the scheme background:
///
/// * [textPrimary] and [textSecondary] pass WCAG AA for body text in both
///   schemes (dark `textSecondary` #A0A0A0 on #0A0A0A ≈ 7.57:1; light
///   `textSecondary` #5E5E5E on #F5F5F2 ≈ 5.93:1).
/// * [textTertiary] does **not** reach the 4.5:1 AA threshold for normal body
///   text (dark #5E5E5E on #0A0A0A ≈ 3.05:1; light #A0A0A0 on #F5F5F2 ≈
///   2.39:1). Restrict [textTertiary] to large, decorative, disabled, or meta
///   text only — never essential body copy.
@immutable
class VeriqooTokens extends ThemeExtension<VeriqooTokens> {
  const VeriqooTokens({
    required this.brightness,
    required this.bg,
    required this.bgTrue,
    required this.surface,
    required this.surfaceRaised,
    required this.borderHairline,
    required this.borderStrong,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.inverseBg,
    required this.inverseText,
  });

  /// Scheme brightness this token set represents.
  final Brightness brightness;

  /// Primary scaffold / page background.
  final Color bg;

  /// True black/white background for hero, loading, and scanner surfaces.
  final Color bgTrue;

  /// Default raised content surface (cards, panels).
  final Color surface;

  /// Higher-emphasis surface for floating nav, sheets, and modals.
  final Color surfaceRaised;

  /// Hairline divider/border — the default separator in place of shadows.
  final Color borderHairline;

  /// Stronger border for emphasized edges and focus affordances.
  final Color borderStrong;

  /// Primary text color (passes WCAG AA for body text).
  final Color textPrimary;

  /// Secondary text color (passes WCAG AA for body text).
  final Color textSecondary;

  /// Tertiary text color. Does NOT pass AA for normal body text — restrict to
  /// large/decorative/disabled/meta usage. See class doc.
  final Color textTertiary;

  /// Inverse (high-contrast) background used for primary fills.
  final Color inverseBg;

  /// Text/glyph color on top of [inverseBg].
  final Color inverseText;

  /// Dark scheme — the primary VERIQOO appearance.
  static const VeriqooTokens dark = VeriqooTokens(
    brightness: Brightness.dark,
    bg: VeriqooColors.deepBlack,
    bgTrue: VeriqooColors.black,
    surface: VeriqooColors.charcoal,
    surfaceRaised: VeriqooColors.graphite,
    borderHairline: Color(0x1AFFFFFF), // white @ 10% opacity
    borderStrong: VeriqooColors.borderStrongDark,
    textPrimary: VeriqooColors.offWhite,
    textSecondary: VeriqooColors.lightGrey,
    textTertiary: VeriqooColors.midGrey,
    inverseBg: VeriqooColors.white,
    inverseText: VeriqooColors.deepBlack,
  );

  /// Light scheme.
  static const VeriqooTokens light = VeriqooTokens(
    brightness: Brightness.light,
    bg: VeriqooColors.offWhite,
    bgTrue: VeriqooColors.white,
    surface: VeriqooColors.white,
    surfaceRaised: VeriqooColors.white,
    borderHairline: VeriqooColors.borderGrey,
    borderStrong: VeriqooColors.lightGrey,
    textPrimary: VeriqooColors.deepBlack,
    textSecondary: VeriqooColors.midGrey,
    textTertiary: VeriqooColors.lightGrey,
    inverseBg: VeriqooColors.deepBlack,
    inverseText: VeriqooColors.white,
  );

  @override
  VeriqooTokens copyWith({
    Brightness? brightness,
    Color? bg,
    Color? bgTrue,
    Color? surface,
    Color? surfaceRaised,
    Color? borderHairline,
    Color? borderStrong,
    Color? textPrimary,
    Color? textSecondary,
    Color? textTertiary,
    Color? inverseBg,
    Color? inverseText,
  }) {
    return VeriqooTokens(
      brightness: brightness ?? this.brightness,
      bg: bg ?? this.bg,
      bgTrue: bgTrue ?? this.bgTrue,
      surface: surface ?? this.surface,
      surfaceRaised: surfaceRaised ?? this.surfaceRaised,
      borderHairline: borderHairline ?? this.borderHairline,
      borderStrong: borderStrong ?? this.borderStrong,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textTertiary: textTertiary ?? this.textTertiary,
      inverseBg: inverseBg ?? this.inverseBg,
      inverseText: inverseText ?? this.inverseText,
    );
  }

  @override
  VeriqooTokens lerp(ThemeExtension<VeriqooTokens>? other, double t) {
    if (other is! VeriqooTokens) {
      return this;
    }
    return VeriqooTokens(
      brightness: t < 0.5 ? brightness : other.brightness,
      bg: Color.lerp(bg, other.bg, t)!,
      bgTrue: Color.lerp(bgTrue, other.bgTrue, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceRaised: Color.lerp(surfaceRaised, other.surfaceRaised, t)!,
      borderHairline: Color.lerp(borderHairline, other.borderHairline, t)!,
      borderStrong: Color.lerp(borderStrong, other.borderStrong, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textTertiary: Color.lerp(textTertiary, other.textTertiary, t)!,
      inverseBg: Color.lerp(inverseBg, other.inverseBg, t)!,
      inverseText: Color.lerp(inverseText, other.inverseText, t)!,
    );
  }
}
