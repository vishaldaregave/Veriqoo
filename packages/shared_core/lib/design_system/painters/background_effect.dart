import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_tokens.dart';

/// Shared plumbing for the eight VERIQOO background effects.
///
/// Every background is a strictly monochrome, low-opacity decoration that sits
/// BELOW page content. This base owns the three pause rules the design system
/// requires, so individual effects only describe how they paint:
///
/// * **Disabled** — when [enabled] is false the loop is stopped and held at its
///   static end state (`progress == 1`).
/// * **Offscreen** — the driving [AnimationController] is a ticker, so Flutter's
///   [TickerMode] automatically mutes it when the subtree is offscreen (e.g. a
///   covered route); no frames are scheduled while muted.
/// * **Reduced motion** — when the platform reduce-motion flag is set
///   ([VeriqooMotion.reduceMotion]) the loop is stopped at its end state.
///
/// Repaint is throttled by quantizing the animation value into
/// [BackgroundEffectState.repaintSteps] discrete steps: the host rebuilds each
/// tick, but the painter's `shouldRepaint` only returns true when the quantized
/// progress actually changes, so long loops repaint at a fraction of the
/// display refresh rate.
abstract class BackgroundEffect extends StatefulWidget {
  const BackgroundEffect({
    super.key,
    this.enabled = true,
    this.color,
  });

  /// When false the effect is held at its static end state and never animates.
  final bool enabled;

  /// Optional override for the monochrome stroke color. When null the effect
  /// resolves [VeriqooTokens.textPrimary] from the ambient theme.
  final Color? color;
}

/// State base that drives a looping, pausable animation for a [BackgroundEffect].
///
/// Subclasses provide the loop [period] and build their [CustomPainter] via
/// [buildPainter]; everything else (pausing, reduced motion, throttling) is
/// handled here.
abstract class BackgroundEffectState<T extends BackgroundEffect> extends State<T>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  /// Loop duration for this effect.
  Duration get period;

  /// Number of discrete steps the loop is quantized into for repaint
  /// throttling. Lower values repaint less often.
  int get repaintSteps => 90;

  /// Builds the painter for the current quantized [progress] (0..1) using the
  /// resolved monochrome [color].
  CustomPainter buildPainter(double progress, Color color);

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: period);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _apply();
  }

  @override
  void didUpdateWidget(covariant T oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enabled != widget.enabled) {
      _apply();
    }
  }

  void _apply() {
    final shouldAnimate =
        widget.enabled && !VeriqooMotion.reduceMotion(context);
    if (shouldAnimate) {
      if (!_controller.isAnimating) {
        _controller.repeat();
      }
    } else {
      _controller.stop();
      _controller.value = 1; // static end state
    }
  }

  Color _resolveColor() {
    if (widget.color != null) {
      return widget.color!;
    }
    final tokens = Theme.of(context).extension<VeriqooTokens>();
    return tokens?.textPrimary ?? const Color(0xFFF5F5F2);
  }

  double get _quantizedProgress {
    final steps = repaintSteps;
    return (_controller.value * steps).round() / steps;
  }

  @override
  Widget build(BuildContext context) {
    final color = _resolveColor();
    return RepaintBoundary(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            size: Size.infinite,
            isComplex: true,
            willChange: _controller.isAnimating,
            painter: buildPainter(_quantizedProgress, color),
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}

/// Convenience base for the background painters: holds the quantized [progress]
/// and resolved [color], and implements a throttle-friendly `shouldRepaint`.
abstract class BackgroundPainter extends CustomPainter {
  const BackgroundPainter({required this.progress, required this.color});

  /// Quantized animation value in `[0, 1]`.
  final double progress;

  /// Monochrome stroke/fill color (opacity applied per-effect).
  final Color color;

  /// Paints the effect; opacity is kept low so it reads as a background.
  void paintEffect(Canvas canvas, Size size);

  @override
  void paint(Canvas canvas, Size size) => paintEffect(canvas, size);

  @override
  bool shouldRepaint(covariant BackgroundPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.color != color;
  }
}
