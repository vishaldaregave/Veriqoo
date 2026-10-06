import 'dart:io' show Platform;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/camera/scan_camera_controller.dart';

/// Real [ScanCameraController] over the `camera` package.
///
/// Every plugin call is guarded so a camera failure degrades gracefully (the
/// preview falls back to a placeholder, live OCR is reported unsupported) and
/// never crashes the scanner. On web, live OCR is unsupported (ML Kit has no
/// web implementation) so the stream is never started.
class CameraPackageController implements ScanCameraController {
  CameraController? _controller;
  CameraDescription? _description;
  bool _initialized = false;
  bool _supportsLiveOcr = false;
  bool _flashOn = false;
  bool _streaming = false;

  @override
  bool get isInitialized => _initialized;

  @override
  bool get supportsLiveOcr => _supportsLiveOcr;

  @override
  bool get flashOn => _flashOn;

  @override
  Future<void> initialize() async {
    // ML Kit text recognition has no web implementation; keep preview + manual
    // capture working but never attempt the live stream.
    if (kIsWeb) {
      _supportsLiveOcr = false;
    }
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        _initialized = false;
        _supportsLiveOcr = false;
        return;
      }
      final description = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      _description = description;

      final controller = CameraController(
        description,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: kIsWeb
            ? ImageFormatGroup.unknown
            : (Platform.isAndroid
                ? ImageFormatGroup.nv21
                : ImageFormatGroup.bgra8888),
      );
      await controller.initialize();
      _controller = controller;
      _initialized = true;
      // Live OCR requires a non-web platform with a usable byte stream.
      _supportsLiveOcr = !kIsWeb;
    } catch (error, stackTrace) {
      debugPrint('Camera initialize failed; degrading: $error');
      debugPrintStack(stackTrace: stackTrace);
      _initialized = false;
      _supportsLiveOcr = false;
    }
  }

  @override
  Widget buildPreview() {
    final controller = _controller;
    if (_initialized && controller != null) {
      return CameraPreview(controller);
    }
    return const _CameraPlaceholder();
  }

  @override
  Future<XFile> takePicture() async {
    final controller = _controller;
    if (controller == null || !_initialized) {
      throw StateError('Camera is not initialized.');
    }
    // takePicture cannot run while the image stream is active on some
    // platforms; pause the stream around the capture.
    final wasStreaming = _streaming;
    if (wasStreaming) {
      await stopImageStream();
    }
    final file = await controller.takePicture();
    return file;
  }

  @override
  Future<void> startImageStream(
    void Function(ScanCameraFrame frame) onFrame,
  ) async {
    final controller = _controller;
    if (!_supportsLiveOcr || controller == null || !_initialized) {
      return;
    }
    if (_streaming) {
      return;
    }
    try {
      final description = _description;
      final rotation = description == null
          ? InputImageRotation.rotation0deg
          : (InputImageRotationValue.fromRawValue(
                description.sensorOrientation,
              ) ??
              InputImageRotation.rotation0deg);
      final format = kIsWeb || !Platform.isAndroid
          ? InputImageFormat.bgra8888
          : InputImageFormat.nv21;

      await controller.startImageStream((CameraImage image) {
        if (image.planes.isEmpty) {
          return;
        }
        final plane = image.planes.first;
        onFrame(
          ScanCameraFrame(
            bytes: plane.bytes,
            width: image.width,
            height: image.height,
            format: format,
            rotation: rotation,
            bytesPerRow: plane.bytesPerRow,
          ),
        );
      });
      _streaming = true;
    } catch (error, stackTrace) {
      debugPrint('startImageStream failed; degrading: $error');
      debugPrintStack(stackTrace: stackTrace);
      _streaming = false;
    }
  }

  @override
  Future<void> stopImageStream() async {
    final controller = _controller;
    if (controller == null || !_streaming) {
      return;
    }
    try {
      await controller.stopImageStream();
    } catch (error) {
      debugPrint('stopImageStream failed: $error');
    } finally {
      _streaming = false;
    }
  }

  @override
  Future<void> setFlash(bool on) async {
    final controller = _controller;
    if (controller == null || !_initialized) {
      return;
    }
    try {
      await controller.setFlashMode(on ? FlashMode.torch : FlashMode.off);
      _flashOn = on;
    } catch (error) {
      debugPrint('setFlash failed: $error');
    }
  }

  @override
  Future<void> dispose() async {
    final controller = _controller;
    _controller = null;
    _initialized = false;
    _streaming = false;
    if (controller == null) {
      return;
    }
    try {
      await controller.dispose();
    } catch (error) {
      debugPrint('Camera dispose failed: $error');
    }
  }
}

/// Shown while the camera is unavailable/initializing — a true-black surface so
/// the overlay reads cleanly over it.
class _CameraPlaceholder extends StatelessWidget {
  const _CameraPlaceholder();

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return ColoredBox(color: tokens.bgTrue);
  }
}
