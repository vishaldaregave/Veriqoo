import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// The four verification outcomes. Each is encoded by a distinct SHAPE + GLYPH
/// + LABEL so meaning never depends on color (the system is monochrome).
enum VeriqooStatusKind {
  /// Solid filled square + check glyph + label "VERIFIED".
  verified,

  /// Diagonal-hatch outlined square + label "FLAG".
  flag,

  /// Dashed outlined square + label "NOT DETECTED".
  missing,

  /// Inverted high-contrast solid block + label "VIOLATION".
  violation,
}

extension VeriqooStatusKindLabel on VeriqooStatusKind {
  /// The uppercase label announced and rendered for this status.
  String get label {
    switch (this) {
      case VeriqooStatusKind.verified:
        return 'VERIFIED';
      case VeriqooStatusKind.flag:
        return 'FLAG';
      case VeriqooStatusKind.missing:
        return 'NOT DETECTED';
      case VeriqooStatusKind.violation:
        return 'VIOLATION';
    }
  }
}

/// A monochrome status chip: a shape glyph marker followed by its label.
///
/// Status is conveyed by shape + glyph + label only — never by color — so the
/// chip stays legible for color-blind users and in grayscale. The Semantics
/// label is the status word, so screen readers announce the outcome directly.
/// Radius is [none] (square, technical).
class VeriqooStatus extends StatelessWidget {
  const VeriqooStatus({
    super.key,
    required this.kind,
    this.markerSize = 16,
    this.showLabel = true,
  });

  /// Which of the four outcomes to render.
  final VeriqooStatusKind kind;

  /// Side length of the square marker.
  final double markerSize;

  /// When false only the marker is shown (label still exposed to Semantics).
  final bool showLabel;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Semantics(
      label: kind.label,
      container: true,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: markerSize,
              height: markerSize,
              child: CustomPaint(
                painter: _StatusMarkerPainter(
                  kind: kind,
                  color: tokens.textPrimary,
                  inverseBg: tokens.inverseBg,
                  inverseText: tokens.inverseText,
                ),
                child: kind == VeriqooStatusKind.verified
                    ? Center(
                        child: Icon(
                          VeriqooIcons.check,
                          size: markerSize * 0.7,
                          color: tokens.inverseText,
                        ),
                      )
                    : kind == VeriqooStatusKind.violation
                        ? Center(
                            child: Icon(
                              VeriqooIcons.close,
                              size: markerSize * 0.7,
                              color: tokens.inverseText,
                            ),
                          )
                        : null,
              ),
            ),
            if (showLabel) ...[
              const SizedBox(width: VeriqooSpacing.s8),
              Text(
                kind.label,
                style: VeriqooType.meta.copyWith(color: tokens.textPrimary),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Paints the square marker for each [VeriqooStatusKind]:
/// * verified  — solid filled square (check glyph layered on top).
/// * flag      — outlined square with diagonal hatching.
/// * missing   — dashed outlined square.
/// * violation — solid inverted block (close glyph layered on top).
class _StatusMarkerPainter extends CustomPainter {
  const _StatusMarkerPainter({
    required this.kind,
    required this.color,
    required this.inverseBg,
    required this.inverseText,
  });

  final VeriqooStatusKind kind;
  final Color color;
  final Color inverseBg;
  final Color inverseText;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    switch (kind) {
      case VeriqooStatusKind.verified:
        canvas.drawRect(rect, Paint()..color = color);
      case VeriqooStatusKind.flag:
        _drawOutline(canvas, rect);
        _drawHatch(canvas, rect);
      case VeriqooStatusKind.missing:
        _drawDashedOutline(canvas, rect);
      case VeriqooStatusKind.violation:
        canvas.drawRect(rect, Paint()..color = inverseBg);
    }
  }

  void _drawOutline(Canvas canvas, Rect rect) {
    canvas.drawRect(
      rect.deflate(0.5),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = color,
    );
  }

  void _drawHatch(Canvas canvas, Rect rect) {
    canvas.save();
    canvas.clipRect(rect);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color;
    const step = 3.5;
    for (double x = -rect.height; x < rect.width; x += step) {
      canvas.drawLine(
        Offset(rect.left + x, rect.bottom),
        Offset(rect.left + x + rect.height, rect.top),
        paint,
      );
    }
    canvas.restore();
  }

  void _drawDashedOutline(Canvas canvas, Rect rect) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color;
    final r = rect.deflate(0.5);
    const dash = 2.5;
    const gap = 2.0;
    _dashLine(canvas, r.topLeft, r.topRight, dash, gap, paint);
    _dashLine(canvas, r.topRight, r.bottomRight, dash, gap, paint);
    _dashLine(canvas, r.bottomRight, r.bottomLeft, dash, gap, paint);
    _dashLine(canvas, r.bottomLeft, r.topLeft, dash, gap, paint);
  }

  void _dashLine(
    Canvas canvas,
    Offset a,
    Offset b,
    double dash,
    double gap,
    Paint paint,
  ) {
    final total = (b - a).distance;
    if (total == 0) return;
    final dir = (b - a) / total;
    double drawn = 0;
    while (drawn < total) {
      final start = a + dir * drawn;
      final end = a + dir * (drawn + dash).clamp(0, total).toDouble();
      canvas.drawLine(start, end, paint);
      drawn += dash + gap;
    }
  }

  @override
  bool shouldRepaint(covariant _StatusMarkerPainter oldDelegate) {
    return oldDelegate.kind != kind ||
        oldDelegate.color != color ||
        oldDelegate.inverseBg != inverseBg;
  }
}
