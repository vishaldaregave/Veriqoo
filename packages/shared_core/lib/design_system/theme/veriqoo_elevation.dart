import 'package:flutter/widgets.dart';

/// VERIQOO elevation tokens.
///
/// The system favors hairline borders over shadows. Exactly one soft-shadow
/// token exists, reserved for floating navigation and modals, plus one
/// restrained translucent-surface token used sparingly.
abstract final class VeriqooElevation {
  const VeriqooElevation._();

  /// The single permitted soft shadow — floating nav bar and modals only.
  static const List<BoxShadow> softShadow = [
    BoxShadow(
      color: Color(0x33000000), // black @ 20%
      blurRadius: 24,
      spreadRadius: 0,
      offset: Offset(0, 8),
    ),
  ];

  /// The single restrained translucent-surface token (scrims / subtle
  /// overlays). Use sparingly; no glassmorphism.
  static const Color translucentSurface = Color(0x990A0A0A); // deepBlack @ 60%
}
