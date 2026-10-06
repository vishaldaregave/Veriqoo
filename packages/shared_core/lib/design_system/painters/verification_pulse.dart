import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: concentric hairline rings expanding from the center and
/// fading as they grow, like a verification ping.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class VerificationPulse extends BackgroundEffect {
  const VerificationPulse({
    super.key,
    super.enabled,
    super.color,
    this.rings = 3,
  });

  /// Number of simultaneous rings in flight.
  final int rings;

  @override
  State<VerificationPulse> createState() => _VerificationPulseState();
}

class _VerificationPulseState extends BackgroundEffectState<VerificationPulse> {
  @override
  Duration get period => const Duration(milliseconds: 4200);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _VerificationPulsePainter(
      progress: progress,
      color: color,
      rings: widget.rings,
    );
  }
}

class _VerificationPulsePainter extends BackgroundPainter {
  const _VerificationPulsePainter({
    required super.progress,
    required super.color,
    required this.rings,
  });

  final int rings;

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    final center = Offset(size.width / 2, size.height / 2);
    final maxRadius = size.shortestSide * 0.5;

    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    for (var i = 0; i < rings; i++) {
      final t = (progress + i / rings) % 1.0;
      final radius = t * maxRadius;
      final alpha = 0.12 * (1 - t); // fade as it expands
      if (radius <= 0 || alpha <= 0) {
        continue;
      }
      stroke.color = color.withValues(alpha: alpha);
      canvas.drawCircle(center, radius, stroke);
    }

    // A small fixed center dot.
    canvas.drawCircle(
      center,
      1.5,
      Paint()..color = color.withValues(alpha: 0.14),
    );
  }
}
