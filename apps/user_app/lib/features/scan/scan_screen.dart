import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/scan/camera/scan_camera_controller.dart';
import 'package:flutter_application_1/features/scan/camera/scan_gallery_picker.dart';
import 'package:flutter_application_1/features/scan/ocr/live_ocr_analyzer.dart';
import 'package:flutter_application_1/features/scan/scan_providers.dart';
import 'package:flutter_application_1/features/scan/widgets/detection_boxes.dart';

/// Screen 3: Multi-Photo Camera / Scanner Screen matching the mockup and workflow.
///
/// Features:
/// - Step-by-step multi-angle capture: Front (Brand/Net Qty), Back (MRP/Mfg/Packer), Side/Declarations
/// - Viewfinder with corner brackets and dynamic guidance banner
/// - Live horizontal thumbnail tray of captured sides with delete/retake affordance
/// - Prominent "Analyze (N Photos) ->" button
/// - Continuous shutter: keeps user in camera mode until they tap Analyze
class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({super.key});

  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen> {
  late final ScanCameraController _camera;
  ThrottledOcrRunner? _ocrRunner;
  bool _cameraReady = false;
  bool _flashOn = false;
  bool _busy = false;
  String _selectedMode = 'Label';

  final List<String> _modes = ['Auto', 'Label', 'Barcode', 'Manual'];

  @override
  void initState() {
    super.initState();
    _camera = ref.read(scanCameraControllerProvider)();
    _initCamera();
  }

  Future<void> _initCamera() async {
    await _camera.initialize();
    if (!mounted) return;
    if (_camera.supportsLiveOcr) {
      final analyzer = ref.read(scanLiveOcrAnalyzerProvider);
      _ocrRunner = ThrottledOcrRunner(analyze: analyzer.analyze);
      await _camera.startImageStream(_onFrame);
    }
    setState(() => _cameraReady = true);
  }

  void _onFrame(ScanCameraFrame frame) {
    final runner = _ocrRunner;
    if (runner == null || !mounted) return;
    runner.submit(frame).then((result) {
      if (!mounted || result == null) return;
      ref.read(scanStateProvider.notifier)
        ..setLiveOcr(result.rawText, result.fields)
        ..advancePhase();
    });
  }

  Future<void> _toggleFlash() async {
    final next = !_flashOn;
    await _camera.setFlash(next);
    if (!mounted) return;
    setState(() => _flashOn = next);
  }

  Future<void> _pickFromGallery() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final picked = await ref.read(scanGalleryPickerProvider).pick();
      if (picked == null || !mounted) return;

      ref.read(scanStateProvider.notifier)
        ..addEvidence(picked)
        ..advancePhase(capturing: true);

      final count = ref.read(scanStateProvider).evidence.length;
      final role = ref.read(scanStateProvider).evidence.last.label;

      messenger.clearSnackBars();
      messenger.showSnackBar(
        SnackBar(
          content: Text('Photo $count ($role) added. Add other sides or tap Analyze.'),
          duration: const Duration(milliseconds: 2000),
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xFF133E30),
        ),
      );
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Could not open gallery. Please try again.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Future<void> _capture() async {
    if (_busy) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);

    try {
      final file = await _camera.takePicture();
      if (!mounted) return;

      ref.read(scanStateProvider.notifier)
        ..addEvidence(file)
        ..advancePhase(capturing: true);

      final count = ref.read(scanStateProvider).evidence.length;
      final role = ref.read(scanStateProvider).evidence.last.label;

      messenger.clearSnackBars();
      messenger.showSnackBar(
        SnackBar(
          content: Text('Photo $count ($role) captured! Flip package to capture other sides.'),
          duration: const Duration(milliseconds: 2000),
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xFF133E30),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Could not capture photo. Please try again.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _proceedToProcessing() {
    final evidence = ref.read(scanStateProvider).evidence;
    if (evidence.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please capture at least one product label photo first.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    _camera.stopImageStream();
    context.push(AppRoutes.scanProcessingPath);
  }

  void _resetEvidence() {
    ref.read(scanStateProvider.notifier).reset();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Cleared captured photos. Ready for new product scan.'),
        duration: Duration(milliseconds: 1500),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  void dispose() {
    _camera.stopImageStream();
    _camera.dispose();
    super.dispose();
  }

  String _getGuidanceText(int count) {
    switch (count) {
      case 0:
        return 'Photo 1: Frame Front Label\n(Brand Name & Net Quantity)';
      case 1:
        return 'Photo 2: Frame Back Label\n(MRP, Dates & Packer Details)';
      case 2:
        return 'Photo 3: Frame Side Details\n(Ingredients, FSSAI & Helpline)';
      default:
        return '$count Photos Captured\nTap Analyze or add more sides';
    }
  }

  @override
  Widget build(BuildContext context) {
    final scanState = ref.watch(scanStateProvider);
    final evidence = scanState.evidence;
    final supportsLiveOcr = _cameraReady && _camera.supportsLiveOcr;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 1. Live Camera Preview
          if (_cameraReady)
            _camera.buildPreview()
          else
            const Center(
              child: CircularProgressIndicator(color: ProPalette.accentEmerald),
            ),

          // 2. Viewfinder with dark vignette and corner brackets
          CustomPaint(
            painter: _ViewfinderOverlayPainter(
              hasEvidence: evidence.isNotEmpty,
            ),
          ),

          // 3. Live OCR detection boxes (if supported)
          if (supportsLiveOcr)
            Positioned.fill(
              child: DetectionBoxesOverlay(fields: scanState.detectedFields),
            ),

          // 4. Top Bar: Back | Step Guidance | Flash & Reset
          SafeArea(
            child: Align(
              alignment: Alignment.topCenter,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
                      onPressed: () {
                        if (context.canPop()) {
                          context.pop();
                        } else {
                          context.go(AppRoutes.homePath);
                        }
                      },
                    ),
                    Expanded(
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 8),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.65),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.white.withValues(alpha: 0.15)),
                        ),
                        child: Text(
                          _getGuidanceText(evidence.length),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            height: 1.2,
                          ),
                        ),
                      ),
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (evidence.isNotEmpty)
                          IconButton(
                            icon: const Icon(Icons.refresh_rounded, color: Colors.white70, size: 22),
                            tooltip: 'Reset captures',
                            onPressed: _resetEvidence,
                          ),
                        IconButton(
                          icon: Icon(
                            _flashOn ? Icons.flash_on_rounded : Icons.flash_off_rounded,
                            color: _flashOn ? Colors.amber : Colors.white,
                            size: 22,
                          ),
                          onPressed: _toggleFlash,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),

          // 5. Bottom Controls: Evidence Tray + Analyze Button + Shutter Row
          SafeArea(
            child: Align(
              alignment: Alignment.bottomCenter,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Captured Evidence Thumbnail Strip (if any captured)
                  if (evidence.isNotEmpty) ...[
                    Container(
                      height: 78,
                      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        itemCount: evidence.length + 1,
                        separatorBuilder: (_, __) => const SizedBox(width: 8),
                        itemBuilder: (context, index) {
                          if (index == evidence.length) {
                            return _buildAddMoreThumbnail();
                          }
                          final item = evidence[index];
                          return _buildEvidenceThumbnail(
                            index: index,
                            item: item,
                            onDelete: () => ref.read(scanStateProvider.notifier).deleteAt(index),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 6),
                  ],

                  // Mode Selector: Auto | Label | Barcode | Manual
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.55),
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: _modes.map((mode) {
                        final isSelected = mode == _selectedMode;
                        return GestureDetector(
                          onTap: () => setState(() => _selectedMode = mode),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                            decoration: BoxDecoration(
                              color: isSelected ? const Color(0xFF133E30) : Colors.transparent,
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              mode,
                              style: TextStyle(
                                color: isSelected ? Colors.white : Colors.white70,
                                fontSize: 11,
                                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Shutter Row: Gallery | Big Shutter Button | Quick Proceed
                  Padding(
                    padding: const EdgeInsets.only(left: 32, right: 32, bottom: 16),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // Gallery Picker Button
                        IconButton(
                          onPressed: _pickFromGallery,
                          icon: Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.22),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.photo_library_outlined, color: Colors.white, size: 22),
                          ),
                        ),

                        // Large Circular Shutter Button
                        GestureDetector(
                          onTap: _busy ? null : _capture,
                          child: Container(
                            width: 72,
                            height: 72,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 4),
                            ),
                            padding: const EdgeInsets.all(4),
                            child: Container(
                              decoration: BoxDecoration(
                                color: _busy ? ProPalette.accentEmerald : Colors.white,
                                shape: BoxShape.circle,
                              ),
                              child: _busy
                                  ? const Padding(
                                      padding: EdgeInsets.all(16),
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2.5,
                                        color: Colors.white,
                                      ),
                                    )
                                  : null,
                            ),
                          ),
                        ),

                        // Quick Proceed Arrow or Placeholder
                        if (evidence.isNotEmpty)
                          IconButton(
                            onPressed: _proceedToProcessing,
                            icon: Container(
                              padding: const EdgeInsets.all(10),
                              decoration: const BoxDecoration(
                                color: ProPalette.accentEmerald,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 22),
                            ),
                          )
                        else
                          const SizedBox(width: 48),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEvidenceThumbnail({
    required int index,
    required dynamic item,
    required VoidCallback onDelete,
  }) {
    final path = item.file.path as String;
    final label = item.label as String;

    return Container(
      width: 66,
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.4), width: 1.5),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: Stack(
          fit: StackFit.expand,
          children: [
            Image.file(
              File(path),
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => const Center(
                child: Icon(Icons.broken_image, color: Colors.white54, size: 20),
              ),
            ),
            // Gradient scrim
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Colors.black54, Colors.transparent, Colors.black87],
                  stops: [0.0, 0.4, 1.0],
                ),
              ),
            ),
            // Sequence & label at bottom
            Positioned(
              left: 2,
              right: 2,
              bottom: 2,
              child: Text(
                '#${index + 1} $label',
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            // Delete button at top-right
            Positioned(
              top: 0,
              right: 0,
              child: GestureDetector(
                onTap: onDelete,
                child: Container(
                  padding: const EdgeInsets.all(2),
                  decoration: const BoxDecoration(
                    color: Colors.redAccent,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.close, color: Colors.white, size: 12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddMoreThumbnail() {
    return GestureDetector(
      onTap: _capture,
      child: Container(
        width: 66,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white.withValues(alpha: 0.3), width: 1.2),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.add_a_photo_outlined, color: Colors.white, size: 20),
            SizedBox(height: 3),
            Text(
              '+ Side',
              style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }
}

/// Custom Viewfinder Painter with four corner brackets
class _ViewfinderOverlayPainter extends CustomPainter {
  _ViewfinderOverlayPainter({this.hasEvidence = false});

  final bool hasEvidence;

  @override
  void paint(Canvas canvas, Size size) {
    final frameWidth = size.width * 0.82;
    // Shrink height slightly if evidence tray is visible at bottom
    final frameHeight = hasEvidence ? size.height * 0.44 : size.height * 0.52;
    final left = (size.width - frameWidth) / 2;
    final top = (size.height - frameHeight) / 2 - (hasEvidence ? 40 : 20);
    final rect = Rect.fromLTWH(left, top, frameWidth, frameHeight);

    // Dark semi-transparent scrim outside viewfinder
    final bgPaint = Paint()..color = Colors.black.withValues(alpha: 0.55);
    final bgPath = Path()
      ..addRect(Rect.fromLTWH(0, 0, size.width, size.height))
      ..addRRect(RRect.fromRectAndRadius(rect, const Radius.circular(16)))
      ..fillType = PathFillType.evenOdd;
    canvas.drawPath(bgPath, bgPaint);

    // Corner bracket strokes
    final cornerPaint = Paint()
      ..color = Colors.white
      ..strokeWidth = 3.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const cornerLength = 26.0;

    // Top-left corner
    canvas.drawLine(Offset(left, top + cornerLength), Offset(left, top + 10), cornerPaint);
    canvas.drawArc(Rect.fromLTWH(left, top, 20, 20), 3.14159, 1.57079, false, cornerPaint);
    canvas.drawLine(Offset(left + 10, top), Offset(left + cornerLength, top), cornerPaint);

    // Top-right corner
    final right = left + frameWidth;
    canvas.drawLine(Offset(right - cornerLength, top), Offset(right - 10, top), cornerPaint);
    canvas.drawArc(Rect.fromLTWH(right - 20, top, 20, 20), -1.57079, 1.57079, false, cornerPaint);
    canvas.drawLine(Offset(right, top + 10), Offset(right, top + cornerLength), cornerPaint);

    // Bottom-left corner
    final bottom = top + frameHeight;
    canvas.drawLine(Offset(left, bottom - cornerLength), Offset(left, bottom - 10), cornerPaint);
    canvas.drawArc(Rect.fromLTWH(left, bottom - 20, 20, 20), 3.14159, -1.57079, false, cornerPaint);
    canvas.drawLine(Offset(left + 10, bottom), Offset(left + cornerLength, bottom), cornerPaint);

    // Bottom-right corner
    canvas.drawLine(Offset(right - cornerLength, bottom), Offset(right - 10, bottom), cornerPaint);
    canvas.drawArc(Rect.fromLTWH(right - 20, bottom - 20, 20, 20), 0, 1.57079, false, cornerPaint);
    canvas.drawLine(Offset(right, bottom - 10), Offset(right, bottom - cornerLength), cornerPaint);
  }

  @override
  bool shouldRepaint(covariant _ViewfinderOverlayPainter oldDelegate) =>
      oldDelegate.hasEvidence != hasEvidence;
}
