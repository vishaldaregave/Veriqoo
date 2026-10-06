import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: a single thin horizontal line that sweeps top to bottom,
/// trailing a faint fade — the ambient version of the verification sweep.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class ScanningLine extends BackgroundEffect {
  const ScanningLine({
    super.key,
    super.enabled,
    super.color,
  });

  @override
  State<ScanningLine> createState() => _ScanningLineState();
}

class _ScanningLineState extends BackgroundEffectState<ScanningLine> {
  @override
  Duration get period => const Duration(milliseconds: 3600);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _ScanningLinePainter(progress: progress, color: color);
  }
}

class _ScanningLinePainter extends BackgroundPainter {
  const _ScanningLinePainter({required super.progress, required super.color});

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    final y = progress * size.height;

    // Faint trailing lines above the leading edge (manual falloff, no shader).
    const trail = 5;
    const spacing = 7.0;
    final trailPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (var i = trail; i >= 1; i--) {
      final ty = y - i * spacing;
      if (ty < 0) {
        continue;
      }
      trailPaint.color = color.withValues(alpha: 0.03 * (trail - i + 1) / trail);
      canvas.drawLine(Offset(0, ty), Offset(size.width, ty), trailPaint);
    }

    // Leading edge: a crisp hairline.
    final edge = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = color.withValues(alpha: 0.12);
    canvas.drawLine(Offset(0, y), Offset(size.width, y), edge);
  }
}
