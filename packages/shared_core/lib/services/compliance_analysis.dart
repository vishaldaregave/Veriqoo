class AIAnalysisException implements Exception {
  const AIAnalysisException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Thrown when Gemini determines the scanned image is not a packaged product.
class NotAProductException implements Exception {
  const NotAProductException(this.reason);

  /// Human-readable explanation of what the image actually shows.
  final String reason;

  @override
  String toString() => reason;
}
enum LegalVerificationStatus {
  legallyVerified,
  possibleConcern,
  cannotDetermine,
  generalObservation;

  static LegalVerificationStatus fromValue(String? value) {
    switch (value) {
      case 'legally_verified':
        return legallyVerified;

      case 'possible_concern':
        return possibleConcern;

      case 'cannot_determine':
        return cannotDetermine;

      case 'general_observation':
      default:
        return generalObservation;
    }
  }

  String get value {
    switch (this) {
      case LegalVerificationStatus.legallyVerified:
        return 'legally_verified';

      case LegalVerificationStatus.possibleConcern:
        return 'possible_concern';

      case LegalVerificationStatus.cannotDetermine:
        return 'cannot_determine';

      case LegalVerificationStatus.generalObservation:
        return 'general_observation';
    }
  }
}
class ComplianceIssue {
  const ComplianceIssue({
    required this.title,
    required this.description,
    required this.severity,
    this.ruleNumbers = const [],
    this.ruleTitles = const [],
    this.legalBasis,
    this.ocrEvidence,
    this.verificationStatus =
        LegalVerificationStatus.generalObservation,
  });

  final String title;
  final String description;
  final String severity;
  final List<String> ruleNumbers;
  final List<String> ruleTitles;
  final String? legalBasis;
  final String? ocrEvidence;
  

  final LegalVerificationStatus verificationStatus;
  factory ComplianceIssue.fromJson(Map<String, dynamic> json) {
  final rawRuleNumbers = json['ruleNumbers'] is List
      ? List<dynamic>.from(json['ruleNumbers'] as List)
      : const <dynamic>[];

  final rawRuleTitles = json['ruleTitles'] is List
      ? List<dynamic>.from(json['ruleTitles'] as List)
      : const <dynamic>[];

  return ComplianceIssue(
    title: (json['title'] as String? ?? '').trim(),
    description: (json['description'] as String? ?? '').trim(),
    severity: (json['severity'] as String? ?? 'medium').trim(),

    ruleNumbers: rawRuleNumbers
        .map((entry) => entry.toString().trim())
        .where((entry) => entry.isNotEmpty)
        .toList(),

    ruleTitles: rawRuleTitles
        .map((entry) => entry.toString().trim())
        .where((entry) => entry.isNotEmpty)
        .toList(),

    legalBasis: (json['legalBasis'] as String?)?.trim().isNotEmpty == true
        ? (json['legalBasis'] as String).trim()
        : null,

    ocrEvidence: (json['ocrEvidence'] as String?)?.trim().isNotEmpty == true
        ? (json['ocrEvidence'] as String).trim()
        : null,

    verificationStatus: LegalVerificationStatus.fromValue(
      json['verificationStatus']?.toString(),
    ),
  );
}

  Map<String, dynamic> toJson() => {
      'title': title,
      'description': description,
      'severity': severity,

      'verificationStatus': verificationStatus.value,

      if (ruleNumbers.isNotEmpty) 'ruleNumbers': ruleNumbers,
      if (ruleTitles.isNotEmpty) 'ruleTitles': ruleTitles,

      if (legalBasis != null && legalBasis!.trim().isNotEmpty)
        'legalBasis': legalBasis,

      if (ocrEvidence != null && ocrEvidence!.trim().isNotEmpty)
        'ocrEvidence': ocrEvidence,
    };
}

class ComplianceAnalysis {
  const ComplianceAnalysis({
    required this.productName,
    required this.mrp,
    required this.netQuantity,
    required this.manufacturer,
    required this.address,
    required this.packingDate,
    required this.customerCare,
    required this.missingInformation,
    required this.possibleIssues,
  });

  final String productName;
  final String mrp;
  final String netQuantity;
  final String manufacturer;
  final String address;
  final String packingDate;
  final String customerCare;
  final List<String> missingInformation;
  final List<ComplianceIssue> possibleIssues;

  bool get isCompliant => possibleIssues.isEmpty && missingInformation.isEmpty;

  factory ComplianceAnalysis.fromJson(Map<String, dynamic> json) {
    final possibleIssuesJson = json['possibleIssues'] as List? ??
        (json['violations'] as List? ?? const []);

    return ComplianceAnalysis(
      productName: (json['productName'] as String? ?? '').trim(),
      mrp: (json['mrp'] as String? ?? '').trim(),
      netQuantity: (json['netQuantity'] as String? ?? '').trim(),
      manufacturer: (json['manufacturer'] as String? ?? '').trim(),
      address: (json['address'] as String? ??
              json['manufacturerAddress'] as String? ?? '').trim(),
      packingDate: (json['packingDate'] as String? ??
              json['dateOfManufacturePacking'] as String? ?? '').trim(),
      customerCare: (json['customerCare'] as String? ??
              json['customerCareDetails'] as String? ?? '').trim(),
      missingInformation: ((json['missingInformation'] as List?) ??
              (json['missingMandatoryDeclarations'] as List? ?? const []))
          .map((entry) => entry.toString().trim())
          .where((entry) => entry.isNotEmpty)
          .toList(),
      possibleIssues: possibleIssuesJson
          .map((entry) => ComplianceIssue.fromJson(Map<String, dynamic>.from(entry as Map)))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'productName': productName,
        'mrp': mrp,
        'netQuantity': netQuantity,
        'manufacturer': manufacturer,
        'address': address,
        'packingDate': packingDate,
        'customerCare': customerCare,
        'missingInformation': missingInformation,
        'possibleIssues': possibleIssues.map((entry) => entry.toJson()).toList(),
      };
}
