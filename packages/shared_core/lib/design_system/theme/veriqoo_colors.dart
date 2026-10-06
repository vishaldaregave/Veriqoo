import 'package:flutter/widgets.dart';

/// VERIQOO primitive color ramp.
///
/// A strictly monochrome scale — no green, no accent hues anywhere. Semantic
/// tokens ([VeriqooTokens]) are composed exclusively from these primitives;
/// widgets should read semantic tokens from the theme rather than referencing
/// this ramp directly.
abstract final class VeriqooColors {
  const VeriqooColors._();

  static const Color black = Color(0xFF000000);
  static const Color deepBlack = Color(0xFF0A0A0A);
  static const Color charcoal = Color(0xFF111111);
  static const Color graphite = Color(0xFF181818);
  static const Color borderStrongDark = Color(0xFF2A2A2A);
  static const Color midGrey = Color(0xFF5E5E5E);
  static const Color lightGrey = Color(0xFFA0A0A0);
  static const Color borderGrey = Color(0xFFD5D5D5);
  static const Color offWhite = Color(0xFFF5F5F2);
  static const Color white = Color(0xFFFFFFFF);
}
