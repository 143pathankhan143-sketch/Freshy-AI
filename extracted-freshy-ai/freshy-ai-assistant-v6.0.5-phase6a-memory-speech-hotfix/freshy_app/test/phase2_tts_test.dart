import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:freshy_app/models/tts_settings.dart';
import 'package:freshy_app/services/freshy_api_service.dart';
import 'package:freshy_app/widgets/tts_settings_dialog.dart';

  class MockFreshyApiService extends FreshyApiService {
  bool checkHealthResult = true;
  TTSSettings? settingsResult = TTSSettings(
    enabled: true,
    selectedVoice: 'voice_1',
    rate: 175,
    volume: 1.0,
    startupGreeting: true,
  );
  TTSSettings? updateSettingsResult;
  bool failUpdateSettings = false;
  List<TTSVoice> voicesResult = [
    TTSVoice(id: 'voice_1', name: 'Microsoft Zira - English (United States)', languages: ['en-US']),
  ];
  Map<String, dynamic> statusResult = {
    'is_speaking': false,
    'queue_size': 0,
    'enabled': true,
    'engine_available': true,
    'error_status': 'Ready',
  };
  TTSActionResult testVoiceResult = TTSActionResult(accepted: true, reason: 'Test voice phrase enqueued');
  TTSActionResult stopSpeechResult = TTSActionResult(accepted: true, reason: 'Speech playback stopped');

  @override
  Future<bool> checkHealth() async => checkHealthResult;

  @override
  Future<TTSSettings?> getTtsSettings() async => settingsResult;

  @override
  Future<TTSUpdateResult> updateTtsSettingsResult(TTSSettings settings) async {
    if (failUpdateSettings) {
      return TTSUpdateResult(
        success: false,
        error: 'Save failed on server',
        failureType: TTSUpdateFailureType.serviceUnavailable,
      );
    }
    return TTSUpdateResult(
      success: true,
      settings: updateSettingsResult ?? settings,
    );
  }

  @override
  Future<TTSSettings?> updateTtsSettings(TTSSettings settings) async {
    if (failUpdateSettings) return null;
    return updateSettingsResult ?? settings;
  }

  @override
  Future<List<TTSVoice>> getTtsVoices() async => voicesResult;

  @override
  Future<Map<String, dynamic>> getTtsStatus() async => statusResult;

  @override
  Future<TTSActionResult> testTtsVoice([String? phrase]) async => testVoiceResult;

  @override
  Future<TTSActionResult> stopTtsSpeech() async => stopSpeechResult;
}

void main() {
  group('Phase 2 TTS Model Tests', () {
    test('TTSSettings serialization and deserialization', () {
      final json = {
        'enabled': true,
        'selected_voice': 'voice_xyz',
        'rate': 200,
        'volume': 0.8,
        'startup_greeting': false,
        'fast_start_enabled': true,
        'prepare_during_silence': true,
        'fast_chunk_characters': 160,
      };

      final settings = TTSSettings.fromJson(json);
      expect(settings.enabled, true);
      expect(settings.selectedVoice, 'voice_xyz');
      expect(settings.rate, 200);
      expect(settings.volume, 0.8);
      expect(settings.startupGreeting, false);
      expect(settings.fastStartEnabled, true);
      expect(settings.prepareDuringSilence, true);
      expect(settings.fastChunkCharacters, 160);

      final exported = settings.toJson();
      expect(exported['enabled'], true);
      expect(exported['selected_voice'], 'voice_xyz');
      expect(exported['rate'], 200);
      expect(exported['volume'], 0.8);
      expect(exported['startup_greeting'], false);
      expect(exported['fast_start_enabled'], true);
      expect(exported['prepare_during_silence'], true);
      expect(exported['fast_chunk_characters'], 160);
    });

    test('TTSActionResult parsing for accepted and rejected responses', () {
      final acceptedJson = {'status': 'ok', 'accepted': true, 'reason': 'Phrase queued'};
      final acceptedRes = TTSActionResult.fromJson(acceptedJson);
      expect(acceptedRes.accepted, true);
      expect(acceptedRes.reason, 'Phrase queued');

      final rejectedJson = {'status': 'rejected', 'accepted': false, 'reason': 'TTS engine unavailable'};
      final rejectedRes = TTSActionResult.fromJson(rejectedJson);
      expect(rejectedRes.accepted, false);
      expect(rejectedRes.reason, 'TTS engine unavailable');

      // Test accepted: false taking precedence even when status is 'ok'
      final precedenceJson = {'status': 'ok', 'accepted': false, 'reason': 'Explicitly rejected'};
      final precedenceRes = TTSActionResult.fromJson(precedenceJson);
      expect(precedenceRes.accepted, false);
      expect(precedenceRes.reason, 'Explicitly rejected');
    });
  });

  group('Phase 2 TTS Widget Tests', () {
    late MockFreshyApiService mockApi;

    setUp(() {
      mockApi = MockFreshyApiService();
    });

    testWidgets('Displays settings and loaded voice list', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('TTS Voice Settings'), findsOneWidget);
      expect(find.text('Microsoft Zira - English (United States)'), findsOneWidget);
      expect(find.text('Test Voice'), findsOneWidget);
      expect(find.text('Stop Speaking'), findsOneWidget);
    });

    testWidgets('Handles offline backend state with warning banner', (WidgetTester tester) async {
      mockApi.settingsResult = null;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.textContaining('Freshy Core backend is offline'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);

      final refreshButton = tester.widget<IconButton>(
        find.byTooltip('Refresh Voices'),
      );
      expect(refreshButton.onPressed, isNotNull);
    });

    testWidgets('Displays empty voice list warning state', (WidgetTester tester) async {
      mockApi.voicesResult = [];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.textContaining('No Windows voices detected'), findsOneWidget);
    });

    testWidgets('Shows rejection reason when Test Voice is rejected', (WidgetTester tester) async {
      mockApi.testVoiceResult = TTSActionResult(accepted: false, reason: 'TTS is disabled in settings');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.text('Test Voice'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Test voice rejected: TTS is disabled in settings'), findsOneWidget);
    });

    testWidgets('Shows rejection reason when Stop Speaking fails', (WidgetTester tester) async {
      mockApi.stopSpeechResult = TTSActionResult(accepted: false, reason: 'Service is shutting down');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.text('Stop Speaking'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Failed to stop speech: Service is shutting down'), findsOneWidget);
    });

    testWidgets('Rolls back settings when save fails', (WidgetTester tester) async {
      mockApi.failUpdateSettings = true;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      Switch switchWidget = tester.widget<Switch>(find.byType(Switch).first);
      expect(switchWidget.value, isTrue);

      // Toggle switch to false, which fails on backend and should roll back
      await tester.tap(find.byType(Switch).first);
      await tester.pumpAndSettle();

      expect(find.textContaining('Failed to update TTS settings'), findsOneWidget);

      Switch switchWidgetAfter = tester.widget<Switch>(find.byType(Switch).first);
      expect(switchWidgetAfter.value, isTrue);
    });

    testWidgets('Displays System Default voice when selectedVoice is empty string', (WidgetTester tester) async {
      mockApi.settingsResult = TTSSettings(
        enabled: true,
        selectedVoice: '',
        rate: 175,
        volume: 1.0,
        startupGreeting: true,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TtsSettingsDialog(apiService: mockApi),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('System Default'), findsOneWidget);
    });
  });
}
