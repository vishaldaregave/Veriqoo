import 'dart:ui' show Rect, Size;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

import 'package:flutter_application_1/features/scan/camera/scan_camera_controller.dart';
import 'package:flutter_application_1/features/scan/model/detected_field.dart';

/// A pure, ML-Kit-free view of one recognized text block: its [text] and its
/// pixel [boundingBox]. Lets the block→field mapping be unit-tested without a
/// camera or a `TextRecognizer`.
@immutable
class RecognizedBlockLite {
  const RecognizedBlockLite({required this.text, required this.boundingBox});

  final String text;
  final Rect boundingBox;
}

/// Minimum interval between live-OCR passes (within the 300–500ms band).
const Duration kLiveOcrMinInterval = Duration(milliseconds: 350);

/// Builds an ML-Kit [InputImage] from a platform-agnostic [ScanCameraFrame].
///
/// Pure and side-effect-free so per-platform construction (Android NV21, iOS
/// BGRA) can be asserted in tests via `InputImage.toJson()`.
InputImage buildInputImage(ScanCameraFrame frame) {
  return InputImage.fromBytes(
    bytes: frame.bytes,
    metadata: InputImageMetadata(
      size: Size(frame.width.toDouble(), frame.height.toDouble()),
      rotation: frame.rotation,
      format: frame.format,
      bytesPerRow: frame.bytesPerRow,
    ),
  );
}

/// Maps recognized blocks to the five target [DetectedField]s using a pure
/// keyword heuristic, normalizing each box by [imageWidth]/[imageHeight].
///
/// Heuristics (first match wins per label, each label emitted at most once):
/// * MRP — `mrp`, `m.r.p`, `₹`, `rs`, `inr`, `price`.
/// * BATCH — `batch`, `lot`, `b.no`, `batch no`.
/// * MANUFACTURER — `mfg`, `manufactured by`, `marketed by`, `packed by`.
/// * MANDATORY DECLARATION — `net`, `qty`, `quantity`, `net wt`, or a unit
///   token (`g`, `kg`, `ml`, `l`) alongside a quantity keyword.
/// * PRODUCT NAME — the first large block near the top that matched nothing
///   else.
List<DetectedField> mapBlocksToFields(
  List<RecognizedBlockLite> blocks, {
  required int imageWidth,
  required int imageHeight,
}) {
  if (blocks.isEmpty || imageWidth <= 0 || imageHeight <= 0) {
    return const <DetectedField>[];
  }

  final width = imageWidth.toDouble();
  final height = imageHeight.toDouble();
  final taken = <String>{};
  final fields = <DetectedField>[];

  Rect normalize(Rect r) {
    final left = (r.left / width).clamp(0.0, 1.0);
    final top = (r.top / height).clamp(0.0, 1.0);
    final right = (r.right / width).clamp(0.0, 1.0);
    final bottom = (r.bottom / height).clamp(0.0, 1.0);
    return Rect.fromLTRB(left, top, right, bottom);
  }

  void add(String label, RecognizedBlockLite block) {
    if (taken.contains(label)) {
      return;
    }
    taken.add(label);
    fields.add(
      DetectedField(
        rectNormalized: normalize(block.boundingBox),
        label: label,
        text: block.text,
      ),
    );
  }

  String? classify(String raw) {
    final text = raw.toLowerCase();
    if (text.contains('mrp') ||
        text.contains('m.r.p') ||
        text.contains('₹') ||
        text.contains('inr') ||
        text.contains('rs.') ||
        text.contains('rs ') ||
        text.contains('price')) {
      return DetectedFieldLabels.mrp;
    }
    if (text.contains('batch') ||
        text.contains('lot') ||
        text.contains('b.no') ||
        text.contains('batch no')) {
      return DetectedFieldLabels.batch;
    }
    if (text.contains('mfg') ||
        text.contains('manufactured by') ||
        text.contains('marketed by') ||
        text.contains('packed by') ||
        text.contains('manufacturer')) {
      return DetectedFieldLabels.manufacturer;
    }
    final hasUnit = RegExp(r'\b\d+(\.\d+)?\s?(g|kg|ml|l)\b').hasMatch(text);
    if (text.contains('net') ||
        text.contains('qty') ||
        text.contains('quantity') ||
        text.contains('net wt') ||
        hasUnit) {
      return DetectedFieldLabels.mandatoryDeclaration;
    }
    return null;
  }

  for (final block in blocks) {
    final label = classify(block.text);
    if (label != null) {
      add(label, block);
    }
  }

  // Product name: first large-ish block near the top that was not already
  // claimed, otherwise just the first block.
  if (!taken.contains(DetectedFieldLabels.productName)) {
    final sorted = <RecognizedBlockLite>[...blocks]
      ..sort((a, b) => a.boundingBox.top.compareTo(b.boundingBox.top));
    RecognizedBlockLite? candidate;
    for (final block in sorted) {
      if (classify(block.text) == null && block.text.trim().isNotEmpty) {
        candidate = block;
        break;
      }
    }
    candidate ??= sorted.isNotEmpty ? sorted.first : null;
    if (candidate != null) {
      add(DetectedFieldLabels.productName, candidate);
    }
  }

  return fields;
}

/// Runs ML-Kit text recognition over camera frames and maps the result to
/// [DetectedField]s. The [TextRecognizer] is injectable so tests can supply a
/// fake (and the analyzer never touches a camera).
class LiveOcrAnalyzer {
  LiveOcrAnalyzer({TextRecognizer? recognizer})
      : _recognizer = recognizer ?? TextRecognizer();

  final TextRecognizer _recognizer;

  /// Recognizes text in [frame] and maps it to a [LiveOcrResult]. Returns null
  /// on failure (so a transient frame error never breaks the stream).
  Future<LiveOcrResult?> analyze(ScanCameraFrame frame) async {
    try {
      final inputImage = buildInputImage(frame);
      final recognized = await _recognizer.processImage(inputImage);
      final blocks = <RecognizedBlockLite>[
        for (final block in recognized.blocks)
          RecognizedBlockLite(
            text: block.text,
            boundingBox: block.boundingBox,
          ),
      ];
      final fields = mapBlocksToFields(
        blocks,
        imageWidth: frame.width,
        imageHeight: frame.height,
      );
      return LiveOcrResult(rawText: recognized.text, fields: fields);
    } catch (error) {
      debugPrint('LiveOcrAnalyzer.analyze failed: $error');
      return null;
    }
  }

  /// Releases the recognizer.
  Future<void> close() => _recognizer.close();
}

/// Throttles frame processing: drops frames while a recognition is in flight
/// AND enforces [minInterval] between passes. The scanner feeds every frame to
/// [submit]; at most one recognition runs at a time.
class ThrottledOcrRunner {
  ThrottledOcrRunner({
    required this.analyze,
    this.minInterval = kLiveOcrMinInterval,
  });

  /// The recognition callback (typically `LiveOcrAnalyzer.analyze`).
  final Future<LiveOcrResult?> Function(ScanCameraFrame frame) analyze;

  /// Minimum spacing between recognitions.
  final Duration minInterval;

  final Stopwatch _since = Stopwatch();
  bool _inFlight = false;

  /// Feeds a [frame]. Returns the result when the frame was processed, or null
  /// when it was throttled/dropped or recognition yielded nothing.
  Future<LiveOcrResult?> submit(ScanCameraFrame frame) async {
    if (_inFlight) {
      return null;
    }
    if (_since.isRunning && _since.elapsed < minInterval) {
      return null;
    }
    _inFlight = true;
    try {
      final result = await analyze(frame);
      return result;
    } finally {
      _inFlight = false;
      _since
        ..reset()
        ..start();
    }
  }
}

/// Provides the live-OCR analyzer. Overridable in tests with a fake.
final scanLiveOcrAnalyzerProvider = Provider<LiveOcrAnalyzer>((ref) {
  final analyzer = LiveOcrAnalyzer();
  ref.onDispose(analyzer.close);
  return analyzer;
});
