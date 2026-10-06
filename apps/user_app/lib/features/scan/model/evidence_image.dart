import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

/// The role a captured evidence image plays in an inspection.
///
/// The first three captures are auto-assigned [front], [back], then [side];
/// any further captures are [additional]. The ordering drives the
/// auto-sequencing in `ScanController.addEvidence`.
enum EvidenceRole { front, back, side, additional }

/// Human-facing label for an [EvidenceRole].
extension EvidenceRoleLabel on EvidenceRole {
  /// Short label shown on evidence-tray tiles and the add affordance.
  String get label {
    switch (this) {
      case EvidenceRole.front:
        return 'Front';
      case EvidenceRole.back:
        return 'Back';
      case EvidenceRole.side:
        return 'Side';
      case EvidenceRole.additional:
        return '+ Add';
    }
  }
}

/// A single captured evidence image plus its inspection metadata.
///
/// Immutable; the ordered list of these on `ScanState.evidence` is the Phase 6
/// evidence-viewer hand-off. [file] is the underlying [XFile] (camera capture
/// or gallery pick); [sequence] is 1-based and [twoDigit] renders it as
/// `01/02/03` for the tray.
@immutable
class EvidenceImage {
  const EvidenceImage({
    required this.file,
    required this.role,
    required this.sequence,
    required this.label,
  });

  /// The captured/picked image file.
  final XFile file;

  /// The role this image plays (front/back/side/additional).
  final EvidenceRole role;

  /// 1-based capture order.
  final int sequence;

  /// Display label (defaults to the role label, but kept explicit so Phase 6
  /// can rename an image without reassigning its role).
  final String label;

  /// Zero-padded sequence for the tray badge, e.g. `01`, `02`, `03`.
  String get twoDigit => sequence.toString().padLeft(2, '0');

  EvidenceImage copyWith({
    XFile? file,
    EvidenceRole? role,
    int? sequence,
    String? label,
  }) {
    return EvidenceImage(
      file: file ?? this.file,
      role: role ?? this.role,
      sequence: sequence ?? this.sequence,
      label: label ?? this.label,
    );
  }
}
