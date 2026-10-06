import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: scattered OCR detection boxes with small corner ticks
/// that fade in and out in a staggered rhythm, suggesting fields being read.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class OCROverlay extends BackgroundEffect {
  const OCROverlay({
    super.key,
    super.enabled,
    super.color,
  });

  @override
  State<OCROverlay> createState() => _OCROverlayState();
}

class _OCROverlayState extends BackgroundEffectState<OCROverlay> {
  @override
  Duration get period => const Duration(seconds: 6);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _OCROverlayPainter(progress: progress, color: color);
  }
}

class _OCROverlayPainter extends BackgroundPainter {
  const _OCROverlayPainter({required super.progress, required super.color});

  // Normalized field boxes (left, top, width, height) in 0..1 space.
  static const List<Rect> _boxes = [
    Rect.fromLTWH(0.08, 0.12, 0.34, 0.06),
    Rect.fromLTWH(0.55, 0.22, 0.30, 0.05),
    Rect.fromLTWH(0.12, 0.44, 0.42, 0.06),
    Rect.fromLTWH(0.58, 0.58, 0.28, 0.05),
    Rect.fromLTWH(0.10, 0.74, 0.36, 0.06),
    Rect.fromLTWH(0.52, 0.84, 0.34, 0.05),
  ];

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    for (var i = 0; i < _boxes.length; i++) {
      // Each box pulses on its own phase.
      final phase = (progress + i / _boxes.length) % 1.0;
      final pulse = math.sin(phase * math.pi); // 0 -> 1 -> 0
      final alpha = 0.03 + 0.09 * pulse;

      final n = _boxes[i];
      final rect = Rect.fromLTWH(
        n.left * size.width,
        n.top * size.height,
        n.width * size.width,
        n.height * size.height,
      );

      stroke.color = color.withValues(alpha: alpha);
      canvas.drawRect(rect, stroke);
      _drawCornerTicks(canvas, rect, stroke);
    }
  }

  void _drawCornerTicks(Canvas canvas, Rect rect, Paint paint) {
    const t = 4.0;
    // Top-left
    canvas.drawLine(rect.topLeft, rect.topLeft.translate(t, 0), paint);
    canvas.drawLine(rect.topLeft, rect.topLeft.translate(0, t), paint);
    // Bottom-right
    canvas.drawLine(rect.bottomRight, rect.bottomRight.translate(-t, 0), paint);
    canvas.drawLine(rect.bottomRight, rect.bottomRight.translate(0, -t), paint);
  }
}
