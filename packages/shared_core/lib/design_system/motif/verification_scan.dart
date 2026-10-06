import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A single OCR field target for [VerificationScan]: a [rect] in normalized
/// `0..1` coordinates plus an optional tiny [label].
@immutable
class ScanField {
  const ScanField(this.rect, {this.label});

  /// Field bounds in normalized `0..1` space (resolved against the paint size).
  final Rect rect;

  /// Optional short label rendered beneath the box as it locks in.
  final String? label;
}

/// The VERIQOO signature verification-scan motif.
///
/// A 1–2px luminous hairline sweeps down across structured product data, four
/// corner markers "lock" into place, and the OCR field boxes fade in one after
/// another with a ~40ms stagger. It is the shared basis for `VeriqooLoading`
/// and `VeriqooScannerOverlay`.
///
/// ## Reduced motion
/// When the platform reduce-motion flag is set (via
/// [VeriqooMotion.reduceMotion]) — or when [enabled] is false — the motif
/// renders its final locked state directly: corners locked, every field box
/// visible, and no sweeping line. No animation frames are scheduled.
///
/// The [child] (e.g. a camera preview or data panel) is painted beneath the
/// scan overlay.
class VerificationScan extends StatefulWidget {
  const VerificationScan({
    super.key,
    this.child,
    this.fields = defaultFields,
    this.enabled = true,
    this.loop = true,
    this.duration = const Duration(milliseconds: 1600),
    this.stagger = const Duration(milliseconds: 40),
    this.color,
    this.cornerLength = 18,
    this.sweepThickness = 1.5,
  });

  /// Content painted beneath the scan overlay (optional).
  final Widget? child;

  /// OCR field targets, in normalized coordinates.
  final List<ScanField> fields;

  /// When false the motif holds its static locked end state and never animates.
  final bool enabled;

  /// Whether the scan repeats. When false it plays once and holds the locked
  /// end state.
  final bool loop;

  /// Duration of one full scan pass.
  final Duration duration;

  /// Per-box fade-in stagger (~40ms by spec).
  final Duration stagger;

  /// Optional override for the monochrome scan color. Defaults to the ambient
  /// [VeriqooTokens.textPrimary].
  final Color? color;

  /// Length of each corner-marker arm in logical pixels.
  final double cornerLength;

  /// Thickness of the sweeping hairline (1–2px).
  final double sweepThickness;

  /// Default field layout approximating a product declaration panel.
  static const List<ScanField> defaultFields = <ScanField>[
    ScanField(Rect.fromLTWH(0.12, 0.16, 0.52, 0.08), label: 'PRODUCT'),
    ScanField(Rect.fromLTWH(0.12, 0.34, 0.34, 0.07), label: 'MRP'),
    ScanField(Rect.fromLTWH(0.54, 0.34, 0.30, 0.07), label: 'NET QTY'),
    ScanField(Rect.fromLTWH(0.12, 0.52, 0.72, 0.07), label: 'MANUFACTURER'),
    ScanField(Rect.fromLTWH(0.12, 0.70, 0.44, 0.07), label: 'MFG DATE'),
  ];

  @override
  State<VerificationScan> createState() => _VerificationScanState();
}

class _VerificationScanState extends State<VerificationScan>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    // Extend the pass so every staggered box still finishes within the loop.
    final tail = widget.stagger * widget.fields.length;
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration + tail,
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _apply();
  }

  @override
  void didUpdateWidget(covariant VerificationScan oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enabled != widget.enabled || oldWidget.loop != widget.loop) {
      _apply();
    }
  }

  void _apply() {
    final animate = widget.enabled && !VeriqooMotion.reduceMotion(context);
    if (!animate) {
      _controller.stop();
      _controller.value = 1; // static locked end state
      return;
    }
    if (widget.loop) {
      if (!_controller.isAnimating) {
        _controller.repeat();
      }
    } else {
      _controller.forward(from: 0);
    }
  }

  Color _resolveColor() {
    if (widget.color != null) {
      return widget.color!;
    }
    final tokens = Theme.of(context).extension<VeriqooTokens>();
    return tokens?.textPrimary ?? const Color(0xFFF5F5F2);
  }

  @override
  Widget build(BuildContext context) {
    final color = _resolveColor();
    final totalMs = _controller.duration!.inMilliseconds;
    final staggerFraction =
        totalMs == 0 ? 0.0 : widget.stagger.inMilliseconds / totalMs;

    final overlay = RepaintBoundary(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            size: Size.infinite,
            willChange: _controller.isAnimating,
            painter: VerificationScanPainter(
              progress: _controller.value,
              color: color,
              fields: widget.fields,
              staggerFraction: staggerFraction,
              cornerLength: widget.cornerLength,
              sweepThickness: widget.sweepThickness,
            ),
          );
        },
      ),
    );

    if (widget.child == null) {
      return overlay;
    }
    return Stack(
      fit: StackFit.passthrough,
      children: [
        widget.child!,
        Positioned.fill(child: overlay),
      ],
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}

/// Paints the verification-scan motif at a given [progress] in `[0, 1]`.
///
/// Timeline (fractions of [progress]):
/// * `0.00 – 0.60`: hairline sweeps top → bottom.
/// * `0.45 – 0.75`: corner markers lock inward to full opacity.
/// * `0.50 → …`: field boxes fade in, each offset by [staggerFraction].
class VerificationScanPainter extends CustomPainter {
  const VerificationScanPainter({
    required this.progress,
    required this.color,
    required this.fields,
    required this.staggerFraction,
    required this.cornerLength,
    required this.sweepThickness,
  });

  final double progress;
  final Color color;
  final List<ScanField> fields;
  final double staggerFraction;
  final double cornerLength;
  final double sweepThickness;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) {
      return;
    }
    _paintCorners(canvas, size);
    _paintFields(canvas, size);
    _paintSweep(canvas, size);
  }

  void _paintCorners(Canvas canvas, Size size) {
    final t = _interval(progress, 0.45, 0.75);
    final inset = (1 - t) * 10; // start pushed out, lock inward
    final alpha = 0.25 + 0.55 * t;
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.square
      ..color = color.withValues(alpha: alpha);

    final rect = Rect.fromLTRB(
      inset,
      inset,
      size.width - inset,
      size.height - inset,
    );
    final arm = cornerLength;

    // Top-left
    canvas.drawLine(rect.topLeft, rect.topLeft.translate(arm, 0), paint);
    canvas.drawLine(rect.topLeft, rect.topLeft.translate(0, arm), paint);
    // Top-right
    canvas.drawLine(rect.topRight, rect.topRight.translate(-arm, 0), paint);
    canvas.drawLine(rect.topRight, rect.topRight.translate(0, arm), paint);
    // Bottom-left
    canvas.drawLine(rect.bottomLeft, rect.bottomLeft.translate(arm, 0), paint);
    canvas.drawLine(rect.bottomLeft, rect.bottomLeft.translate(0, -arm), paint);
    // Bottom-right
    canvas.drawLine(
        rect.bottomRight, rect.bottomRight.translate(-arm, 0), paint);
    canvas.drawLine(
        rect.bottomRight, rect.bottomRight.translate(0, -arm), paint);
  }

  void _paintFields(Canvas canvas, Size size) {
    final box = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    for (var i = 0; i < fields.length; i++) {
      final start = 0.5 + i * staggerFraction;
      final a = _interval(progress, start, (start + 0.18).clamp(0.0, 1.0));
      if (a <= 0) {
        continue;
      }

      final n = fields[i].rect;
      final rect = Rect.fromLTWH(
        n.left * size.width,
        n.top * size.height,
        n.width * size.width,
        n.height * size.height,
      );

      box.color = color.withValues(alpha: 0.55 * a);
      canvas.drawRect(rect, box);

      // Leading corner ticks for a "detected" feel.
      final tick = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = color.withValues(alpha: 0.8 * a);
      const l = 5.0;
      canvas.drawLine(rect.topLeft, rect.topLeft.translate(l, 0), tick);
      canvas.drawLine(rect.topLeft, rect.topLeft.translate(0, l), tick);
      canvas.drawLine(
          rect.bottomRight, rect.bottomRight.translate(-l, 0), tick);
      canvas.drawLine(
          rect.bottomRight, rect.bottomRight.translate(0, -l), tick);

      final label = fields[i].label;
      if (label != null) {
        final tp = TextPainter(
          text: TextSpan(
            text: label,
            style: VeriqooType.meta.copyWith(
              color: color.withValues(alpha: 0.7 * a),
              fontSize: 9,
              letterSpacing: 1.2,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(rect.left, rect.bottom + 2));
      }
    }
  }

  void _paintSweep(Canvas canvas, Size size) {
    // Visible only during the sweep window; fade the tail out.
    if (progress >= 0.62) {
      return;
    }
    final t = _interval(progress, 0.0, 0.6);
    final y = t * size.height;
    final fade = progress > 0.5 ? _interval(0.62 - progress, 0.0, 0.12) : 1.0;

    // Soft glow underlay via a blur (not a gradient shader).
    final glow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = sweepThickness + 4
      ..color = color.withValues(alpha: 0.10 * fade)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
    canvas.drawLine(Offset(0, y), Offset(size.width, y), glow);

    // Crisp luminous hairline.
    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = sweepThickness
      ..color = color.withValues(alpha: 0.85 * fade);
    canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
  }

  /// Normalized progress of [value] across `[start, end]`, clamped to `[0, 1]`.
  double _interval(double value, double start, double end) {
    if (end <= start) {
      return value >= end ? 1 : 0;
    }
    return ((value - start) / (end - start)).clamp(0.0, 1.0);
  }

  @override
  bool shouldRepaint(covariant VerificationScanPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.color != color ||
        oldDelegate.fields != fields;
  }
}
