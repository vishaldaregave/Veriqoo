import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';

import 'package:flutter_application_1/features/scan/camera/camera_package_controller.dart';

/// A platform-agnostic camera frame handed to the live-OCR analyzer.
///
/// Deliberately camera-package-free: it carries only the raw plane [bytes],
/// geometry, and the two ML-Kit descriptors ([format], [rotation]) needed to
/// build an `InputImage`. This is the ONLY ML-Kit type the abstraction leaks,
/// so the analyzer and tests never import `camera`.
@immutable
class ScanCameraFrame {
  const ScanCameraFrame({
    required this.bytes,
    required this.width,
    required this.height,
    required this.format,
    required this.rotation,
    required this.bytesPerRow,
  });

  /// Raw bytes of the first plane (NV21 on Android, BGRA on iOS).
  final Uint8List bytes;

  /// Frame width in pixels.
  final int width;

  /// Frame height in pixels.
  final int height;

  /// ML-Kit input format for these [bytes].
  final InputImageFormat format;

  /// Sensor rotation to apply.
  final InputImageRotation rotation;

  /// Row stride of the first plane, in bytes.
  final int bytesPerRow;
}

/// Injectable camera surface the scanner UI drives.
///
/// A fake implements this for widget tests so no real camera (or Supabase) is
/// touched; [CameraPackageController] implements it over the `camera` package.
abstract class ScanCameraController {
  /// Prepares the camera. Must not throw — failures degrade to an
  /// uninitialized / live-OCR-unsupported state.
  Future<void> initialize();

  /// Whether [initialize] succeeded and a preview can be shown.
  bool get isInitialized;

  /// Whether this platform can run the live image stream for OCR. False on web
  /// (ML Kit unavailable) or when the camera failed to initialize.
  bool get supportsLiveOcr;

  /// Builds the preview widget (a real `CameraPreview`, or a placeholder).
  Widget buildPreview();

  /// Captures a still image.
  Future<XFile> takePicture();

  /// Starts streaming frames to [onFrame]. A no-op when live OCR is
  /// unsupported.
  Future<void> startImageStream(void Function(ScanCameraFrame frame) onFrame);

  /// Stops the frame stream.
  Future<void> stopImageStream();

  /// Toggles the torch/flash.
  Future<void> setFlash(bool on);

  /// Current flash state.
  bool get flashOn;

  /// Releases camera resources.
  Future<void> dispose();
}

/// Factory provider so each screen mount gets a fresh controller. Tests
/// override this to return a fake factory.
final scanCameraControllerProvider =
    Provider<ScanCameraController Function()>((ref) {
  return CameraPackageController.new;
});
