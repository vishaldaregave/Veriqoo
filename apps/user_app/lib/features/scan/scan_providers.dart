import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/model/scan_phase.dart';

/// Scan-session state — the **Phase 6 evidence-viewer hand-off seam**.
///
/// Holds the ordered, role-tagged [evidence] images captured during an
/// inspection, the latest live-OCR [liveOcrText] + [detectedFields], the
/// current [phase], and whether the analysis pipeline [isAnalyzing]. Phase 6
/// reads [evidence] (all images, with role/label/sequence) to drive the
/// evidence viewer; Phase 5 only ever passes the [primaryImage] into the
/// existing analysis + save pipeline, so `SupabaseService` is untouched.
///
/// Business logic (OCR, RAG, Gemini) stays in `shared_core`; this is pure
/// session state.
@immutable
class ScanState {
  const ScanState({
    this.evidence = const <EvidenceImage>[],
    this.currentIndex = 0,
    this.liveOcrText = '',
    this.detectedFields = const <DetectedField>[],
    this.phase = ScanPhase.positionProduct,
    this.isAnalyzing = false,
  });

  /// Ordered captured evidence (front, back, side, then additional).
  final List<EvidenceImage> evidence;

  /// Index of the tile currently highlighted in the evidence tray.
  final int currentIndex;

  /// Most recent live-OCR raw text.
  final String liveOcrText;

  /// Most recent live-OCR detected label regions.
  final List<DetectedField> detectedFields;

  /// Current live-scan phase.
  final ScanPhase phase;

  /// Whether the analysis pipeline is running.
  final bool isAnalyzing;

  /// The primary image passed to the analysis + save pipeline (first capture),
  /// or null when nothing has been captured yet.
  XFile? get primaryImage =>
      evidence.isEmpty ? null : evidence.first.file;

  /// The role the next capture should take, based on how many images exist.
  EvidenceRole get nextRole {
    switch (evidence.length) {
      case 0:
        return EvidenceRole.front;
      case 1:
        return EvidenceRole.back;
      case 2:
        return EvidenceRole.side;
      default:
        return EvidenceRole.additional;
    }
  }

  ScanState copyWith({
    List<EvidenceImage>? evidence,
    int? currentIndex,
    String? liveOcrText,
    List<DetectedField>? detectedFields,
    ScanPhase? phase,
    bool? isAnalyzing,
  }) {
    return ScanState(
      evidence: evidence ?? this.evidence,
      currentIndex: currentIndex ?? this.currentIndex,
      liveOcrText: liveOcrText ?? this.liveOcrText,
      detectedFields: detectedFields ?? this.detectedFields,
      phase: phase ?? this.phase,
      isAnalyzing: isAnalyzing ?? this.isAnalyzing,
    );
  }
}

/// Owns the [ScanState]. Keeps the public provider name/type stable so the
/// router and tests do not drift.
class ScanController extends Notifier<ScanState> {
  @override
  ScanState build() => const ScanState();

  EvidenceRole _roleForIndex(int index) {
    switch (index) {
      case 0:
        return EvidenceRole.front;
      case 1:
        return EvidenceRole.back;
      case 2:
        return EvidenceRole.side;
      default:
        return EvidenceRole.additional;
    }
  }

  /// Rebuilds the ordered evidence list from a list of files, re-assigning
  /// sequence (1-based) and auto-roles front/back/side/additional.
  List<EvidenceImage> _resequence(List<XFile> files) {
    return <EvidenceImage>[
      for (var i = 0; i < files.length; i++)
        EvidenceImage(
          file: files[i],
          role: _roleForIndex(i),
          sequence: i + 1,
          label: _roleForIndex(i).label,
        ),
    ];
  }

  /// Appends a captured/picked [file] as the next evidence image. The [role]
  /// is auto-assigned from position unless one is supplied; the new tile
  /// becomes the current selection.
  void addEvidence(XFile file, {EvidenceRole? role}) {
    final index = state.evidence.length;
    final resolvedRole = role ?? _roleForIndex(index);
    final image = EvidenceImage(
      file: file,
      role: resolvedRole,
      sequence: index + 1,
      label: resolvedRole.label,
    );
    state = state.copyWith(
      evidence: <EvidenceImage>[...state.evidence, image],
      currentIndex: index,
    );
  }

  /// Replaces the image at [index] with [file], preserving its role/sequence.
  void retakeAt(int index, XFile file) {
    if (index < 0 || index >= state.evidence.length) {
      return;
    }
    final updated = <EvidenceImage>[...state.evidence];
    updated[index] = updated[index].copyWith(file: file);
    state = state.copyWith(evidence: updated, currentIndex: index);
  }

  /// Removes the image at [index] and re-sequences the remaining images.
  void deleteAt(int index) {
    if (index < 0 || index >= state.evidence.length) {
      return;
    }
    final files = <XFile>[
      for (var i = 0; i < state.evidence.length; i++)
        if (i != index) state.evidence[i].file,
    ];
    final resequenced = _resequence(files);
    final nextIndex = resequenced.isEmpty
        ? 0
        : index.clamp(0, resequenced.length - 1);
    state = state.copyWith(evidence: resequenced, currentIndex: nextIndex);
  }

  /// Highlights the tile at [index].
  void setCurrent(int index) {
    if (index < 0 || index >= state.evidence.length) {
      return;
    }
    state = state.copyWith(currentIndex: index);
  }

  /// Stores the latest live-OCR output.
  void setLiveOcr(String text, List<DetectedField> fields) {
    state = state.copyWith(liveOcrText: text, detectedFields: fields);
  }

  /// Advances the live-scan phase via the pure [nextScanPhase] transition.
  void advancePhase({
    bool? capturing,
    bool? analyzing,
    bool complete = false,
  }) {
    final next = nextScanPhase(
      state.phase,
      detectedFieldCount: state.detectedFields.length,
      hasText: state.liveOcrText.trim().isNotEmpty,
      capturing: capturing ?? state.evidence.isNotEmpty,
      analyzing: analyzing ?? state.isAnalyzing,
      complete: complete,
    );
    if (next != state.phase) {
      state = state.copyWith(phase: next);
    }
  }

  /// Sets the analyzing flag and recomputes the phase.
  void setAnalyzing(bool value) {
    state = state.copyWith(isAnalyzing: value);
    advancePhase(analyzing: value);
  }

  /// Clears the whole session back to its initial state.
  void reset() => state = const ScanState();
}

final scanStateProvider =
    NotifierProvider<ScanController, ScanState>(ScanController.new);
