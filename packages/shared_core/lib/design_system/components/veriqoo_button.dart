import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// Visual weight of a [VeriqooButton].
///
/// * [primary] — solid inverse fill (highest emphasis).
/// * [secondary] — hairline outline on a transparent surface.
/// * [ghost] — text only, no border or fill.
enum VeriqooButtonVariant { primary, secondary, ghost }

/// Height/padding scale for a [VeriqooButton]. Every size keeps a 44px minimum
/// tap target.
enum VeriqooButtonSize { small, medium, large }

/// A monochrome VERIQOO button.
///
/// Pressing scales the button down slightly using [VeriqooMotion.press] (a
/// no-overshoot curve). Supports [disabled] and [loading] states, exposes a
/// Semantics button label, and shows a visible focus ring. The tap target is
/// never smaller than 44×44.
class VeriqooButton extends StatefulWidget {
  const VeriqooButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = VeriqooButtonVariant.primary,
    this.size = VeriqooButtonSize.medium,
    this.icon,
    this.loading = false,
    this.expand = false,
    this.semanticLabel,
  });

  /// Button text.
  final String label;

  /// Tap handler. When null (and not [loading]) the button is disabled.
  final VoidCallback? onPressed;

  /// Visual weight.
  final VeriqooButtonVariant variant;

  /// Size step.
  final VeriqooButtonSize size;

  /// Optional leading icon.
  final IconData? icon;

  /// When true a progress indicator replaces the content and taps are ignored.
  final bool loading;

  /// When true the button stretches to the full available width.
  final bool expand;

  /// Overrides the announced Semantics label (defaults to [label]).
  final String? semanticLabel;

  bool get _enabled => onPressed != null && !loading;

  @override
  State<VeriqooButton> createState() => _VeriqooButtonState();
}

class _VeriqooButtonState extends State<VeriqooButton> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (_pressed != value) {
      setState(() => _pressed = value);
    }
  }

  double get _height {
    switch (widget.size) {
      case VeriqooButtonSize.small:
        return 44;
      case VeriqooButtonSize.medium:
        return 48;
      case VeriqooButtonSize.large:
        return 56;
    }
  }

  EdgeInsets get _padding {
    switch (widget.size) {
      case VeriqooButtonSize.small:
        return const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s16);
      case VeriqooButtonSize.medium:
        return const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s24);
      case VeriqooButtonSize.large:
        return const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s32);
    }
  }

  double get _iconSize {
    switch (widget.size) {
      case VeriqooButtonSize.small:
        return 16;
      case VeriqooButtonSize.medium:
        return 18;
      case VeriqooButtonSize.large:
        return 20;
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final enabled = widget._enabled;

    final Color foreground;
    final Color background;
    final Color borderColor;
    switch (widget.variant) {
      case VeriqooButtonVariant.primary:
        foreground = tokens.inverseText;
        background = tokens.inverseBg;
        borderColor = Colors.transparent;
      case VeriqooButtonVariant.secondary:
        foreground = tokens.textPrimary;
        background = Colors.transparent;
        borderColor = tokens.borderStrong;
      case VeriqooButtonVariant.ghost:
        foreground = tokens.textPrimary;
        background = Colors.transparent;
        borderColor = Colors.transparent;
    }

    final content = widget.loading
        ? SizedBox(
            width: _iconSize,
            height: _iconSize,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(foreground),
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.icon != null) ...[
                Icon(widget.icon, size: _iconSize, color: foreground),
                const SizedBox(width: VeriqooSpacing.s8),
              ],
              Flexible(
                child: Text(
                  widget.label,
                  overflow: TextOverflow.ellipsis,
                  style: VeriqooType.body.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          );

    Widget button = AnimatedScale(
      scale: _pressed && enabled ? 0.97 : 1,
      duration: VeriqooMotion.fast,
      curve: VeriqooMotion.press,
      child: AnimatedOpacity(
        opacity: enabled ? 1 : 0.4,
        duration: VeriqooMotion.fast,
        child: Container(
          height: _height,
          width: widget.expand ? double.infinity : null,
          padding: _padding,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: background,
            borderRadius: VeriqooRadius.smAll,
            border: Border.all(
              color: borderColor,
              width: 1,
            ),
          ),
          child: content,
        ),
      ),
    );

    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.semanticLabel ?? widget.label,
      child: _VeriqooFocusTap(
        enabled: enabled,
        borderRadius: VeriqooRadius.smAll,
        onTap: widget.onPressed,
        onHighlightChanged: _setPressed,
        child: button,
      ),
    );
  }
}

/// Internal gesture + focus wrapper shared by the button variants: provides a
/// visible focus ring, keyboard activation, and press-highlight callbacks
/// without the Material ink splash.
class _VeriqooFocusTap extends StatefulWidget {
  const _VeriqooFocusTap({
    required this.child,
    required this.enabled,
    required this.borderRadius,
    required this.onTap,
    required this.onHighlightChanged,
  });

  final Widget child;
  final bool enabled;
  final BorderRadius borderRadius;
  final VoidCallback? onTap;
  final ValueChanged<bool> onHighlightChanged;

  @override
  State<_VeriqooFocusTap> createState() => _VeriqooFocusTapState();
}

class _VeriqooFocusTapState extends State<_VeriqooFocusTap> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return GestureDetector(
      onTap: widget.enabled ? widget.onTap : null,
      onTapDown:
          widget.enabled ? (_) => widget.onHighlightChanged(true) : null,
      onTapUp: widget.enabled ? (_) => widget.onHighlightChanged(false) : null,
      onTapCancel:
          widget.enabled ? () => widget.onHighlightChanged(false) : null,
      behavior: HitTestBehavior.opaque,
      child: FocusableActionDetector(
        enabled: widget.enabled,
        onShowFocusHighlight: (value) => setState(() => _focused = value),
        actions: <Type, Action<Intent>>{
          ActivateIntent: CallbackAction<ActivateIntent>(
            onInvoke: (_) {
              widget.onTap?.call();
              return null;
            },
          ),
        },
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: widget.borderRadius,
            border: Border.all(
              color: _focused && widget.enabled
                  ? tokens.textPrimary
                  : Colors.transparent,
              width: 2,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(2),
            child: widget.child,
          ),
        ),
      ),
    );
  }
}
