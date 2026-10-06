import 'package:flutter/material.dart';

import 'background_effect.dart';

/// Background effect: a faint technical measurement grid with a highlight that
/// slowly traverses the columns, like a sheet being inspected.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class InspectionGrid extends BackgroundEffect {
  const InspectionGrid({
    super.key,
    super.enabled,
    super.color,
    this.cell = 32,
  });

  /// Grid cell size in logical pixels.
  final double cell;

  @override
  State<InspectionGrid> createState() => _InspectionGridState();
}

class _InspectionGridState extends BackgroundEffectState<InspectionGrid> {
  @override
  Duration get period => const Duration(seconds: 8);

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _InspectionGridPainter(
      progress: progress,
      color: color,
      cell: widget.cell,
    );
  }
}

class _InspectionGridPainter extends BackgroundPainter {
  const _InspectionGridPainter({
    required super.progress,
    required super.color,
    required this.cell,
  });

  final double cell;

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty || cell <= 0) {
      return;
    }

    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withValues(alpha: 0.05);

    for (double x = 0; x <= size.width; x += cell) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), line);
    }
    for (double y = 0; y <= size.height; y += cell) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }

    // A single column highlight that traverses left to right.
    final columns = (size.width / cell).ceil().clamp(1, 1 << 20);
    final activeColumn = (progress * columns).floor() % columns;
    final highlight = Paint()
      ..color = color.withValues(alpha: 0.07);
    canvas.drawRect(
      Rect.fromLTWH(activeColumn * cell, 0, cell, size.height),
      highlight,
    );
  }
}
