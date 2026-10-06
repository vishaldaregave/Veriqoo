import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_tokens.dart';

/// Visual weight of a [VeriqooIconButton].
///
/// * [ghost] — no border or fill (chrome actions).
/// * [outline] — hairline-bordered square.
enum VeriqooIconButtonVariant { ghost, outline }

/// A square, monochrome icon-only button with a guaranteed 44×44 tap target,
/// a Semantics label (required so it is announced), a visible focus ring, and
/// a no-overshoot press scale-down.
class VeriqooIconButton extends StatefulWidget {
  const VeriqooIconButton({
    super.key,
    required this.icon,
    required this.semanticLabel,
    this.onPressed,
    this.variant = VeriqooIconButtonVariant.ghost,
    this.iconSize = 20,
    this.size = 44,
  });

  /// Glyph to render (from `VeriqooIcons`).
  final IconData icon;

  /// Required accessibility label announced by screen readers.
  final String semanticLabel;

  /// Tap handler. When null the button is disabled.
  final VoidCallback? onPressed;

  /// Visual weight.
  final VeriqooIconButtonVariant variant;

  /// Glyph size in logical pixels.
  final double iconSize;

  /// Square target size (minimum 44 enforced).
  final double size;

  bool get _enabled => onPressed != null;

  @override
  State<VeriqooIconButton> createState() => _VeriqooIconButtonState();
}

class _VeriqooIconButtonState extends State<VeriqooIconButton> {
  bool _pressed = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final enabled = widget._enabled;
    final side = widget.size < 44 ? 44.0 : widget.size;

    final border = widget.variant == VeriqooIconButtonVariant.outline
        ? Border.all(color: tokens.borderStrong, width: 1)
        : null;

    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.semanticLabel,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: enabled ? widget.onPressed : null,
        onTapDown: enabled ? (_) => setState(() => _pressed = true) : null,
        onTapUp: enabled ? (_) => setState(() => _pressed = false) : null,
        onTapCancel: enabled ? () => setState(() => _pressed = false) : null,
        child: FocusableActionDetector(
          enabled: enabled,
          onShowFocusHighlight: (value) => setState(() => _focused = value),
          actions: <Type, Action<Intent>>{
            ActivateIntent: CallbackAction<ActivateIntent>(
              onInvoke: (_) {
                widget.onPressed?.call();
                return null;
              },
            ),
          },
          child: AnimatedScale(
            scale: _pressed && enabled ? 0.92 : 1,
            duration: VeriqooMotion.fast,
            curve: VeriqooMotion.press,
            child: AnimatedOpacity(
              opacity: enabled ? 1 : 0.4,
              duration: VeriqooMotion.fast,
              child: Container(
                width: side,
                height: side,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  borderRadius: VeriqooRadius.smAll,
                  border: Border.all(
                    color: _focused && enabled
                        ? tokens.textPrimary
                        : Colors.transparent,
                    width: 2,
                  ),
                ),
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: VeriqooRadius.smAll,
                    border: border,
                  ),
                  width: side - 4,
                  height: side - 4,
                  alignment: Alignment.center,
                  child: Icon(
                    widget.icon,
                    size: widget.iconSize,
                    color: tokens.textPrimary,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
