import 'package:flutter/widgets.dart';

/// VERIQOO corner-radius scale plus [BorderRadius] helpers.
///
/// Radius is applied deliberately, not universally:
/// * [none] — reports, tables, technical panels, status chips.
/// * [sm] — inputs, buttons, nav items.
/// * [md] — sheets and small modals.
/// * [lg] — hero and auth surfaces only.
abstract final class VeriqooRadius {
  const VeriqooRadius._();

  static const double none = 0;
  static const double sm = 6;
  static const double md = 10;
  static const double lg = 20;

  static const BorderRadius noneAll = BorderRadius.zero;
  static const BorderRadius smAll = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius mdAll = BorderRadius.all(Radius.circular(md));
  static const BorderRadius lgAll = BorderRadius.all(Radius.circular(lg));

  /// Rounds only the top corners (e.g. bottom sheets) at [radius].
  static BorderRadius top(double radius) => BorderRadius.vertical(
        top: Radius.circular(radius),
      );
}
