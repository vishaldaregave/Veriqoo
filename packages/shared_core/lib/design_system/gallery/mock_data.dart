import 'package:flutter/foundation.dart';

import '../../services/compliance_analysis.dart';
import '../components/veriqoo_status.dart';

/// Mock data for the VERIQOO [design gallery].
///
/// Everything here is realistic Indian packaged-goods inspection data built on
/// the REAL [ComplianceAnalysis] / [ComplianceIssue] business models from
/// `package:shared_core/services/compliance_analysis.dart`. The gallery never
/// hits the network or Supabase; it renders these fixtures so the design
/// system can be reviewed in isolation.
abstract final class VeriqooMockData {
  const VeriqooMockData._();

  /// The hero product used across the gallery headline, score dial, and the
  /// scanner / loading previews.
  static const String heroProductName = 'Organic Wheat Biscuits';

  /// Hero MRP as printed on the pack.
  static const String heroMrp = 'Rs.120';

  /// Hero net quantity declaration.
  static const String heroNetQuantity = '200 g';

  /// Hero manufacturer.
  static const String heroManufacturer = 'ABC Foods Pvt. Ltd.';

  /// Hero inspection identifier (rendered in mono tabular figures).
  static const String heroInspectionId = 'VRQ-20261004-0182';

  /// Hero OCR confidence read-out.
  static const String heroOcrConfidence = 'OCR 98.2%';

  /// Hero compliance score (out of 100).
  static const int heroScore = 87;

  /// The fully-populated analysis for the hero product. It is marginally
  /// non-compliant: one missing declaration and one possible issue, which maps
  /// to a [VeriqooStatusKind.flag] in the ledger.
  static final ComplianceAnalysis heroAnalysis = ComplianceAnalysis(
    productName: heroProductName,
    mrp: heroMrp,
    netQuantity: heroNetQuantity,
    manufacturer: heroManufacturer,
    address: 'Plot 14, MIDC Industrial Area, Pune, Maharashtra 411019',
    packingDate: '04 Oct 2026',
    customerCare: 'care@abcfoods.in / 1800-200-0182',
    missingInformation: const <String>[
      'FSSAI license number not detected on the label',
    ],
    possibleIssues: <ComplianceIssue>[
      ComplianceIssue(
        title: 'Net quantity declaration placement',
        description:
            'The net quantity "200 g" is printed on the side panel rather than '
            'the principal display panel, which may not satisfy the placement '
            'requirement for pre-packaged commodities.',
        severity: 'medium',
        ruleNumbers: const <String>['LM(PC) Rule 9'],
        ruleTitles: const <String>[
          'Declarations to be made on every pre-packaged commodity',
        ],
        legalBasis:
            'Legal Metrology (Packaged Commodities) Rules, 2011, Rule 9',
        ocrEvidence: 'NET QTY 200 g (side panel)',
        verificationStatus: LegalVerificationStatus.possibleConcern,
      ),
    ],
  );

  /// A fully-compliant analysis — maps to [VeriqooStatusKind.verified].
  static final ComplianceAnalysis compliantAnalysis = ComplianceAnalysis(
    productName: 'Cold Pressed Groundnut Oil',
    mrp: 'Rs.345',
    netQuantity: '1 L',
    manufacturer: 'Sahyadri Oils & Foods Pvt. Ltd.',
    address: 'Survey 88, Nashik Road, Nashik, Maharashtra 422101',
    packingDate: '28 Sep 2026',
    customerCare: 'support@sahyadrioils.in / 1800-123-4567',
    missingInformation: const <String>[],
    possibleIssues: const <ComplianceIssue>[],
  );

  /// An analysis with multiple serious violations — maps to
  /// [VeriqooStatusKind.violation].
  static final ComplianceAnalysis violationAnalysis = ComplianceAnalysis(
    productName: 'Mixed Fruit Jam',
    mrp: 'Rs.95',
    netQuantity: '500 g',
    manufacturer: 'Nova Preserves',
    address: 'Not legible',
    packingDate: 'Not detected',
    customerCare: '',
    missingInformation: const <String>[
      'Date of manufacture / packing not detected',
      'Complete manufacturer address not legible',
    ],
    possibleIssues: <ComplianceIssue>[
      ComplianceIssue(
        title: 'Missing mandatory manufacturer address',
        description:
            'The complete name and address of the manufacturer could not be '
            'read on the label, which is a mandatory declaration.',
        severity: 'high',
        ruleNumbers: const <String>['LM(PC) Rule 7'],
        ruleTitles: const <String>[
          'Declaration of name and address of manufacturer',
        ],
        legalBasis:
            'Legal Metrology (Packaged Commodities) Rules, 2011, Rule 7',
        ocrEvidence: 'NOVA PRESERVES … (address illegible)',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ),
      ComplianceIssue(
        title: 'Date of manufacture absent',
        description:
            'No month and year of manufacture or packing was detected on the '
            'principal display panel.',
        severity: 'high',
        ruleNumbers: const <String>['LM(PC) Rule 9'],
        ruleTitles: const <String>['Date of manufacture / packing'],
        legalBasis:
            'Legal Metrology (Packaged Commodities) Rules, 2011, Rule 9',
        verificationStatus: LegalVerificationStatus.possibleConcern,
      ),
    ],
  );

  /// An analysis where the label scan was incomplete — maps to
  /// [VeriqooStatusKind.missing].
  static final ComplianceAnalysis incompleteAnalysis = ComplianceAnalysis(
    productName: 'Masala Peanuts',
    mrp: '',
    netQuantity: '150 g',
    manufacturer: 'Krishna Snack Works',
    address: 'Rajkot, Gujarat',
    packingDate: '',
    customerCare: '',
    missingInformation: const <String>[
      'Maximum retail price (MRP) not detected',
      'Customer care details not detected',
    ],
    possibleIssues: const <ComplianceIssue>[],
  );

  /// The ledger rows rendered by the gallery's inspection list, pairing each
  /// [ComplianceAnalysis] with its inspection metadata and verification
  /// outcome. Statuses are mixed on purpose so every [VeriqooStatusKind]
  /// encoding appears.
  static final List<GalleryInspection> inspections = <GalleryInspection>[
    GalleryInspection(
      inspectionId: heroInspectionId,
      timestamp: '04 OCT 2026 · 14:08',
      score: heroScore,
      status: VeriqooStatusKind.flag,
      analysis: heroAnalysis,
    ),
    GalleryInspection(
      inspectionId: 'VRQ-20260928-0149',
      timestamp: '28 SEP 2026 · 09:51',
      score: 96,
      status: VeriqooStatusKind.verified,
      analysis: compliantAnalysis,
    ),
    GalleryInspection(
      inspectionId: 'VRQ-20260922-0113',
      timestamp: '22 SEP 2026 · 17:33',
      score: 41,
      status: VeriqooStatusKind.violation,
      analysis: violationAnalysis,
    ),
    GalleryInspection(
      inspectionId: 'VRQ-20260915-0087',
      timestamp: '15 SEP 2026 · 11:12',
      score: 63,
      status: VeriqooStatusKind.missing,
      analysis: incompleteAnalysis,
    ),
  ];
}

/// A single inspection ledger entry for the gallery: inspection metadata plus
/// the underlying [ComplianceAnalysis].
@immutable
class GalleryInspection {
  const GalleryInspection({
    required this.inspectionId,
    required this.timestamp,
    required this.score,
    required this.status,
    required this.analysis,
  });

  /// Inspection identifier, e.g. `VRQ-20261004-0182`.
  final String inspectionId;

  /// Human-readable timestamp string.
  final String timestamp;

  /// Compliance score out of 100.
  final int score;

  /// Verification outcome encoding.
  final VeriqooStatusKind status;

  /// The real analysis model behind this row.
  final ComplianceAnalysis analysis;
}
