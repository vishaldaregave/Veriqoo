import 'package:flutter/material.dart';

import '../theme/veriqoo_motion.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A monochrome single-line text field with a hairline underline that animates
/// (via [VeriqooMotion]) to a stronger line on focus. Supports an optional
/// [label], helper/[errorText] messaging, and exposes the label to Semantics.
class VeriqooTextField extends StatefulWidget {
  const VeriqooTextField({
    super.key,
    this.controller,
    this.label,
    this.hintText,
    this.helperText,
    this.errorText,
    this.obscureText = false,
    this.keyboardType,
    this.textInputAction,
    this.enabled = true,
    this.onChanged,
    this.onSubmitted,
    this.focusNode,
    this.prefixIcon,
    this.suffixIcon,
  });

  final TextEditingController? controller;

  /// Field label rendered above the input and announced via Semantics.
  final String? label;

  final String? hintText;

  /// Helper copy shown below the field when there is no [errorText].
  final String? helperText;

  /// Error copy shown below the field; when set the field enters its error
  /// state (stronger underline + error text).
  final String? errorText;

  final bool obscureText;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final bool enabled;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final FocusNode? focusNode;
  final IconData? prefixIcon;
  final IconData? suffixIcon;

  @override
  State<VeriqooTextField> createState() => _VeriqooTextFieldState();
}

class _VeriqooTextFieldState extends State<VeriqooTextField> {
  FocusNode? _ownNode;
  bool _focused = false;

  FocusNode get _node => widget.focusNode ?? (_ownNode ??= FocusNode());

  @override
  void initState() {
    super.initState();
    _node.addListener(_onFocusChange);
  }

  void _onFocusChange() {
    if (_focused != _node.hasFocus) {
      setState(() => _focused = _node.hasFocus);
    }
  }

  @override
  void dispose() {
    _node.removeListener(_onFocusChange);
    _ownNode?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final hasError = widget.errorText != null;

    final Color underlineColor;
    if (hasError) {
      underlineColor = tokens.textPrimary;
    } else if (_focused) {
      underlineColor = tokens.textPrimary;
    } else {
      underlineColor = tokens.borderHairline;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (widget.label != null) ...[
          Text(
            widget.label!.toUpperCase(),
            style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
          ),
          const SizedBox(height: VeriqooSpacing.s8),
        ],
        Semantics(
          textField: true,
          label: widget.label,
          child: Row(
            children: [
              if (widget.prefixIcon != null) ...[
                Icon(widget.prefixIcon,
                    size: 18, color: tokens.textSecondary),
                const SizedBox(width: VeriqooSpacing.s12),
              ],
              Expanded(
                child: TextField(
                  controller: widget.controller,
                  focusNode: _node,
                  enabled: widget.enabled,
                  obscureText: widget.obscureText,
                  keyboardType: widget.keyboardType,
                  textInputAction: widget.textInputAction,
                  onChanged: widget.onChanged,
                  onSubmitted: widget.onSubmitted,
                  cursorColor: tokens.textPrimary,
                  style: VeriqooType.bodyL.copyWith(color: tokens.textPrimary),
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: widget.hintText,
                    hintStyle: VeriqooType.bodyL
                        .copyWith(color: tokens.textTertiary),
                    contentPadding: const EdgeInsets.symmetric(
                      vertical: VeriqooSpacing.s12,
                    ),
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    errorBorder: InputBorder.none,
                    focusedErrorBorder: InputBorder.none,
                    disabledBorder: InputBorder.none,
                  ),
                ),
              ),
              if (widget.suffixIcon != null) ...[
                const SizedBox(width: VeriqooSpacing.s12),
                Icon(widget.suffixIcon,
                    size: 18, color: tokens.textSecondary),
              ],
            ],
          ),
        ),
        // Animated focus underline.
        AnimatedContainer(
          duration: VeriqooMotion.fast,
          curve: VeriqooMotion.move,
          height: (_focused || hasError) ? 2 : 1,
          color: underlineColor,
        ),
        if (widget.errorText != null || widget.helperText != null) ...[
          const SizedBox(height: VeriqooSpacing.s8),
          Text(
            widget.errorText ?? widget.helperText!,
            style: VeriqooType.caption.copyWith(
              color: hasError ? tokens.textPrimary : tokens.textSecondary,
              fontWeight: hasError ? FontWeight.w600 : FontWeight.w400,
            ),
          ),
        ],
      ],
    );
  }
}
