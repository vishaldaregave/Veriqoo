import 'package:flutter/material.dart';

import '../theme/veriqoo_typography.dart';
import 'background_effect.dart';

/// Background effect: a technical HUD crosshair that drifts across the surface,
/// annotated with a live monospace X/Y coordinate read-out.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class TechnicalCoordinates extends BackgroundEffect {
  const TechnicalCoordinates({
    super.key,
    super.enabled,
    super.color,
  });

  @override
  State<TechnicalCoordinates> createState() => _TechnicalCoordinatesState();
}

class _TechnicalCoordinatesState
    extends BackgroundEffectState<TechnicalCoordinates> {
  @override
  Duration get period => const Duration(seconds: 10);

  @override
  int get repaintSteps => 160;

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _TechnicalCoordinatesPainter(progress: progress, color: color);
  }
}

class _TechnicalCoordinatesPainter extends BackgroundPainter {
  const _TechnicalCoordinatesPainter({
    required super.progress,
    required super.color,
  });

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    // A smooth Lissajous-style drift so the crosshair never jumps.
    final tx = 0.5 + 0.42 * _wave(progress);
    final ty = 0.5 + 0.42 * _wave((progress * 1.3 + 0.25) % 1.0);
    final point = Offset(tx * size.width, ty * size.height);

    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.07);

    // Full-bleed crosshair.
    canvas.drawLine(Offset(0, point.dy), Offset(size.width, point.dy), line);
    canvas.drawLine(Offset(point.dx, 0), Offset(point.dx, size.height), line);

    // Center marker.
    canvas.drawCircle(
      point,
      3,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = color.withValues(alpha: 0.12),
    );

    // Coordinate read-out near the crosshair.
    final label = 'X ${point.dx.toStringAsFixed(0).padLeft(4)}  '
        'Y ${point.dy.toStringAsFixed(0).padLeft(4)}';
    final tp = TextPainter(
      text: TextSpan(
        text: label,
        style: VeriqooType.mono.copyWith(
          color: color.withValues(alpha: 0.1),
          fontSize: 10,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();

    var dx = point.dx + 6;
    var dy = point.dy + 6;
    if (dx + tp.width > size.width) {
      dx = point.dx - 6 - tp.width;
    }
    if (dy + tp.height > size.height) {
      dy = point.dy - 6 - tp.height;
    }
    tp.paint(canvas, Offset(dx, dy));
  }

  /// Triangle wave in `[-1, 1]` for a continuous, loop-safe drift.
  double _wave(double t) => 1 - (4 * (t - 0.5).abs() - 1).abs();
}
