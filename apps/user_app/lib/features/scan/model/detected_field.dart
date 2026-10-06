import 'dart:ui' show Rect;

import 'package:flutter/foundation.dart';

/// The five target label fields the live OCR heuristic maps recognized text to.
///
/// Kept as plain strings (not an enum) because they double as the tiny labels
/// painted above each detection box and must match the copy in the plan:
/// `PRODUCT NAME`, `MRP`, `BATCH`, `MANUFACTURER`, `MANDATORY DECLARATION`.
abstract final class DetectedFieldLabels {
  const DetectedFieldLabels._();

  static const String productName = 'PRODUCT NAME';
  static const String mrp = 'MRP';
  static const String batch = 'BATCH';
  static const String manufacturer = 'MANUFACTURER';
  static const String mandatoryDeclaration = 'MANDATORY DECLARATION';

  /// All five labels, in display order.
  static const List<String> all = <String>[
    productName,
    mrp,
    batch,
    manufacturer,
    mandatoryDeclaration,
  ];
}

/// A single detected label region rendered as a thin bounding box.
///
/// Camera/ML-Kit-type-free so it is pure and testable: [rectNormalized] is in
/// `0..1` space (resolved against the paint size by `DetectionBoxesPainter`),
/// [label] is one of [DetectedFieldLabels], and [text] is the recognized source
/// text (optional).
@immutable
class DetectedField {
  const DetectedField({
    required this.rectNormalized,
    required this.label,
    this.text,
  });

  /// Field bounds in normalized `0..1` coordinates.
  final Rect rectNormalized;

  /// One of the five [DetectedFieldLabels].
  final String label;

  /// The recognized text this field was mapped from, if any.
  final String? text;

  @override
  bool operator ==(Object other) =>
      other is DetectedField &&
      other.rectNormalized == rectNormalized &&
      other.label == label &&
      other.text == text;

  @override
  int get hashCode => Object.hash(rectNormalized, label, text);
}

/// The result of one live-OCR pass over a camera frame: the raw recognized
/// [rawText] plus the mapped [fields]. Pure and camera-free.
@immutable
class LiveOcrResult {
  const LiveOcrResult({
    required this.rawText,
    required this.fields,
  });

  /// Empty result (no text, no fields).
  const LiveOcrResult.empty()
      : rawText = '',
        fields = const <DetectedField>[];

  /// All recognized text from the frame.
  final String rawText;

  /// The mapped label regions.
  final List<DetectedField> fields;
}
