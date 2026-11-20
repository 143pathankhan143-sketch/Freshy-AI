import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:freshy_app/models/voice_settings.dart';
import 'package:freshy_app/services/freshy_api_service.dart';
import 'package:freshy_app/widgets/freshy_voice_orb.dart';

void main() {
  group('Phase 3 VoiceSettings Models Tests', () {
    test('VoiceSettings serialization and deserialization', () {
      final settings = VoiceSettings(
        deviceIndex: 2,
        recognitionEngine: 'whisper',
        whisperModel: 'base',
        speechLanguage: 'auto',
        vadEngine: 'webrtc',
        wakeWordEnabled: true,
        continuousListening: false,
        hotkeyEnabled: true,
        interruptWhileSpeaking: true,
        adaptiveSilence: false,
        responseSilenceSeconds: 4.0,
        partialProcessing: true,
        fastResponsePreparation: true,
        listeningTimeout: 8.5,
        muted: false,
        noiseThreshold: 0.03,
        modelLoaded: true,
        micAvailable: true,
      );

      final json = settings.toJson();
      expect(json['device_index'], equals(2));
      expect(json['recognition_engine'], equals('whisper'));
      expect(json['whisper_model'], equals('base'));
      expect(json['vad_engine'], equals('webrtc'));
      expect(json['wake_word_enabled'], equals(true));
      expect(json['listening_timeout'], equals(8.5));
      expect(json['interrupt_while_speaking'], isTrue);
      expect(json['response_silence_seconds'], equals(4.0));

      final deserialized = VoiceSettings.fromJson({
        'selected_device': 2,
        'recognition_engine': 'whisper',
        'whisper_model': 'base',
        'speech_language': 'auto',
        'vad_engine': 'webrtc',
        'wake_word_enabled': true,
        'continuous_listening': false,
        'hotkey_enabled': true,
        'interrupt_while_speaking': true,
        'adaptive_silence': false,
        'response_silence_seconds': 4.0,
        'partial_processing': true,
        'fast_response_preparation': true,
        'listening_timeout': 8.5,
        'muted': false,
        'noise_threshold': 0.03,
        'model_loaded': true,
        'mic_available': true,
      });

      expect(deserialized.deviceIndex, equals(2));
      expect(deserialized.recognitionEngine, equals('whisper'));
      expect(deserialized.vadEngine, equals('webrtc'));
      expect(deserialized.responseSilenceSeconds, equals(4.0));
      expect(deserialized.wakeWordEnabled, equals(true));
      expect(deserialized.modelLoaded, equals(true));
      expect(deserialized.micAvailable, equals(true));
    });

    test('VoiceSettings copyWith clearDeviceIndex', () {
      final settings = VoiceSettings(deviceIndex: 3, wakeWordEnabled: true);
      expect(settings.deviceIndex, equals(3));

      final cleared = settings.copyWith(clearDeviceIndex: true);
      expect(cleared.deviceIndex, isNull);
      expect(cleared.wakeWordEnabled, equals(true));
      expect(cleared.toJson().containsKey('device_index'), isTrue);
      expect(cleared.toJson()['device_index'], isNull);
    });

    test('VoiceDevice model parsing', () {
      final device = VoiceDevice.fromJson({
        'id': 1,
        'name': 'Realtek High Definition Audio',
        'channels': 2,
        'sample_rate': 44100,
        'is_default': true,
      });

      expect(device.id, equals(1));
      expect(device.name, equals('Realtek High Definition Audio'));
      expect(device.channels, equals(2));
      expect(device.isDefault, equals(true));
    });

    test('Completed calibration result parses threshold', () {
      final result = VoiceCalibrationResult.fromJson({
        'success': true,
        'reason': 'Ambient noise calibration completed',
        'calibration_id': 4,
        'calibrated_threshold': 0.031,
      });

      expect(result.success, isTrue);
      expect(result.calibrationId, equals(4));
      expect(result.calibratedThreshold, closeTo(0.031, 0.0001));
    });
  });

  group('Freshy Voice Orb widget', () {
    testWidgets('renders truthful labels for every state', (tester) async {
      for (final entry in <OrbState, String>{
        OrbState.idle: 'READY',
        OrbState.listening: 'LISTENING',
        OrbState.thinking: 'THINKING',
        OrbState.speaking: 'SPEAKING — TALK TO INTERRUPT',
        OrbState.offline: 'CORE OFFLINE',
      }.entries) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: FreshyVoiceOrb(state: entry.key),
            ),
          ),
        );
        await tester.pump(const Duration(milliseconds: 20));
        expect(find.text(entry.value), findsOneWidget);
      }
    });
  });
}
