import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:flutter_application_1/app/routes.dart';

/// Supported voice languages in Veriqoo: Hindi, Marathi, and English.
enum VoiceLanguage {
  marathi(code: 'mr_IN', ttsCode: 'mr-IN', label: 'मराठी (Marathi)', shortLabel: 'मराठी'),
  hindi(code: 'hi_IN', ttsCode: 'hi-IN', label: 'हिंदी (Hindi)', shortLabel: 'हिंदी'),
  english(code: 'en_IN', ttsCode: 'en-IN', label: 'English', shortLabel: 'English');

  const VoiceLanguage({
    required this.code,
    required this.ttsCode,
    required this.label,
    required this.shortLabel,
  });

  final String code;
  final String ttsCode;
  final String label;
  final String shortLabel;
}

class VoiceCommandResult {
  const VoiceCommandResult({
    required this.originalSpeech,
    required this.responseText,
    this.navigationRoute,
    required this.intent,
  });

  final String originalSpeech;
  final String responseText;
  final String? navigationRoute;
  final String intent;
}

/// Unified, offline-capable Multilingual Voice Assistant Service:
/// - Real-time Speech-To-Text (STT) for Hindi, Marathi, and English
/// - Natural Text-To-Speech (TTS) for report summaries and rules guidance
/// - Rule-based Intent Classifier for 100% accurate UI navigation without hallucinations
class VoiceAssistantService {
  VoiceAssistantService._internal();
  static final VoiceAssistantService instance = VoiceAssistantService._internal();

  final stt.SpeechToText _speech = stt.SpeechToText();
  final FlutterTts _tts = FlutterTts();

  bool _sttInitialized = false;
  bool _ttsInitialized = false;
  bool _isSpeaking = false;
  bool _isListening = false;
  VoiceLanguage _activeLanguage = VoiceLanguage.marathi;

  bool get isListening => _isListening;
  bool get isSpeaking => _isSpeaking;
  VoiceLanguage get activeLanguage => _activeLanguage;

  void setLanguage(VoiceLanguage lang) {
    _activeLanguage = lang;
    _tts.setLanguage(lang.ttsCode);
  }

  /// Initialize STT and TTS engines
  Future<bool> initialize() async {
    if (!_sttInitialized) {
      try {
        _sttInitialized = await _speech.initialize(
          onStatus: (status) {
            _isListening = status == 'listening';
            debugPrint('STT Status: $status');
          },
          onError: (error) {
            _isListening = false;
            debugPrint('STT Error: ${error.errorMsg}');
          },
        );
      } catch (e) {
        debugPrint('STT Init exception: $e');
        _sttInitialized = false;
      }
    }

    if (!_ttsInitialized) {
      try {
        await _tts.setLanguage(_activeLanguage.ttsCode);
        await _tts.setSpeechRate(0.50);
        await _tts.setPitch(1.0);
        await _tts.setVolume(1.0);

        _tts.setStartHandler(() => _isSpeaking = true);
        _tts.setCompletionHandler(() => _isSpeaking = false);
        _tts.setErrorHandler((msg) => _isSpeaking = false);

        _ttsInitialized = true;
      } catch (e) {
        debugPrint('TTS Init exception: $e');
        _ttsInitialized = false;
      }
    }

    return _sttInitialized;
  }

  /// Starts listening to voice input in the selected language
  Future<void> startListening({
    required Function(String recognizedText) onResult,
    required Function(bool isListening) onListeningStatusChanged,
  }) async {
    if (!_sttInitialized) {
      await initialize();
    }

    // Stop speaking if currently active
    await stopSpeaking();

    if (_speech.isAvailable) {
      _isListening = true;
      onListeningStatusChanged(true);

      await _speech.listen(
        localeId: _activeLanguage.code,
        listenFor: const Duration(seconds: 15),
        pauseFor: const Duration(seconds: 3),
        onResult: (result) {
          final words = result.recognizedWords;
          if (words.isNotEmpty) {
            onResult(words);
          }
          if (result.finalResult) {
            _isListening = false;
            onListeningStatusChanged(false);
          }
        },
      );
    } else {
      _isListening = false;
      onListeningStatusChanged(false);
    }
  }

  /// Stops listening
  Future<void> stopListening() async {
    if (_speech.isListening) {
      await _speech.stop();
    }
    _isListening = false;
  }

  /// Speaks text in the specified language (or active language)
  Future<void> speak(String text, {VoiceLanguage? language}) async {
    final lang = language ?? _activeLanguage;
    if (!_ttsInitialized) {
      await initialize();
    }
    await _tts.setLanguage(lang.ttsCode);
    _isSpeaking = true;
    await _tts.speak(text);
  }

  /// Stops TTS speech
  Future<void> stopSpeaking() async {
    if (_isSpeaking) {
      await _tts.stop();
      _isSpeaking = false;
    }
  }

  /// Evaluates spoken input and maps it to UI Navigation or Legal Metrology rules guidance.
  /// 100% deterministic to prevent hallucinations.
  VoiceCommandResult processCommand(String input, VoiceLanguage language) {
    final text = input.toLowerCase().trim();

    // 1. SCAN / CAMERA INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'स्कॅन', 'कॅमेरा', 'फोटो', 'पॅकेट', 'तपासा', 'स्कॅनिंग',
      // Hindi
      'स्कैन', 'कैमरा', 'फोटो खींचो', 'प्रोडक्ट स्कैन', 'जांच',
      // English
      'scan', 'camera', 'take photo', 'scanner', 'capture', 'inspect',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.scanPath,
        intent: 'scan',
        responseText: language == VoiceLanguage.marathi
            ? 'कॅमेरा उघडत आहे. उत्पादनाचा फोटो स्कॅन करा.'
            : (language == VoiceLanguage.hindi
                ? 'कैमरा खोला जा रहा है। कृपया उत्पाद का फोटो स्कैन करें।'
                : 'Opening compliance camera. Please capture the product label.'),
      );
    }

    // 2. COMPLAINTS HEATMAP INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'तक्रार', 'तक्रारी', 'नकाशा', 'हीटमॅप', 'उल्लंघन नकाशा',
      // Hindi
      'शिकायत', 'शिकायतें', 'नक्शा', 'हीटमैप', 'उल्लंघन',
      // English
      'heatmap', 'complaint', 'complaints', 'map', 'violations',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.heatmapPath,
        intent: 'heatmap',
        responseText: language == VoiceLanguage.marathi
            ? 'देशभरातील ग्राहक तक्रारी आणि उल्लंघनाचा नकाशा दाखवत आहे.'
            : (language == VoiceLanguage.hindi
                ? 'देशभर की उपभोक्ता शिकायतों और उल्लंघन का नक्शा खोला जा रहा है।'
                : 'Displaying nationwide consumer complaints heatmap.'),
      );
    }

    // 3. AD CLICKBAIT DETECTOR INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'जाहिरात', 'फेक जाहिरात', 'सोशल मीडिया', 'इन्स्टाग्राम',
      // Hindi
      'विज्ञापन', 'फेक एड', 'एड डिटेक्टर', 'इंस्टाग्राम',
      // English
      'ad', 'advertisement', 'fake ad', 'clickbait', 'instagram',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.adDetectorPath,
        intent: 'ad_detector',
        responseText: language == VoiceLanguage.marathi
            ? 'भ्रामक जाहिरात तपासणी केंद्र उघडत आहे.'
            : (language == VoiceLanguage.hindi
                ? 'भ्रामक सोशल मीडिया विज्ञापन डिटेक्टर खोला जा रहा है।'
                : 'Opening social media deceptive ad detector.'),
      );
    }

    // 4. HISTORY / PAST SCANS INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'इतिहास', 'माझे रेकॉर्ड', 'मागील तपासण्या', 'हिस्ट्री',
      // Hindi
      'इतिहास', 'पुराने रिकॉर्ड', 'हिस्ट्री', 'पिछले स्कैन',
      // English
      'history', 'past scans', 'records', 'logs', 'recent',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.historyPath,
        intent: 'history',
        responseText: language == VoiceLanguage.marathi
            ? 'तुमचा मागील तपासणी इतिहास उघडत आहे.'
            : (language == VoiceLanguage.hindi
                ? 'आपका पिछला निरीक्षण इतिहास खोला जा रहा है।'
                : 'Opening your past inspection records.'),
      );
    }

    // 5. SAVED REPORTS INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'अहवाल', 'रिपोर्ट', 'सेव्ह रिपोर्ट', 'डॉक्युमेंट',
      // Hindi
      'रिपोर्ट', 'रिपोर्ट्स', 'दस्तावेज', 'सेव रिपोर्ट',
      // English
      'reports', 'saved reports', 'report', 'dossier',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.reportsPath,
        intent: 'reports',
        responseText: language == VoiceLanguage.marathi
            ? 'जतन केलेले अधिकृत कायदेशीर अहवाल उघडत आहे.'
            : (language == VoiceLanguage.hindi
                ? 'सहेजे गए आधिकारिक विधिक रिपोर्ट खोले जा रहे हैं।'
                : 'Opening saved official legal reports.'),
      );
    }

    // 6. HOME INTENT
    if (_matchesKeywords(text, [
      // Marathi
      'होम', 'मुख्य स्क्रीन', 'डॅशबोर्ड',
      // Hindi
      'होम', 'मुख्य पृष्ठ', 'डैशबोर्ड',
      // English
      'home', 'main screen', 'dashboard',
    ])) {
      return VoiceCommandResult(
        originalSpeech: input,
        navigationRoute: AppRoutes.homePath,
        intent: 'home',
        responseText: language == VoiceLanguage.marathi
            ? 'मुख्य स्क्रीनवर नेत आहे.'
            : (language == VoiceLanguage.hindi
                ? 'मुख्य पृष्ठ पर ले जाया जा रहा है।'
                : 'Returning to Home dashboard.'),
      );
    }

    // 7. SPECIFIC RULES & REGULATIONS GUIDANCE
    // MRP Rule
    if (_matchesKeywords(text, ['mrp', 'किंमत', 'भाव', 'मूल्य', 'कीमत', 'दाम', 'price'])) {
      return VoiceCommandResult(
        originalSpeech: input,
        intent: 'rule_mrp',
        responseText: language == VoiceLanguage.marathi
            ? 'नियम ६(१)(क) नुसार: प्रत्येक पाकिटावर सर्व करांसह कमाल किरकोळ किंमत (MRP) स्पष्टपणे छापलेली असणे बंधनकारक आहे.'
            : (language == VoiceLanguage.hindi
                ? 'नियम ६(१)(ग) के अनुसार: प्रत्येक पैकेट पर सभी करों सहित अधिकतम खुदरा मूल्य (MRP) स्पष्ट रूप से लिखा होना अनिवार्य है।'
                : 'Under Rule 6(1)(c): Maximum Retail Price (MRP inclusive of all taxes) must be prominently printed on every retail package.'),
      );
    }

    // Net Quantity Rule
    if (_matchesKeywords(text, ['quantity', 'वजन', 'माप', 'प्रमाण', 'net qty', 'weight', 'ग्राम', 'किलो', 'लिटर'])) {
      return VoiceCommandResult(
        originalSpeech: input,
        intent: 'rule_net_qty',
        responseText: language == VoiceLanguage.marathi
            ? 'नियम ६(१)(इ) आणि नियम १२ नुसार: उत्पादनाचे निव्वळ वजन किंवा प्रमाण मानक युनिट्समध्ये (उदा. ग्रॅम, किलो, मिली, लिटर) असणे आवश्यक आहे.'
            : (language == VoiceLanguage.hindi
                ? 'नियम ६(१)(ङ) और नियम १२ के अनुसार: शुद्ध मात्रा मानक इकाइयों (जैसे ग्राम, किलो, मिली, लीटर) में घोषित होना अनिवार्य है।'
                : 'Under Rule 6(1)(e) and Rule 12: Net quantity must be explicitly declared in standard SI units (g, kg, ml, l, or number).'),
      );
    }

    // Expiry / Date Rule
    if (_matchesKeywords(text, ['date', 'तारीख', 'मॅन्युफॅक्चरिंग', 'दिनांक', 'एक्सपायरी', 'expiry', 'best before'])) {
      return VoiceCommandResult(
        originalSpeech: input,
        intent: 'rule_date',
        responseText: language == VoiceLanguage.marathi
            ? 'नियम ६(१)(ड) नुसार: उत्पादन किंवा पॅकिंगचा महिना आणि वर्ष छापणे बंधनकारक आहे.'
            : (language == VoiceLanguage.hindi
                ? 'नियम ६(१)(घ) के अनुसार: निर्माण या पैकेजिंग का महीना और वर्ष स्पष्ट रूप से लिखा होना चाहिए।'
                : 'Under Rule 6(1)(d): Month and year of manufacture or pre-packing must be declared on the principal display panel.'),
      );
    }

    // Consumer Care Helpline Rule
    if (_matchesKeywords(text, ['care', 'कस्टमर', 'तक्रार निवारण', 'हेल्पलाइन', 'ईमेल', 'फोन', 'helpline', 'customer', 'toll free'])) {
      return VoiceCommandResult(
        originalSpeech: input,
        intent: 'rule_helpline',
        responseText: language == VoiceLanguage.marathi
            ? 'नियम ६(१)(ह) नुसार: ग्राहक तक्रार निवारणासाठी संपर्क नाव, पत्ता, दूरध्वनी क्रमांक आणि ईमेल पत्ता असणे सक्तीचे आहे.'
            : (language == VoiceLanguage.hindi
                ? 'नियम ६(१)(ज) के अनुसार: उपभोक्ता शिकायत निवारण हेतु संपर्क नाम, पता, टेलीफोन नंबर और ईमेल पता होना अनिवार्य है।'
                : 'Under Rule 6(1)(h): Complete consumer grievance redressal phone number, postal address, and email are mandatory on every package.'),
      );
    }

    // Manufacturer Details Rule
    if (_matchesKeywords(text, ['कंपनी', 'निर्माता', 'पत्ता', 'मॅन्युफॅक्चरर', 'manufacturer', 'address', 'packer'])) {
      return VoiceCommandResult(
        originalSpeech: input,
        intent: 'rule_mfr',
        responseText: language == VoiceLanguage.marathi
            ? 'नियम ६(१)(अ) आणि नियम १० नुसार: उत्पादक, पॅकर किंवा आयातदाराचे संपूर्ण नाव आणि पत्ता असणे आवश्यक आहे.'
            : (language == VoiceLanguage.hindi
                ? 'नियम ६(१)(क) और नियम १० के अनुसार: निर्माता, पैकर या आयातक का पूरा नाम और भौतिक पता घोषित होना चाहिए।'
                : 'Under Rule 6(1)(a) and Rule 10: Complete name and physical registered address of the manufacturer or packer must be stated.'),
      );
    }

    // General Legal Metrology Help
    return VoiceCommandResult(
      originalSpeech: input,
      intent: 'general_help',
      responseText: language == VoiceLanguage.marathi
          ? 'विधी मापन शास्त्र नियम २०११ नुसार: एमआरपी, निव्वळ वजन, पॅकिंग तारीख, कंपनी पत्ता आणि ग्राहक तक्रार निवारण तपशील छापलेले असावे लागतात. उत्पादन तपासण्यासाठी "स्कॅन करा" बोला.'
          : (language == VoiceLanguage.hindi
              ? 'विधिक मापविज्ञान नियम २०११ के अनुसार: एमआरपी, शुद्ध वजन, निर्माण तिथि, निर्माता का पता और उपभोक्ता हेल्पलाइन अनिवार्य है। उत्पाद जांचने के लिए "स्कैन करो" बोलें।'
              : 'Under the Legal Metrology Packaged Commodities Rules 2011, MRP, net quantity, manufacturing date, and customer care details are mandatory. Say "Scan" to inspect any product.'),
    );
  }

  static bool _matchesKeywords(String text, List<String> keywords) {
    for (final kw in keywords) {
      if (text.contains(kw.toLowerCase())) return true;
    }
    return false;
  }

  /// Generates a natural, professional audio summary of an inspection report for TTS readout.
  static String generateReportAudioSummary({
    required String productName,
    required String manufacturer,
    required int score,
    required List<String> violations,
    required VoiceLanguage language,
  }) {
    final isCompliant = violations.isEmpty && score >= 90;
    final vCount = violations.length;

    switch (language) {
      case VoiceLanguage.marathi:
        if (isCompliant) {
          return 'व्हेरिक्कू अधिकृत पडताळणी अहवाल. उत्पादन: $productName. कंपनी: $manufacturer. '
              'अनुपालन स्कोर $score टक्के. हे उत्पादन विधी मापन शास्त्र नियम २०११ च्या सर्व अनिवार्य नियमांचे पूर्णपणे पालन करते. '
              'कोणतेही कायदेशीर उल्लंघन आढळले नाही.';
        } else {
          final reasonsText = violations.take(3).join(', ');
          return 'व्हेरिक्कू अधिकृत पडताळणी अहवाल. उत्पादन: $productName. कंपनी: $manufacturer. '
              'अनुपालन स्कोर $score टक्के. या उत्पादनावर $vCount कायदेशीर उल्लंघने आढळली आहेत. '
              'प्रमुख त्रुटी: $reasonsText. विधी मापन शास्त्र नियम २०११ चे उल्लंघन झाले आहे.';
        }

      case VoiceLanguage.hindi:
        if (isCompliant) {
          return 'वेरीकू आधिकारिक सत्यापन रिपोर्ट। उत्पाद: $productName। निर्माता: $manufacturer। '
              'अनुपालन स्कोर $score प्रतिशत। यह उत्पाद विधिक मापविज्ञान पैकेज्ड कमोडिटीज नियम २०११ के सभी मानकों का पूर्ण पालन करता है। '
              'कोई उल्लंघन नहीं पाया गया।';
        } else {
          final reasonsText = violations.take(3).join(', ');
          return 'वेरीकू आधिकारिक सत्यापन रिपोर्ट। उत्पाद: $productName। निर्माता: $manufacturer। '
              'अनुपालन स्कोर $score प्रतिशत। इस उत्पाद पर $vCount अनिवार्य विधिक उल्लंघने पाई गई हैं। '
              'प्रमुख कमियां: $reasonsText। विधिक मापविज्ञान नियम २०११ का उल्लंघन है।';
        }

      case VoiceLanguage.english:
        if (isCompliant) {
          return 'Veriqoo Official Compliance Verification Dossier. Product: $productName by $manufacturer. '
              'Compliance score is $score percent. This product fully satisfies all mandatory packaging declarations '
              'under the Legal Metrology Packaged Commodities Rules 2011. Zero violations detected.';
        } else {
          final reasonsText = violations.take(3).join(', ');
          return 'Veriqoo Official Compliance Verification Dossier. Product: $productName by $manufacturer. '
              'Compliance score is $score percent. Non-compliant: $vCount mandatory violations detected. '
              'Key issues found: $reasonsText. Non-compliant under Legal Metrology Packaged Commodities Rules 2011.';
        }
    }
  }
}
