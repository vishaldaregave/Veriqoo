import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/core/services/voice_assistant_service.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';

/// Opens the Multilingual Voice STT Copilot modal from anywhere in the app.
void showVoiceCopilot(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => const VoiceCopilotSheet(),
  );
}

class VoiceCopilotSheet extends StatefulWidget {
  const VoiceCopilotSheet({super.key});

  @override
  State<VoiceCopilotSheet> createState() => _VoiceCopilotSheetState();
}

class _VoiceCopilotSheetState extends State<VoiceCopilotSheet>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  final VoiceAssistantService _voiceService = VoiceAssistantService.instance;

  bool _isListening = false;
  VoiceLanguage _selectedLanguage = VoiceLanguage.marathi;
  String _transcript = '';
  String _copilotResponse = '';

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);

    _selectedLanguage = _voiceService.activeLanguage;
    _setInitialGreeting();
    _voiceService.initialize();
  }

  void _setInitialGreeting() {
    switch (_selectedLanguage) {
      case VoiceLanguage.marathi:
        _copilotResponse = 'नमस्कार! मी व्हेरिक्कू व्हॉईस असिस्टंट. "स्कॅन करा", "तक्रार नकाशा", किंवा "नियम सांगा" असे बोला.';
        break;
      case VoiceLanguage.hindi:
        _copilotResponse = 'नमस्ते! मैं वेरीकू वॉयस असिस्टेंट हूँ। "स्कैन करो", "हीटमैप", या "नियम बताओ" बोलें।';
        break;
      case VoiceLanguage.english:
        _copilotResponse = 'Hello! I am your Veriqoo Voice Copilot. Say "Scan", "Heatmap", or "What are MRP rules?".';
        break;
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _voiceService.stopListening();
    _voiceService.stopSpeaking();
    super.dispose();
  }

  void _onLanguageChanged(VoiceLanguage lang) {
    setState(() {
      _selectedLanguage = lang;
      _voiceService.setLanguage(lang);
      _transcript = '';
      _setInitialGreeting();
    });
  }

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _voiceService.stopListening();
      setState(() => _isListening = false);
    } else {
      setState(() {
        _isListening = true;
        _transcript = _selectedLanguage == VoiceLanguage.marathi
            ? 'ऐकत आहे... (Listening...)'
            : (_selectedLanguage == VoiceLanguage.hindi ? 'सुन रहा हूँ... (Listening...)' : 'Listening...');
      });

      await _voiceService.startListening(
        onResult: (text) {
          if (!mounted) return;
          setState(() => _transcript = text);
          _executeCommand(text);
        },
        onListeningStatusChanged: (listening) {
          if (!mounted) return;
          setState(() => _isListening = listening);
        },
      );
    }
  }

  void _executeCommand(String text) {
    final result = _voiceService.processCommand(text, _selectedLanguage);

    setState(() {
      _isListening = false;
      _transcript = '"$text"';
      _copilotResponse = result.responseText;
    });

    // Speak response using TTS
    _voiceService.speak(result.responseText, language: _selectedLanguage);

    // If navigation intent is matched, perform smooth route transition
    if (result.navigationRoute != null) {
      Timer(const Duration(milliseconds: 1400), () {
        if (!mounted) return;
        Navigator.of(context).pop();
        context.push(result.navigationRoute!);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 12,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Container(
            width: 44,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey.shade300,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 16),

          // Header Row with Title and Language Toggle
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F5E9),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.record_voice_over_rounded, color: ProPalette.accentEmerald, size: 22),
                  ),
                  const SizedBox(width: 10),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Multilingual Voice Copilot',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: ProPalette.textHeading,
                        ),
                      ),
                      Text(
                        'UI Navigation & Legal Metrology Assistant',
                        style: TextStyle(fontSize: 11, color: ProPalette.textMuted),
                      ),
                    ],
                  ),
                ],
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 20, color: Colors.grey),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Language Selector Tabs (Marathi, Hindi, English)
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: VoiceLanguage.values.map((lang) {
                final isSelected = lang == _selectedLanguage;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => _onLanguageChanged(lang),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? Colors.white : Colors.transparent,
                        borderRadius: BorderRadius.circular(9),
                        boxShadow: isSelected
                            ? [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.05),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ]
                            : null,
                      ),
                      child: Center(
                        child: Text(
                          lang.shortLabel,
                          style: TextStyle(
                            fontSize: 12.5,
                            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                            color: isSelected ? ProPalette.primaryForest : ProPalette.textMuted,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 18),

          // Animated Central Microphone Button
          GestureDetector(
            onTap: _toggleListening,
            child: AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                final scale = _isListening ? 1.0 + (_pulseController.value * 0.15) : 1.0;
                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 78,
                    height: 78,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: _isListening
                            ? [const Color(0xFFDC2626), const Color(0xFFEF4444)]
                            : [const Color(0xFF0E3326), const Color(0xFF10B981)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: (_isListening ? Colors.red : ProPalette.accentEmerald).withValues(alpha: 0.35),
                          blurRadius: _isListening ? 20 : 12,
                          spreadRadius: _isListening ? 4 : 2,
                        ),
                      ],
                    ),
                    child: Icon(
                      _isListening ? Icons.mic : Icons.mic_none_rounded,
                      color: Colors.white,
                      size: 34,
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _isListening
                ? (_selectedLanguage == VoiceLanguage.marathi ? 'आता बोला...' : (_selectedLanguage == VoiceLanguage.hindi ? 'अब बोलें...' : 'Listening now...'))
                : (_selectedLanguage == VoiceLanguage.marathi ? 'माईक दाबा आणि बोला' : (_selectedLanguage == VoiceLanguage.hindi ? 'माइक दबाकर बोलें' : 'Tap mic and speak')),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: _isListening ? Colors.red.shade700 : ProPalette.textMuted,
            ),
          ),
          const SizedBox(height: 14),

          // Speech Transcript & Assistant Response Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_transcript.isNotEmpty) ...[
                  Row(
                    children: [
                      const Icon(Icons.person_outline, size: 14, color: Colors.grey),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          _transcript,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF0F172A),
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 16),
                ],
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.auto_awesome, size: 15, color: ProPalette.accentEmerald),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _copilotResponse,
                        style: const TextStyle(
                          fontSize: 13,
                          height: 1.4,
                          fontWeight: FontWeight.w500,
                          color: Color(0xFF1E293B),
                        ),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.volume_up_rounded, size: 18, color: ProPalette.accentEmerald),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      tooltip: 'Replay audio',
                      onPressed: () => _voiceService.speak(_copilotResponse, language: _selectedLanguage),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Quick Voice Command Suggestions
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              _selectedLanguage == VoiceLanguage.marathi
                  ? 'किंवा खालील आज्ञा निवडा:'
                  : (_selectedLanguage == VoiceLanguage.hindi ? 'या नीचे दिए गए सुझाव चुनें:' : 'Or tap a quick command:'),
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: ProPalette.textMuted),
            ),
          ),
          const SizedBox(height: 8),

          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _getQuickCommandsForLanguage(_selectedLanguage).map((cmd) {
              return ActionChip(
                backgroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                  side: const BorderSide(color: Color(0xFFCBD5E1), width: 1),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                avatar: Text(cmd['icon'] ?? '⚡', style: const TextStyle(fontSize: 13)),
                label: Text(
                  cmd['title'] ?? '',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ProPalette.textHeading),
                ),
                onPressed: () => _executeCommand(cmd['query'] ?? ''),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  List<Map<String, String>> _getQuickCommandsForLanguage(VoiceLanguage lang) {
    switch (lang) {
      case VoiceLanguage.marathi:
        return [
          {'icon': '📸', 'title': 'उत्पादन स्कॅन करा', 'query': 'उत्पादन स्कॅन करा'},
          {'icon': '🗺️', 'title': 'तक्रार नकाशा', 'query': 'तक्रार नकाशा उघडा'},
          {'icon': '⚖️', 'title': 'एमआरपी नियम काय आहेत?', 'query': 'एमआरपी नियम काय आहेत?'},
          {'icon': '📦', 'title': 'वजन नियम सांगा', 'query': 'वजन नियम सांगा'},
          {'icon': '🛡️', 'title': 'जाहिरात तपासा', 'query': 'जाहिरात तपासा'},
          {'icon': '📜', 'title': 'मागील तपासणी इतिहास', 'query': 'माझा इतिहास दाखवा'},
        ];
      case VoiceLanguage.hindi:
        return [
          {'icon': '📸', 'title': 'उत्पाद स्कैन करो', 'query': 'उत्पाद स्कैन करो'},
          {'icon': '🗺️', 'title': 'शिकायत हीटमैप', 'query': 'शिकायत हीटमैप खोलो'},
          {'icon': '⚖️', 'title': 'एमआरपी नियम क्या है?', 'query': 'एमआरपी नियम क्या है?'},
          {'icon': '📦', 'title': 'वजन नियम बताओ', 'query': 'वजन नियम बताओ'},
          {'icon': '🛡️', 'title': 'फेक एड डिटेक्टर', 'query': 'फेक एड डिटेक्टर खोलो'},
          {'icon': '📜', 'title': 'पुराने रिकॉर्ड्स', 'query': 'पुराने रिकॉर्ड्स दिखाओ'},
        ];
      case VoiceLanguage.english:
        return [
          {'icon': '📸', 'title': 'Scan Package', 'query': 'Scan a product package'},
          {'icon': '🗺️', 'title': 'Complaints Heatmap', 'query': 'Open live complaints heatmap'},
          {'icon': '⚖️', 'title': 'What are MRP rules?', 'query': 'What is the MRP rule?'},
          {'icon': '📦', 'title': 'Net Quantity rules', 'query': 'What is net quantity rule?'},
          {'icon': '🛡️', 'title': 'Ad Detector', 'query': 'Open ad clickbait detector'},
          {'icon': '📜', 'title': 'Inspection History', 'query': 'Show my inspection history'},
        ];
    }
  }
}
