import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A monochrome radial score dial.
///
/// Draws a hairline track with a stronger progress arc proportional to
/// `value / maxValue`, and counts the numeric readout up from zero to [value]
/// on first build. Honors reduced motion by jumping straight to the final
/// value. The readout uses the mono tabular style (e.g. `87/100`).
class VeriqooScore extends StatefulWidget {
  const VeriqooScore({
    super.key,
    required this.value,
    this.maxValue = 100,
    this.size = 120,
    this.strokeWidth = 6,
    this.duration = VeriqooMotion.cinematic,
    this.caption,
  });

  /// Target score to display and animate toward.
  final int value;

  /// Denominator (default 100).
  final int maxValue;

  /// Diameter of the dial.
  final double size;

  /// Ring thickness.
  final double strokeWidth;

  /// Count-up duration (ignored under reduced motion).
  final Duration duration;

  /// Optional small caption beneath the readout (e.g. "SCORE").
  final String? caption;

  @override
  State<VeriqooScore> createState() => _VeriqooScoreState();
}

class _VeriqooScoreState extends State<VeriqooScore>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration);
    _animation = CurvedAnimation(parent: _controller, curve: VeriqooMotion.enter);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _start();
  }

  @override
  void didUpdateWidget(covariant VeriqooScore oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value) {
      _start();
    }
  }

  void _start() {
    if (VeriqooMotion.reduceMotion(context)) {
      _controller.value = 1;
    } else {
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final fraction = widget.maxValue == 0
        ? 0.0
        : (widget.value / widget.maxValue).clamp(0.0, 1.0);

    return Semantics(
      label: 'Score ${widget.value} out of ${widget.maxValue}',
      child: ExcludeSemantics(
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: AnimatedBuilder(
            animation: _animation,
            builder: (context, _) {
              final t = _animation.value;
              final current = (widget.value * t).round();
              return CustomPaint(
                painter: _ScoreRingPainter(
                  progress: fraction * t,
                  trackColor: tokens.borderHairline,
                  arcColor: tokens.textPrimary,
                  strokeWidth: widget.strokeWidth,
                ),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      RichText(
                        text: TextSpan(
                          children: [
                            TextSpan(
                              text: '$current',
                              style: VeriqooType.mono.copyWith(
                                color: tokens.textPrimary,
                                fontSize: widget.size * 0.26,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            TextSpan(
                              text: '/${widget.maxValue}',
                              style: VeriqooType.mono.copyWith(
                                color: tokens.textSecondary,
                                fontSize: widget.size * 0.13,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (widget.caption != null)
                        Text(
                          widget.caption!.toUpperCase(),
                          style: VeriqooType.meta.copyWith(
                            color: tokens.textSecondary,
                            fontSize: 9,
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _ScoreRingPainter extends CustomPainter {
  const _ScoreRingPainter({
    required this.progress,
    required this.trackColor,
    required this.arcColor,
    required this.strokeWidth,
  });

  final double progress;
  final Color trackColor;
  final Color arcColor;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (math.min(size.width, size.height) - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..color = trackColor;
    canvas.drawCircle(center, radius, track);

    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = arcColor;
    const start = -math.pi / 2;
    canvas.drawArc(rect, start, 2 * math.pi * progress, false, arc);
  }

  @override
  bool shouldRepaint(covariant _ScoreRingPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.arcColor != arcColor ||
        oldDelegate.trackColor != trackColor;
  }
}
