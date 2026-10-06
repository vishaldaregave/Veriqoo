import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: a stylized packaged-product outline (a labelled carton)
/// drawn in hairlines, with the outline tracing itself on, then holding.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class ProductOutline extends BackgroundEffect {
  const ProductOutline({
    super.key,
    super.enabled,
    super.color,
  });

  @override
  State<ProductOutline> createState() => _ProductOutlineState();
}

class _ProductOutlineState extends BackgroundEffectState<ProductOutline> {
  @override
  Duration get period => const Duration(seconds: 7);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _ProductOutlinePainter(progress: progress, color: color);
  }
}

class _ProductOutlinePainter extends BackgroundPainter {
  const _ProductOutlinePainter({required super.progress, required super.color});

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    // Center a carton roughly 46% of the smaller dimension.
    final unit = size.shortestSide * 0.46;
    final center = Offset(size.width / 2, size.height / 2);
    final body = Rect.fromCenter(
      center: center,
      width: unit * 0.72,
      height: unit,
    );

    final path = Path()..addRect(body);
    // A label band across the carton.
    final band = Rect.fromLTWH(
      body.left,
      body.top + body.height * 0.42,
      body.width,
      body.height * 0.22,
    );
    path.addRect(band);
    // Top flap seam.
    path.moveTo(body.left, body.top + body.height * 0.1);
    path.lineTo(body.right, body.top + body.height * 0.1);

    // Trace the outline on, then hold once drawn.
    final metrics = path.computeMetrics().toList();
    final drawFraction = Curves.easeInOutCubic.transform(
      (progress * 1.6).clamp(0.0, 1.0),
    );

    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round
      ..color = color.withValues(alpha: 0.08);

    for (final metric in metrics) {
      final length = metric.length * drawFraction;
      canvas.drawPath(metric.extractPath(0, length), stroke);
    }
  }
}
