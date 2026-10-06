import 'package:flutter/foundation.dart';

import 'package:flutter_application_1/features/scan/result/report_finding.dart';

/// Arguments passed to the Evidence Viewer via GoRouter `extra`.
///
/// Both fields are optional so the report-level "VIEW EVIDENCE" action can open
/// the viewer with no particular focus (`const EvidenceViewerArgs()`), while a
/// finding's "View evidence"/"Inspect" supplies the image to open on and the
/// [focusFinding] to zoom toward.
@immutable
class EvidenceViewerArgs {
  const EvidenceViewerArgs({
    this.initialImageIndex = 0,
    this.focusFinding,
  });

  /// Index into `scanState.evidence` to open on.
  final int initialImageIndex;

  /// The finding to zoom/explain, when launched from a finding tile.
  final ReportFinding? focusFinding;
}
