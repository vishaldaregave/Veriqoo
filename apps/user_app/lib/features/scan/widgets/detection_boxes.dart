import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/model/detected_field.dart';

/// Paints thin (1px) hairline rectangles for live-detected label regions, each
/// with a tiny 9px letter-spaced field label above it — matching the
/// `VerificationScan` box styling (NOT a thick generic rectangle).
class DetectionBoxesPainter extends CustomPainter {
  const DetectionBoxesPainter({
    required this.fields,
    required this.color,
  });

  final List<DetectedField> fields;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty || fields.isEmpty) {
      return;
    }

    final box = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.7);

    final tick = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.9);

    for (final field in fields) {
      final n = field.rectNormalized;
      final rect = Rect.fromLTRB(
        n.left * size.width,
        n.top * size.height,
        n.right * size.width,
        n.bottom * size.height,
      );
      if (rect.width <= 0 || rect.height <= 0) {
        continue;
      }
      canvas.drawRect(rect, box);

      // Leading corner ticks for a "detected" feel.
      const l = 5.0;
      canvas.drawLine(rect.topLeft, rect.topLeft.translate(l, 0), tick);
      canvas.drawLine(rect.topLeft, rect.topLeft.translate(0, l), tick);
      canvas.drawLine(
          rect.bottomRight, rect.bottomRight.translate(-l, 0), tick);
      canvas.drawLine(
          rect.bottomRight, rect.bottomRight.translate(0, -l), tick);

      final tp = TextPainter(
        text: TextSpan(
          text: field.label,
          style: VeriqooType.meta.copyWith(
            color: color.withValues(alpha: 0.9),
            fontSize: 9,
            letterSpacing: 1.2,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      // Label above the box; clamp so it stays on-canvas near the top edge.
      final labelY = rect.top - tp.height - 2;
      tp.paint(canvas, Offset(rect.left, labelY < 0 ? rect.top + 2 : labelY));
    }
  }

  @override
  bool shouldRepaint(covariant DetectionBoxesPainter oldDelegate) {
    return oldDelegate.fields != fields || oldDelegate.color != color;
  }
}

/// Renders the live [DetectedField] boxes over the camera preview. Static (no
/// animation) so it is inherently reduced-motion safe.
class DetectionBoxesOverlay extends StatelessWidget {
  const DetectionBoxesOverlay({super.key, required this.fields});

  final List<DetectedField> fields;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return IgnorePointer(
      child: CustomPaint(
        size: Size.infinite,
        painter: DetectionBoxesPainter(
          fields: fields,
          color: tokens.textPrimary,
        ),
      ),
    );
  }
}
