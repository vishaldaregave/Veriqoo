import 'package:flutter/material.dart';

import '../theme/veriqoo_typography.dart';
import 'background_effect.dart';

/// Background effect: a slow vertical ticker of tiny monospace status strings
/// ("OCR 98.2%", "FIELD DETECTED", "VERIFYING", "DECLARATION FOUND") drifting
/// upward, like a diagnostic read-out behind the content.
///
/// Monochrome, low opacity, and pausable — see [BackgroundEffect].
class DataTicker extends BackgroundEffect {
  const DataTicker({
    super.key,
    super.enabled,
    super.color,
  });

  /// The repeating sequence of labels, in order.
  static const List<String> labels = <String>[
    'OCR 98.2%',
    'FIELD DETECTED',
    'VERIFYING',
    'DECLARATION FOUND',
  ];

  @override
  State<DataTicker> createState() => _DataTickerState();
}

class _DataTickerState extends BackgroundEffectState<DataTicker> {
  @override
  Duration get period => const Duration(seconds: 12);

  @override
  int get repaintSteps => 120;

  @override
  CustomPainter buildPainter(double progress, Color color) {
    return _DataTickerPainter(progress: progress, color: color);
  }
}

class _DataTickerPainter extends BackgroundPainter {
  const _DataTickerPainter({required super.progress, required super.color});

  static const double _rowHeight = 28;

  @override
  void paintEffect(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }

    final labels = DataTicker.labels;
    final rows = (size.height / _rowHeight).ceil() + 2;
    // Continuous upward scroll offset over one label cycle.
    final offset = progress * _rowHeight * labels.length;

    for (var i = -1; i < rows; i++) {
      final y = size.height - (i * _rowHeight) + (offset % (_rowHeight)) -
          _rowHeight;
      final labelIndex =
          ((offset / _rowHeight).floor() + i) % labels.length;
      final text = labels[(labelIndex + labels.length) % labels.length];

      final tp = TextPainter(
        text: TextSpan(
          text: text,
          style: VeriqooType.mono.copyWith(
            color: color.withValues(alpha: 0.06),
            fontSize: 11,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(12, y));
    }
  }
}
