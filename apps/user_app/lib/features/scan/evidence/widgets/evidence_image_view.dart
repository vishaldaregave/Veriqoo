import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/widgets/detection_boxes.dart';

/// Key for the pan/zoom surface so tests can read its transform.
const Key kEvidenceInteractiveViewerKey = Key('evidence-interactive-viewer');

/// A single evidence image inside an [InteractiveViewer], with the DERIVED
/// live-detection boxes and an optional focus highlight painted ON TOP of the
/// image so they pan/zoom together.
///
/// The bytes are decoded via `XFile.readAsBytes()` (in-memory in tests, so no
/// filesystem or camera is touched) and shown with [Image.memory]; a
/// [VeriqooLoading] fills the frame while decoding.
///
/// [focusRect] (normalized `0..1`) drives a reduced-motion-aware zoom: when it
/// changes the view animates ([VeriqooMotion.base]) toward the region, or jumps
/// instantly under reduce-motion. The highlight itself is static.
class EvidenceImageView extends StatefulWidget {
  const EvidenceImageView({
    super.key,
    required this.image,
    this.detectedFields = const <DetectedField>[],
    this.focusRect,
  });

  /// The evidence image to render.
  final EvidenceImage image;

  /// DERIVED live-detection regions painted over the image.
  final List<DetectedField> detectedFields;

  /// Optional normalized region to zoom toward and highlight.
  final Rect? focusRect;

  @override
  State<EvidenceImageView> createState() => EvidenceImageViewState();
}

/// Public so tests/host can call [animateToRect] directly if needed.
class EvidenceImageViewState extends State<EvidenceImageView>
    with SingleTickerProviderStateMixin {
  final TransformationController _controller = TransformationController();
  late final AnimationController _anim;
  Matrix4Tween _tween = Matrix4Tween(
    begin: Matrix4.identity(),
    end: Matrix4.identity(),
  );
  Size? _childSize;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(vsync: this, duration: VeriqooMotion.base)
      ..addListener(() => _controller.value = _tween.evaluate(_anim));
    // Apply the initial focus once the first layout has sized the view.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        animateToRect(widget.focusRect);
      }
    });
  }

  @override
  void didUpdateWidget(covariant EvidenceImageView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.focusRect != widget.focusRect) {
      animateToRect(widget.focusRect);
    }
  }

  @override
  void dispose() {
    _anim.dispose();
    _controller.dispose();
    super.dispose();
  }

  /// Zooms/pans the view toward [normalized] (null resets to identity).
  ///
  /// Jumps instantly under reduced motion; otherwise eases over
  /// [VeriqooMotion.base]. Safe to call before layout — it no-ops until a size
  /// is known (the post-frame callback re-applies the initial focus).
  void animateToRect(Rect? normalized) {
    final size = _childSize;
    if (size == null || size.isEmpty || !size.isFinite) {
      return;
    }
    final target = (normalized == null || normalized.isEmpty)
        ? Matrix4.identity()
        : _matrixForRect(normalized, size);

    if (VeriqooMotion.reduceMotion(context)) {
      _anim.stop();
      _controller.value = target;
      return;
    }
    _tween = Matrix4Tween(begin: _controller.value, end: target);
    _anim
      ..stop()
      ..forward(from: 0);
  }

  /// Builds a transform that frames [normalized] (with context padding) in the
  /// center of a [size]-sized viewport. Scale is clamped to `[1, 4]`.
  Matrix4 _matrixForRect(Rect normalized, Size size) {
    final rectPx = Rect.fromLTRB(
      normalized.left * size.width,
      normalized.top * size.height,
      normalized.right * size.width,
      normalized.bottom * size.height,
    );
    if (rectPx.isEmpty) {
      return Matrix4.identity();
    }
    final padded = rectPx.inflate(rectPx.longestSide * 0.6 + 16);
    final scaleX = size.width / padded.width;
    final scaleY = size.height / padded.height;
    final scale = (scaleX < scaleY ? scaleX : scaleY).clamp(1.0, 4.0).toDouble();
    final center = padded.center;
    final tx = size.width / 2 - scale * center.dx;
    final ty = size.height / 2 - scale * center.dy;
    // Compose T * S (viewportPoint = scale * scenePoint + translation) using
    // the non-deprecated Matrix4 API.
    return Matrix4.translationValues(tx, ty, 0)
      ..multiply(Matrix4.diagonal3Values(scale, scale, 1));
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return LayoutBuilder(
      builder: (context, constraints) {
        _childSize = Size(constraints.maxWidth, constraints.maxHeight);
        return InteractiveViewer(
          key: kEvidenceInteractiveViewerKey,
          transformationController: _controller,
          minScale: 0.5,
          maxScale: 5,
          boundaryMargin: const EdgeInsets.all(double.infinity),
          clipBehavior: Clip.hardEdge,
          child: SizedBox(
            width: constraints.maxWidth,
            height: constraints.maxHeight,
            child: Stack(
              fit: StackFit.expand,
              children: [
                ColoredBox(color: tokens.bgTrue),
                FutureBuilder<Uint8List>(
                  future: widget.image.file.readAsBytes(),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState != ConnectionState.done) {
                      return const Center(child: VeriqooLoading(message: ''));
                    }
                    final bytes = snapshot.data;
                    if (bytes == null || bytes.isEmpty) {
                      return Center(
                        child: Icon(
                          VeriqooIcons.scan,
                          size: 40,
                          color: tokens.textTertiary,
                        ),
                      );
                    }
                    return Image.memory(
                      bytes,
                      fit: BoxFit.contain,
                      gaplessPlayback: true,
                    );
                  },
                ),
                // DERIVED live-detection regions.
                DetectionBoxesOverlay(fields: widget.detectedFields),
                // Optional focus highlight.
                if (widget.focusRect != null)
                  IgnorePointer(
                    child: CustomPaint(
                      size: Size.infinite,
                      painter: _FocusHighlightPainter(
                        rect: widget.focusRect!,
                        color: tokens.textPrimary,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Paints a brighter 1.5px highlight (with corner emphasis) around the focused
/// normalized region — visually distinct from the thin DERIVED detection boxes.
class _FocusHighlightPainter extends CustomPainter {
  const _FocusHighlightPainter({required this.rect, required this.color});

  final Rect rect;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty || rect.isEmpty) {
      return;
    }
    final r = Rect.fromLTRB(
      rect.left * size.width,
      rect.top * size.height,
      rect.right * size.width,
      rect.bottom * size.height,
    );

    // Dim the surrounding area so the focus region stands out.
    final scrim = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addRect(r);
    canvas.drawPath(scrim, Paint()..color = color.withValues(alpha: 0.04));

    final box = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = color;
    canvas.drawRect(r, box);

    // Corner ticks.
    final tick = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = color;
    const l = 8.0;
    canvas.drawLine(r.topLeft, r.topLeft.translate(l, 0), tick);
    canvas.drawLine(r.topLeft, r.topLeft.translate(0, l), tick);
    canvas.drawLine(r.topRight, r.topRight.translate(-l, 0), tick);
    canvas.drawLine(r.topRight, r.topRight.translate(0, l), tick);
    canvas.drawLine(r.bottomLeft, r.bottomLeft.translate(l, 0), tick);
    canvas.drawLine(r.bottomLeft, r.bottomLeft.translate(0, -l), tick);
    canvas.drawLine(r.bottomRight, r.bottomRight.translate(-l, 0), tick);
    canvas.drawLine(r.bottomRight, r.bottomRight.translate(0, -l), tick);
  }

  @override
  bool shouldRepaint(covariant _FocusHighlightPainter oldDelegate) {
    return oldDelegate.rect != rect || oldDelegate.color != color;
  }
}
