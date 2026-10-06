import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_elevation.dart';
import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A single destination in a [VeriqooNavigationBar].
@immutable
class VeriqooNavigationDestination {
  const VeriqooNavigationDestination({
    required this.icon,
    required this.label,
    this.emphasized = false,
  });

  /// Monochrome line icon (from `VeriqooIcons`).
  final IconData icon;

  /// Short label, also used as the Semantics label.
  final String label;

  /// When true the destination is visually emphasized (e.g. Scan).
  final bool emphasized;

  /// The four default VERIQOO destinations: Home, Scan (emphasized), History,
  /// Profile.
  static const List<VeriqooNavigationDestination> defaults =
      <VeriqooNavigationDestination>[
    VeriqooNavigationDestination(icon: VeriqooIcons.home, label: 'Home'),
    VeriqooNavigationDestination(
        icon: VeriqooIcons.scan, label: 'Scan', emphasized: true),
    VeriqooNavigationDestination(
        icon: VeriqooIcons.history, label: 'History'),
    VeriqooNavigationDestination(
        icon: VeriqooIcons.profile, label: 'Profile'),
  ];
}

/// A floating, monochrome bottom navigation bar.
///
/// Uses the single permitted [VeriqooElevation.softShadow], a radius-sm
/// container, line icons, and a subtle active indicator (no color). The Scan
/// destination can be emphasized. Each item is a 44×44 min target with a
/// Semantics label and visible focus.
class VeriqooNavigationBar extends StatelessWidget {
  const VeriqooNavigationBar({
    super.key,
    required this.currentIndex,
    required this.onDestinationSelected,
    this.destinations = VeriqooNavigationDestination.defaults,
  });

  /// Index of the active destination.
  final int currentIndex;

  /// Called with the tapped destination index.
  final ValueChanged<int> onDestinationSelected;

  /// Destinations to render (defaults to the four standard destinations).
  final List<VeriqooNavigationDestination> destinations;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          VeriqooSpacing.s16,
          0,
          VeriqooSpacing.s16,
          VeriqooSpacing.s16,
        ),
        child: Container(
          decoration: BoxDecoration(
            color: tokens.surfaceRaised,
            borderRadius: VeriqooRadius.smAll,
            border: Border.all(color: tokens.borderHairline, width: 1),
            boxShadow: VeriqooElevation.softShadow,
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: VeriqooSpacing.s8,
            vertical: VeriqooSpacing.s8,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (var i = 0; i < destinations.length; i++)
                Expanded(
                  child: _NavItem(
                    destination: destinations[i],
                    selected: i == currentIndex,
                    onTap: () => onDestinationSelected(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatefulWidget {
  const _NavItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final VeriqooNavigationDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_NavItem> createState() => _NavItemState();
}

class _NavItemState extends State<_NavItem> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final d = widget.destination;
    final active = widget.selected;

    final iconColor =
        active ? tokens.textPrimary : tokens.textSecondary;

    Widget icon = Icon(d.icon, size: 22, color: iconColor);
    if (d.emphasized) {
      icon = Container(
        width: 36,
        height: 36,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: active ? tokens.inverseBg : Colors.transparent,
          borderRadius: VeriqooRadius.smAll,
          border: Border.all(color: tokens.borderStrong, width: 1),
        ),
        child: Icon(
          d.icon,
          size: 20,
          color: active ? tokens.inverseText : tokens.textPrimary,
        ),
      );
    }

    return Semantics(
      button: true,
      selected: active,
      label: d.label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: FocusableActionDetector(
          onShowFocusHighlight: (v) => setState(() => _focused = v),
          actions: <Type, Action<Intent>>{
            ActivateIntent: CallbackAction<ActivateIntent>(
              onInvoke: (_) {
                widget.onTap();
                return null;
              },
            ),
          },
          child: Container(
            constraints: const BoxConstraints(minHeight: 44),
            padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s4),
            decoration: BoxDecoration(
              borderRadius: VeriqooRadius.smAll,
              border: Border.all(
                color: _focused ? tokens.textPrimary : Colors.transparent,
                width: 2,
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                icon,
                const SizedBox(height: VeriqooSpacing.s4),
                Text(
                  d.label.toUpperCase(),
                  style: VeriqooType.meta.copyWith(
                    color: iconColor,
                    fontSize: 9,
                    letterSpacing: 0.8,
                  ),
                ),
                const SizedBox(height: 3),
                // Subtle monochrome active indicator (no color).
                AnimatedContainer(
                  duration: VeriqooMotion.fast,
                  curve: VeriqooMotion.move,
                  height: 2,
                  width: active ? 16 : 0,
                  color: tokens.textPrimary,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
