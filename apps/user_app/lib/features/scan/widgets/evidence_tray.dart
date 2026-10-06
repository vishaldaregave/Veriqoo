import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/model/evidence_image.dart';

/// Stable keys for the evidence tray (used by widget tests).
const Key kEvidenceTrayKey = Key('evidence-tray');
const Key kEvidenceAddTileKey = Key('evidence-add-tile');

Key evidenceTileKey(int index) => Key('evidence-tile-$index');
Key evidenceRetakeKey(int index) => Key('evidence-retake-$index');
Key evidenceDeleteKey(int index) => Key('evidence-delete-$index');

/// Horizontal thumbnail strip of captured evidence, with a trailing `+ Add`
/// tile. Feels like evidence collection: numbered `01/02/03`, current capture
/// highlighted, with retake / delete per tile. The screen owns the camera /
/// picker side effects via the callbacks.
class EvidenceTray extends StatelessWidget {
  const EvidenceTray({
    super.key,
    required this.evidence,
    required this.currentIndex,
    required this.onSelect,
    required this.onRetake,
    required this.onDelete,
    required this.onAdd,
  });

  final List<EvidenceImage> evidence;
  final int currentIndex;
  final ValueChanged<int> onSelect;
  final ValueChanged<int> onRetake;
  final ValueChanged<int> onDelete;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 96,
      child: ListView.separated(
        key: kEvidenceTrayKey,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s16),
        itemCount: evidence.length + 1,
        separatorBuilder: (_, __) =>
            const SizedBox(width: VeriqooSpacing.s12),
        itemBuilder: (context, index) {
          if (index == evidence.length) {
            return _AddTile(onAdd: onAdd);
          }
          return _EvidenceTile(
            key: evidenceTileKey(index),
            image: evidence[index],
            selected: index == currentIndex,
            onSelect: () => onSelect(index),
            onRetake: () => onRetake(index),
            onDelete: () => onDelete(index),
          );
        },
      ),
    );
  }
}

class _EvidenceTile extends StatelessWidget {
  const _EvidenceTile({
    super.key,
    required this.image,
    required this.selected,
    required this.onSelect,
    required this.onRetake,
    required this.onDelete,
  });

  final EvidenceImage image;
  final bool selected;
  final VoidCallback onSelect;
  final VoidCallback onRetake;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return GestureDetector(
      onTap: onSelect,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 76,
        decoration: BoxDecoration(
          color: tokens.bgTrue,
          border: Border.all(
            color: selected ? tokens.borderStrong : tokens.borderHairline,
            width: selected ? 2 : 1,
          ),
        ),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Thumbnail.
            FutureBuilder<Uint8List>(
              future: image.file.readAsBytes(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Center(
                    child: FittedBox(
                      fit: BoxFit.contain,
                      child: SizedBox(
                        width: 64,
                        height: 56,
                        child: VeriqooLoading(
                          message: '',
                          size: Size(56, 40),
                        ),
                      ),
                    ),
                  );
                }
                return Image.memory(
                  snapshot.data!,
                  fit: BoxFit.cover,
                );
              },
            ),
            // Sequence badge + role label.
            Positioned(
              left: 2,
              top: 2,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
                color: tokens.bgTrue.withValues(alpha: 0.7),
                child: Text(
                  image.twoDigit,
                  style: VeriqooType.meta.copyWith(
                    color: tokens.textTertiary,
                    fontSize: 9,
                  ),
                ),
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: Container(
                color: tokens.bgTrue.withValues(alpha: 0.7),
                padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
                child: Text(
                  image.label.toUpperCase(),
                  overflow: TextOverflow.ellipsis,
                  style: VeriqooType.meta.copyWith(
                    color: tokens.textSecondary,
                    fontSize: 8,
                  ),
                ),
              ),
            ),
            // Retake + delete controls.
            Positioned(
              right: 0,
              top: 0,
              child: Row(
                children: [
                  VeriqooIconButton(
                    key: evidenceRetakeKey(image.sequence - 1),
                    icon: VeriqooIcons.history,
                    semanticLabel: 'Retake ${image.label}',
                    onPressed: onRetake,
                    iconSize: 12,
                    size: 24,
                  ),
                  VeriqooIconButton(
                    key: evidenceDeleteKey(image.sequence - 1),
                    icon: VeriqooIcons.close,
                    semanticLabel: 'Delete ${image.label}',
                    onPressed: onDelete,
                    iconSize: 12,
                    size: 24,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddTile extends StatelessWidget {
  const _AddTile({required this.onAdd});

  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return GestureDetector(
      key: kEvidenceAddTileKey,
      onTap: onAdd,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 76,
        decoration: BoxDecoration(
          color: tokens.surface,
          border: Border.all(color: tokens.borderHairline, width: 1),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(VeriqooIcons.camera, size: 20, color: tokens.textSecondary),
            const SizedBox(height: VeriqooSpacing.s4),
            Text(
              '+ ADD',
              style: VeriqooType.meta.copyWith(
                color: tokens.textTertiary,
                fontSize: 9,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
