import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

/// Facade over the raw Lucide icon set.
///
/// This is the ONLY file in the design system that imports the icon package
/// directly. Every component references icons through [VeriqooIcons], so
/// swapping the underlying package (e.g. to `phosphor_flutter`) is a
/// single-file change. All glyphs are monochrome line icons.
abstract final class VeriqooIcons {
  const VeriqooIcons._();

  // Primary navigation destinations.
  static const IconData home = LucideIcons.house;
  static const IconData scan = LucideIcons.scanLine;
  static const IconData history = LucideIcons.history;
  static const IconData profile = LucideIcons.user;

  // Navigation / chrome.
  static const IconData back = LucideIcons.arrowLeft;
  static const IconData close = LucideIcons.x;
  static const IconData chevronRight = LucideIcons.chevronRight;
  static const IconData settings = LucideIcons.settings;
  static const IconData search = LucideIcons.search;

  // Status / feedback.
  static const IconData check = LucideIcons.check;
  static const IconData alert = LucideIcons.triangleAlert;
  static const IconData verified = LucideIcons.circleCheck;
  static const IconData violation = LucideIcons.circleX;

  // Capture / input.
  static const IconData camera = LucideIcons.camera;
  static const IconData upload = LucideIcons.upload;

  // Report actions / evidence (Phase 6 — additive, no removals/renames).
  static const IconData share = LucideIcons.share;
  static const IconData qrCode = LucideIcons.qrCode;
  static const IconData flag = LucideIcons.flag;
  static const IconData eye = LucideIcons.eye;
  static const IconData zoomIn = LucideIcons.zoomIn;
  static const IconData shield = LucideIcons.shield;

  // History / search (Phase 7 — additive, no removals/renames).
  static const IconData filter = LucideIcons.filter;
  static const IconData sort = LucideIcons.arrowUpDown;
  static const IconData calendar = LucideIcons.calendar;
  static const IconData package = LucideIcons.package;

  // Profile / settings / notifications (Phase 8 — additive, no removals/
  // renames). "user" is intentionally omitted — it is already exposed as
  // [profile] above.
  static const IconData notifications = LucideIcons.bell;
  static const IconData language = LucideIcons.globe;
  static const IconData privacy = LucideIcons.lock;
  static const IconData help = LucideIcons.circleHelp;
  static const IconData logout = LucideIcons.logOut;
}
