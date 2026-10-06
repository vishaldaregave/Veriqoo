import 'package:flutter/material.dart';

/// Professional Theme Palette for VERIQOO Legal Metrology & Consumer Protection.
///
/// Tailored exactly to match the official Veriqoo UI design board:
/// Deep forest greens, clean white surfaces, emerald compliance accents,
/// amber warnings, and crisp typography.
abstract final class ProPalette {
  const ProPalette._();

  // Signature Brand Tones
  static const Color primaryForest = Color(0xFF0E3326); // Hero & primary buttons
  static const Color forestCardDark = Color(0xFF133E30);
  static const Color forestDeepDark = Color(0xFF071913); // Splash & cinematic dark
  static const Color forestWatermark = Color(0xFF164233);
  static const Color electricBlue = Color(0xFF2563EB);
  static const Color aiIndigo = Color(0xFF6366F1);

  // Status & Compliance Accents
  static const Color accentEmerald = Color(0xFF10B981);
  static const Color emeraldVerified = Color(0xFF10B981); // Emerald checkmark
  static const Color emeraldText = Color(0xFF15803D); // Green text
  static const Color emeraldBg = Color(0xFFDCFCE7); // Light green pill fill

  static const Color amberWarning = Color(0xFFD97706); // Amber warning
  static const Color amberBg = Color(0xFFFEF3C7); // Light amber pill fill
  static const Color amberNote = Color(0xFFFFFBEB); // Processing card amber

  static const Color crimsonViolation = Color(0xFFDC2626); // Red issue
  static const Color crimsonBg = Color(0xFFFEE2E2); // Light red pill fill

  static const Color purpleAct = Color(0xFF7E22CE); // Legal Metrology Act purple
  static const Color purpleBg = Color(0xFFF3E8FF);

  static const Color blueStandard = Color(0xFF0369A1); // BIS standards blue
  static const Color blueBg = Color(0xFFE0F2FE);

  // Clean Neutral Surfaces (Light Mode)
  static const Color background = Color(0xFFF9FAFB);
  static const Color cardSurface = Colors.white;
  static const Color cardBorder = Color(0xFFE5E7EB);
  static const Color cardBorderSubtle = Color(0xFFF0F0EE);
  static const Color textHeading = Color(0xFF111827);
  static const Color textMuted = Color(0xFF6B7280);
  static const Color textTertiary = Color(0xFF9CA3AF);

  // Dark Mode Fallbacks
  static const Color darkBackground = Color(0xFF0A0F0D);
  static const Color darkCardSurface = Color(0xFF121B17);
  static const Color darkCardBorder = Color(0xFF1E2D27);

  // Surface Compatibility
  static const Color lightSurface = Colors.white;
  static const Color darkSurface = Color(0xFF1E293B);

  /// Standard card decoration matching the clean rounded aesthetic in the mockup.
  static BoxDecoration cardDecoration(
    BuildContext context, {
    Color? color,
    Color? borderColor,
    Color? accentBorder,
    double radius = 16,
    bool elevated = false,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return BoxDecoration(
      color: color ?? (isDark ? darkCardSurface : cardSurface),
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(
        color: accentBorder ?? borderColor ?? (isDark ? darkCardBorder : cardBorder),
        width: 1.0,
      ),
      boxShadow: elevated
          ? [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.25 : 0.04),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ]
          : null,
    );
  }

  /// Badge decoration helper for consumer protection status indicators.
  static BoxDecoration badgeDecoration({
    Color color = const Color(0xFF10B981),
    double radius = 20,
  }) {
    return BoxDecoration(
      color: color.withValues(alpha: 0.12),
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: color.withValues(alpha: 0.3)),
    );
  }



  /// Compliance status badge pill builder
  static Widget statusPill(
    String label, {
    required StatusBadgeType type,
    bool showCheck = false,
  }) {
    Color bg;
    Color fg;
    IconData? icon;

    switch (type) {
      case StatusBadgeType.compliant:
        bg = emeraldBg;
        fg = emeraldText;
        if (showCheck) icon = Icons.check;
        break;
      case StatusBadgeType.minorIssue:
      case StatusBadgeType.suggestion:
        bg = amberBg;
        fg = amberWarning;
        break;
      case StatusBadgeType.nonCompliant:
      case StatusBadgeType.issue:
        bg = crimsonBg;
        fg = crimsonViolation;
        break;
      case StatusBadgeType.neutral:
        bg = const Color(0xFFF3F4F6);
        fg = textMuted;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: fg,
            ),
          ),
        ],
      ),
    );
  }
}

enum StatusBadgeType {
  compliant,
  minorIssue,
  nonCompliant,
  suggestion,
  issue,
  neutral,
}
