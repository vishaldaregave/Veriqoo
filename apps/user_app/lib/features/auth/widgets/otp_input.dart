import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_core/design_system/design_system.dart';

/// A segmented one-time-code input rendered as [length] monospace cells.
///
/// There is a single backing [TextField] (transparent, overlaid on the cells),
/// so auto-advance and clipboard paste work by construction — typing or pasting
/// digits simply fills the cells left to right, and deleting walks back. Input
/// is restricted to digits and capped at [length]. [onChanged] fires on every
/// edit and [onCompleted] fires once the full code is entered (it does NOT
/// submit — the hosting screen owns verification).
class OtpInput extends StatefulWidget {
  const OtpInput({
    super.key,
    this.length = 6,
    required this.onChanged,
    this.onCompleted,
    this.enabled = true,
    this.autofocus = true,
  });

  /// Number of cells / code length.
  final int length;

  /// Fires on every edit with the current (possibly partial) code.
  final ValueChanged<String> onChanged;

  /// Fires once when the code reaches [length]. Does not auto-submit.
  final ValueChanged<String>? onCompleted;

  final bool enabled;
  final bool autofocus;

  @override
  State<OtpInput> createState() => _OtpInputState();
}

class _OtpInputState extends State<OtpInput> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  int _lastReported = -1;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_handleChange);
    _focusNode.addListener(_handleFocus);
  }

  void _handleChange() {
    setState(() {});
    final text = _controller.text;
    widget.onChanged(text);
    if (text.length == widget.length && _lastReported != text.length) {
      widget.onCompleted?.call(text);
    }
    _lastReported = text.length;
  }

  void _handleFocus() => setState(() {});

  @override
  void dispose() {
    _controller.removeListener(_handleChange);
    _focusNode.removeListener(_handleFocus);
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    return Stack(
      children: [
        Row(
          children: [
            for (var i = 0; i < widget.length; i++) ...[
              if (i > 0) const SizedBox(width: VeriqooSpacing.s8),
              Expanded(child: _cell(i, tokens)),
            ],
          ],
        ),
        // The real input, overlaid and visually transparent: taps anywhere
        // focus it, and the cells above mirror its value.
        Positioned.fill(
          child: TextField(
            controller: _controller,
            focusNode: _focusNode,
            enabled: widget.enabled,
            autofocus: widget.autofocus,
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.done,
            showCursor: false,
            enableInteractiveSelection: false,
            style: const TextStyle(color: Colors.transparent, height: 1),
            cursorColor: Colors.transparent,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(widget.length),
            ],
            decoration: const InputDecoration(
              counterText: '',
              contentPadding: EdgeInsets.zero,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              disabledBorder: InputBorder.none,
            ),
          ),
        ),
      ],
    );
  }

  Widget _cell(int index, VeriqooTokens tokens) {
    final text = _controller.text;
    final hasChar = index < text.length;
    final char = hasChar ? text[index] : '';
    final isActive = _focusNode.hasFocus &&
        (index == text.length ||
            (text.length == widget.length && index == widget.length - 1));

    return AnimatedContainer(
      duration: VeriqooMotion.fast,
      curve: VeriqooMotion.move,
      height: 56,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: tokens.surface,
        borderRadius: VeriqooRadius.smAll,
        border: Border.all(
          color: isActive ? tokens.borderStrong : tokens.borderHairline,
          width: isActive ? 2 : 1,
        ),
      ),
      child: Text(
        char,
        style: VeriqooType.mono.copyWith(
          color: tokens.textPrimary,
          fontSize: 20,
        ),
      ),
    );
  }
}
