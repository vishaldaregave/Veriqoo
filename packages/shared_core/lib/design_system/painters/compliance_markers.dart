import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: a sparse field of small square compliance markers that
/// "check in" one after another with a brief tick, then settle.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class ComplianceMarkers extends BackgroundEffect {
  const ComplianceMarkers({
    super.key,
    super.enabled,
    super.color,
    this.spacing = 72,
  });

  /// Distance between markers in logical pixels.
  final double spacing;

  @override
  State<ComplianceMarkers> createState() => _ComplianceMarkersState();
}

class _ComplianceMarkersState extends BackgroundEffectState<ComplianceMarkers> {
  @override
  Duration get period => const Duration(seconds: 9);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _ComplianceMarkersPainter(
      progress: progress,
      color: color,
      spacing: widget.spacing,
    );
  }
}

class _ComplianceMarkersPainter extends BackgroundPainter {
  const _ComplianceMarkersPainter({
    required super.progress,
    required super.color,
    required this.spacing,
  });

  final double spacing;

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty || spacing <= 0) {
      return;
    }

    const markerSize = 7.0;
    final cols = (size.width / spacing).ceil() + 1;
    final rowCount = (size.height / spacing).ceil() + 1;
    final total = cols * rowCount;
    if (total <= 0) {
      return;
    }

    final box = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final tick = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..strokeCap = StrokeCap.round;

    for (var r = 0; r < rowCount; r++) {
      for (var c = 0; c < cols; c++) {
        final index = r * cols + c;
        // Each marker's check-in phase, staggered across the field.
        final phase = (progress - index / total) % 1.0;
        final checked = phase >= 0 && phase < 0.5;

        final origin = Offset(
          c * spacing + spacing / 2,
          r * spacing + spacing / 2,
        );
        final rect = Rect.fromCenter(
          center: origin,
          width: markerSize,
          height: markerSize,
        );

        box.color = color.withValues(alpha: 0.06);
        canvas.drawRect(rect, box);

        if (checked) {
          final k = (phase / 0.5).clamp(0.0, 1.0);
          tick.color = color.withValues(alpha: 0.12 * k);
          // A tiny check mark inside the marker.
          final p1 = rect.centerLeft.translate(1.5, 0.5);
          final mid = rect.bottomCenter.translate(-0.5, -1.5);
          final p3 = rect.topRight.translate(-1, 1.5);
          canvas.drawLine(p1, mid, tick);
          canvas.drawLine(mid, p3, tick);
        }
      }
    }
  }
}
