import 'dart:typed_data';
import 'dart:ui' show Rect;

import 'package:flutter_test/flutter_test.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

import 'package:flutter_application_1/features/scan/camera/scan_camera_controller.dart';
import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/ocr/live_ocr_analyzer.dart';

void main() {
  group('mapBlocksToFields', () {
    List<RecognizedBlockLite> blocks() => <RecognizedBlockLite>[
          const RecognizedBlockLite(
            text: 'Oat Crunch Cereal',
            boundingBox: Rect.fromLTWH(20, 10, 200, 40),
          ),
          const RecognizedBlockLite(
            text: 'MRP ₹120 (incl. of all taxes)',
            boundingBox: Rect.fromLTWH(20, 120, 160, 30),
          ),
          const RecognizedBlockLite(
            text: 'Batch No: AB123',
            boundingBox: Rect.fromLTWH(20, 170, 150, 30),
          ),
          const RecognizedBlockLite(
            text: 'Mfg by Acme Foods Pvt Ltd',
            boundingBox: Rect.fromLTWH(20, 220, 260, 30),
          ),
          const RecognizedBlockLite(
            text: 'Net Qty: 500 g',
            boundingBox: Rect.fromLTWH(20, 270, 140, 30),
          ),
        ];

    test('maps keywords to the five labels', () {
      final fields = mapBlocksToFields(
        blocks(),
        imageWidth: 400,
        imageHeight: 400,
      );
      final labels = fields.map((f) => f.label).toSet();
      expect(labels, contains(DetectedFieldLabels.mrp));
      expect(labels, contains(DetectedFieldLabels.batch));
      expect(labels, contains(DetectedFieldLabels.manufacturer));
      expect(labels, contains(DetectedFieldLabels.mandatoryDeclaration));
      expect(labels, contains(DetectedFieldLabels.productName));
    });

    test('normalizes rects into 0..1 space', () {
      final fields = mapBlocksToFields(
        blocks(),
        imageWidth: 400,
        imageHeight: 400,
      );
      final mrp = fields.firstWhere((f) => f.label == DetectedFieldLabels.mrp);
      // left 20/400 = 0.05, top 120/400 = 0.30.
      expect(mrp.rectNormalized.left, closeTo(0.05, 1e-9));
      expect(mrp.rectNormalized.top, closeTo(0.30, 1e-9));
      for (final f in fields) {
        expect(f.rectNormalized.left, inInclusiveRange(0.0, 1.0));
        expect(f.rectNormalized.top, inInclusiveRange(0.0, 1.0));
        expect(f.rectNormalized.right, inInclusiveRange(0.0, 1.0));
        expect(f.rectNormalized.bottom, inInclusiveRange(0.0, 1.0));
      }
    });

    test('each label is emitted at most once', () {
      final fields = mapBlocksToFields(
        blocks(),
        imageWidth: 400,
        imageHeight: 400,
      );
      final labels = fields.map((f) => f.label).toList();
      expect(labels.length, labels.toSet().length);
    });

    test('empty input or invalid size yields no fields', () {
      expect(
        mapBlocksToFields(const [], imageWidth: 400, imageHeight: 400),
        isEmpty,
      );
      expect(
        mapBlocksToFields(blocks(), imageWidth: 0, imageHeight: 400),
        isEmpty,
      );
    });
  });

  group('buildInputImage per-platform construction', () {
    test('Android NV21 frame → nv21 format + rotation + stride', () {
      final frame = ScanCameraFrame(
        bytes: Uint8List.fromList(List<int>.filled(16, 0)),
        width: 640,
        height: 480,
        format: InputImageFormat.nv21,
        rotation: InputImageRotation.rotation90deg,
        bytesPerRow: 640,
      );
      final json = buildInputImage(frame).toJson();
      final metadata = json['metadata'] as Map<String, dynamic>;
      expect(metadata['image_format'], InputImageFormat.nv21.rawValue);
      expect(metadata['rotation'], InputImageRotation.rotation90deg.rawValue);
      expect(metadata['bytes_per_row'], 640);
      expect(metadata['width'], 640.0);
      expect(metadata['height'], 480.0);
    });

    test('iOS BGRA frame → bgra8888 format + stride', () {
      final frame = ScanCameraFrame(
        bytes: Uint8List.fromList(List<int>.filled(32, 0)),
        width: 1280,
        height: 720,
        format: InputImageFormat.bgra8888,
        rotation: InputImageRotation.rotation0deg,
        bytesPerRow: 1280 * 4,
      );
      final json = buildInputImage(frame).toJson();
      final metadata = json['metadata'] as Map<String, dynamic>;
      expect(metadata['image_format'], InputImageFormat.bgra8888.rawValue);
      expect(metadata['rotation'], InputImageRotation.rotation0deg.rawValue);
      expect(metadata['bytes_per_row'], 1280 * 4);
      expect(metadata['width'], 1280.0);
      expect(metadata['height'], 720.0);
    });
  });

  group('ThrottledOcrRunner', () {
    test('drops frames while a recognition is in flight', () async {
      var calls = 0;
      final runner = ThrottledOcrRunner(
        analyze: (frame) async {
          calls++;
          // Simulate in-flight work spanning the next submit.
          await Future<void>.delayed(const Duration(milliseconds: 5));
          return const LiveOcrResult.empty();
        },
      );
      final frame = ScanCameraFrame(
        bytes: Uint8List.fromList(const <int>[0]),
        width: 10,
        height: 10,
        format: InputImageFormat.nv21,
        rotation: InputImageRotation.rotation0deg,
        bytesPerRow: 10,
      );

      final first = runner.submit(frame);
      final droppedWhileInFlight = await runner.submit(frame);
      await first;

      expect(droppedWhileInFlight, isNull);
      expect(calls, 1);
    });

    test('enforces the minimum interval between passes', () async {
      final runner = ThrottledOcrRunner(
        analyze: (frame) async => const LiveOcrResult.empty(),
        minInterval: const Duration(milliseconds: 50),
      );
      final frame = ScanCameraFrame(
        bytes: Uint8List.fromList(const <int>[0]),
        width: 10,
        height: 10,
        format: InputImageFormat.nv21,
        rotation: InputImageRotation.rotation0deg,
        bytesPerRow: 10,
      );

      final first = await runner.submit(frame);
      final tooSoon = await runner.submit(frame);
      expect(first, isNotNull);
      expect(tooSoon, isNull);
    });
  });
}
