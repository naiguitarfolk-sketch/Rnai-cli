import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

class SpeechService {
  final SpeechToText _speech = SpeechToText();
  bool _isInitialized = false;
  bool _isListening = false;
  String _lastRecognizedWords = '';
  String? _currentLocaleId;

  bool get isListening => _isListening;
  bool get isInitialized => _isInitialized;
  String get lastRecognizedWords => _lastRecognizedWords;

  Function(String text)? onResult;
  Function(bool isListening)? onListeningStateChanged;
  Function(String error)? onError;

  Future<bool> init() async {
    if (_isInitialized) return true;
    try {
      _isInitialized = await _speech.initialize(
        onError: (SpeechRecognitionError error) {
          debugPrint('Speech error: ${error.errorMsg}');
          _isListening = false;
          onListeningStateChanged?.call(false);
          onError?.call(error.errorMsg);
        },
        onStatus: (String status) {
          debugPrint('Speech status: $status');
          if (status == 'listening') {
            _isListening = true;
            onListeningStateChanged?.call(true);
          } else if (status == 'notListening' || status == 'done') {
            _isListening = false;
            onListeningStateChanged?.call(false);
          }
        },
      );

      if (_isInitialized) {
        final locales = await _speech.locales();
        // พยายามหาภาษาไทยก่อน (th_TH) หากไม่มีให้ใช้ default
        for (final loc in locales) {
          if (loc.localeId.toLowerCase().startsWith('th')) {
            _currentLocaleId = loc.localeId;
            break;
          }
        }
      }
      return _isInitialized;
    } catch (e) {
      debugPrint('Speech init error: $e');
      return false;
    }
  }

  Future<void> startListening({
    required Function(String text) onWords,
  }) async {
    if (!_isInitialized) {
      final ok = await init();
      if (!ok) {
        onError?.call('ไม่สามารถเปิดใช้งานไมโครโฟนได้');
        return;
      }
    }

    _lastRecognizedWords = '';
    onResult = onWords;

    try {
      await _speech.listen(
        onResult: (SpeechRecognitionResult result) {
          _lastRecognizedWords = result.recognizedWords;
          onResult?.call(_lastRecognizedWords);
        },
        listenOptions: SpeechListenOptions(
          cancelOnError: false,
          partialResults: true,
          listenMode: ListenMode.dictation,
          localeId: _currentLocaleId,
        ),
      );
      _isListening = true;
      onListeningStateChanged?.call(true);
    } catch (e) {
      _isListening = false;
      onListeningStateChanged?.call(false);
      onError?.call(e.toString());
    }
  }

  Future<void> stopListening() async {
    if (_isListening) {
      await _speech.stop();
      _isListening = false;
      onListeningStateChanged?.call(false);
    }
  }

  Future<void> cancelListening() async {
    await _speech.cancel();
    _isListening = false;
    onListeningStateChanged?.call(false);
  }
}
