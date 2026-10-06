import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/scan/model/scan_phase.dart';

void main() {
  group('nextScanPhase transition table', () {
    test('idle framing stays at positionProduct', () {
      expect(
        nextScanPhase(
          ScanPhase.positionProduct,
          detectedFieldCount: 0,
          hasText: false,
          capturing: false,
          analyzing: false,
          complete: false,
        ),
        ScanPhase.positionProduct,
      );
    });

    test('any recognized text → productDetected', () {
      expect(
        nextScanPhase(
          ScanPhase.positionProduct,
          detectedFieldCount: 0,
          hasText: true,
          capturing: false,
          analyzing: false,
          complete: false,
        ),
        ScanPhase.productDetected,
      );
    });

    test('detected field boxes → readingLabel', () {
      expect(
        nextScanPhase(
          ScanPhase.productDetected,
          detectedFieldCount: 2,
          hasText: true,
          capturing: false,
          analyzing: false,
          complete: false,
        ),
        ScanPhase.readingLabel,
      );
    });

    test('capturing → extractingDeclarations', () {
      expect(
        nextScanPhase(
          ScanPhase.readingLabel,
          detectedFieldCount: 2,
          hasText: true,
          capturing: true,
          analyzing: false,
          complete: false,
        ),
        ScanPhase.extractingDeclarations,
      );
    });

    test('analyzing → verifyingCompliance', () {
      expect(
        nextScanPhase(
          ScanPhase.extractingDeclarations,
          detectedFieldCount: 2,
          hasText: true,
          capturing: true,
          analyzing: true,
          complete: false,
        ),
        ScanPhase.verifyingCompliance,
      );
    });

    test('complete → analysisComplete', () {
      expect(
        nextScanPhase(
          ScanPhase.verifyingCompliance,
          detectedFieldCount: 2,
          hasText: true,
          capturing: true,
          analyzing: false,
          complete: true,
        ),
        ScanPhase.analysisComplete,
      );
    });

    test('full forward sequence position→detected→reading→extracting→verifying→complete',
        () {
      // position → detected
      var phase = nextScanPhase(
        ScanPhase.positionProduct,
        detectedFieldCount: 0,
        hasText: true,
        capturing: false,
        analyzing: false,
        complete: false,
      );
      expect(phase, ScanPhase.productDetected);

      // detected → reading
      phase = nextScanPhase(
        phase,
        detectedFieldCount: 3,
        hasText: true,
        capturing: false,
        analyzing: false,
        complete: false,
      );
      expect(phase, ScanPhase.readingLabel);

      // reading → extracting
      phase = nextScanPhase(
        phase,
        detectedFieldCount: 3,
        hasText: true,
        capturing: true,
        analyzing: false,
        complete: false,
      );
      expect(phase, ScanPhase.extractingDeclarations);

      // extracting → verifying
      phase = nextScanPhase(
        phase,
        detectedFieldCount: 3,
        hasText: true,
        capturing: true,
        analyzing: true,
        complete: false,
      );
      expect(phase, ScanPhase.verifyingCompliance);

      // verifying → complete
      phase = nextScanPhase(
        phase,
        detectedFieldCount: 3,
        hasText: true,
        capturing: true,
        analyzing: true,
        complete: true,
      );
      expect(phase, ScanPhase.analysisComplete);
    });

    test('transient detection loss does not regress a latched phase', () {
      // Mid-capture, a frame loses detection — should hold extracting, not
      // drop back to positionProduct.
      final phase = nextScanPhase(
        ScanPhase.extractingDeclarations,
        detectedFieldCount: 0,
        hasText: false,
        capturing: false,
        analyzing: false,
        complete: false,
      );
      expect(phase, ScanPhase.extractingDeclarations);
    });

    test('captions are the uppercase plan copy', () {
      expect(ScanPhase.positionProduct.caption, 'POSITION PRODUCT');
      expect(ScanPhase.productDetected.caption, 'PRODUCT DETECTED');
      expect(ScanPhase.readingLabel.caption, 'READING LABEL');
      expect(
        ScanPhase.extractingDeclarations.caption,
        'EXTRACTING DECLARATIONS',
      );
      expect(ScanPhase.verifyingCompliance.caption, 'VERIFYING COMPLIANCE');
      expect(ScanPhase.analysisComplete.caption, 'ANALYSIS COMPLETE');
    });
  });
}
