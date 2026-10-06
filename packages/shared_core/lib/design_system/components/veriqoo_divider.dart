import 'package:flutter/material.dart';

import '../theme/veriqoo_tokens.dart';

/// A single hairline separator drawn with the [VeriqooTokens.borderHairline]
/// token. Supports horizontal (default) and vertical orientations.
class VeriqooDivider extends StatelessWidget {
  const VeriqooDivider({
    super.key,
    this.height,
    this.indent = 0,
    this.endIndent = 0,
  }) : _vertical = false;

  /// A vertical hairline, for separating inline content.
  const VeriqooDivider.vertical({
    super.key,
    this.height,
    this.indent = 0,
    this.endIndent = 0,
  }) : _vertical = true;

  final bool _vertical;

  /// Extent of the divider's cross axis including surrounding space.
  final double? height;

  /// Leading gap before the line starts.
  final double indent;

  /// Trailing gap after the line ends.
  final double endIndent;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    if (_vertical) {
      return Padding(
        padding: EdgeInsets.only(top: indent, bottom: endIndent),
        child: SizedBox(
          width: height ?? 1,
          child: Center(
            child: Container(width: 1, color: tokens.borderHairline),
          ),
        ),
      );
    }
    return Padding(
      padding: EdgeInsets.only(left: indent, right: endIndent),
      child: SizedBox(
        height: height ?? 1,
        child: Center(
          child: Container(height: 1, color: tokens.borderHairline),
        ),
      ),
    );
  }
}
