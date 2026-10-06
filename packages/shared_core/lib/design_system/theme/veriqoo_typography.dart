import 'package:flutter/widgets.dart';

/// Font family identifiers for the bundled typefaces.
///
/// The `packages/shared_core/<Family>` prefix tells Flutter to resolve the
/// font from this package's bundled assets (declared in `pubspec.yaml`) rather
/// than the app's own asset bundle.
const String kInterFamily = 'packages/shared_core/Inter';
const String kMonoFamily = 'packages/shared_core/IBMPlexMono';

/// VERIQOO type ramp.
///
/// Inter is used for all prose; IBM Plex Mono (with tabular figures) is used
/// for numerals, IDs, scores, and OCR confidence so columns align. Each style
/// leaves `color` null — color is applied by widgets from [VeriqooTokens] so a
/// single style works across both schemes.
abstract final class VeriqooType {
  const VeriqooType._();

  static const TextStyle display = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 52,
    letterSpacing: -1.5,
    fontWeight: FontWeight.w600,
    height: 1.02,
  );

  static const TextStyle h1 = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 32,
    letterSpacing: -0.5,
    fontWeight: FontWeight.w700,
    height: 1.1,
  );

  static const TextStyle h2 = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 24,
    letterSpacing: -0.25,
    fontWeight: FontWeight.w600,
    height: 1.2,
  );

  static const TextStyle h3 = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 20,
    letterSpacing: 0,
    fontWeight: FontWeight.w600,
    height: 1.3,
  );

  static const TextStyle bodyL = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 16,
    letterSpacing: 0,
    fontWeight: FontWeight.w400,
    height: 1.5,
  );

  static const TextStyle body = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 14,
    letterSpacing: 0,
    fontWeight: FontWeight.w400,
    height: 1.5,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 13,
    letterSpacing: 0,
    fontWeight: FontWeight.w400,
    height: 1.4,
  );

  /// Small uppercase label. Apply the UPPERCASE transform at the call site
  /// (e.g. `label.toUpperCase()`); `letterSpacing` of 1.61 ≈ 0.14em at 11.5px.
  static const TextStyle meta = TextStyle(
    fontFamily: kInterFamily,
    fontSize: 11.5,
    letterSpacing: 1.61,
    fontWeight: FontWeight.w500,
    height: 1.2,
  );

  /// Monospace style for numerals/IDs/scores with tabular (fixed-width)
  /// figures so values line up in columns.
  static const TextStyle mono = TextStyle(
    fontFamily: kMonoFamily,
    fontSize: 13,
    letterSpacing: 0,
    fontWeight: FontWeight.w400,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}
