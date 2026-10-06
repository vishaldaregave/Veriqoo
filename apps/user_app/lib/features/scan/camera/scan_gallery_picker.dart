import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// Injectable gallery picker (image_picker fallback). Tests supply a fake so
/// the gallery path is exercised without opening a real picker.
abstract class ScanGalleryPicker {
  /// Picks a single image from the device gallery, or null if cancelled.
  Future<XFile?> pick();
}

/// Production picker over `image_picker`.
class ImagePickerGallery implements ScanGalleryPicker {
  ImagePickerGallery({ImagePicker? picker})
      : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  @override
  Future<XFile?> pick() {
    return _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
    );
  }
}

/// Provides the gallery picker. Overridable in tests with a fake.
final scanGalleryPickerProvider = Provider<ScanGalleryPicker>((ref) {
  return ImagePickerGallery();
});
