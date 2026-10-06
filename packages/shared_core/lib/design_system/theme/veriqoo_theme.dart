import 'package:flutter/material.dart';

import 'veriqoo_tokens.dart';
import 'veriqoo_typography.dart';

/// Builds the VERIQOO [ThemeData] for each scheme, wiring the bundled Inter
/// font, the [VeriqooTokens] extension, and a [TextTheme] derived from
/// [VeriqooType]. Material surface tinting is disabled so surfaces stay the
/// exact token colors.
abstract final class VeriqooTheme {
  const VeriqooTheme._();

  /// Dark scheme — the primary VERIQOO appearance.
  static ThemeData get dark => _build(VeriqooTokens.dark);

  /// Light scheme.
  static ThemeData get light => _build(VeriqooTokens.light);

  static ThemeData _build(VeriqooTokens tokens) {
    final colorScheme = ColorScheme(
      brightness: tokens.brightness,
      primary: tokens.inverseBg,
      onPrimary: tokens.inverseText,
      secondary: tokens.inverseBg,
      onSecondary: tokens.inverseText,
      surface: tokens.surface,
      onSurface: tokens.textPrimary,
      error: tokens.textPrimary,
      onError: tokens.inverseText,
      surfaceTint: Colors.transparent,
      outline: tokens.borderStrong,
    );

    final textTheme = _textTheme(tokens);

    return ThemeData(
      useMaterial3: true,
      brightness: tokens.brightness,
      fontFamily: kInterFamily,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: tokens.bg,
      canvasColor: tokens.bg,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,
      extensions: <ThemeExtension<dynamic>>[tokens],
    );
  }

  static TextTheme _textTheme(VeriqooTokens tokens) {
    final primary = tokens.textPrimary;
    final secondary = tokens.textSecondary;
    return TextTheme(
      displayLarge: VeriqooType.display.copyWith(color: primary),
      headlineLarge: VeriqooType.h1.copyWith(color: primary),
      headlineMedium: VeriqooType.h2.copyWith(color: primary),
      headlineSmall: VeriqooType.h3.copyWith(color: primary),
      titleLarge: VeriqooType.h3.copyWith(color: primary),
      bodyLarge: VeriqooType.bodyL.copyWith(color: primary),
      bodyMedium: VeriqooType.body.copyWith(color: primary),
      bodySmall: VeriqooType.caption.copyWith(color: secondary),
      labelLarge: VeriqooType.meta.copyWith(color: primary),
      labelMedium: VeriqooType.meta.copyWith(color: secondary),
      labelSmall: VeriqooType.meta.copyWith(color: secondary),
    );
  }
}
