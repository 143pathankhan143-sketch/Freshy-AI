import 'package:flutter_test/flutter_test.dart';
import 'package:freshy_app/services/freshy_api_service.dart';

void main() {
  group('FreshyApiResponse Deserialization Tests', () {
    test('Parses valid API response correctly', () {
      final jsonMap = {
        'success': true,
        'reply': 'Hello! How can I help you today?',
        'intent_name': 'GREETING',
        'confidence': 0.95,
        'action_executed': true,
        'freshy_status': 'speaking',
        'details': {'action': 'GREETING'},
      };

      final response = FreshyApiResponse.fromJson(jsonMap);

      expect(response.success, true);
      expect(response.reply, 'Hello! How can I help you today?');
      expect(response.intentName, 'GREETING');
      expect(response.confidence, 0.95);
      expect(response.actionExecuted, true);
      expect(response.freshyStatus, 'speaking');
      expect(response.details['action'], 'GREETING');
    });

    test('Parses Phase 4 diagnostics safely', () {
      final response = FreshyApiResponse.fromJson({
        'success': true,
        'reply': 'Grounded answer',
        'intent_name': 'GENERAL_CHAT',
        'provider': 'mistral',
        'model': 'configured-model',
        'used_web_search': true,
        'sources': [
          {'title': 'Official source', 'url': 'https://example.com'},
        ],
        'fallback_chain': [
          {'provider': 'groq', 'status': 'rate_limited'},
          {'provider': 'mistral', 'status': 'success'},
        ],
        'tool_used': 'web_search',
        'tts_requested': true,
      });

      expect(response.provider, 'mistral');
      expect(response.model, 'configured-model');
      expect(response.usedWebSearch, true);
      expect(response.sources.single['title'], 'Official source');
      expect(response.fallbackChain.length, 2);
      expect(response.toolUsed, 'web_search');
    });

    test('Keeps one stable session id per service instance', () {
      final service = FreshyApiService();
      expect(service.sessionId, isNotEmpty);
      expect(service.sessionId, service.sessionId);
      expect(FreshyApiService(sessionId: 'test-session').sessionId, 'test-session');
    });

    test('Handles missing fields safely with default values', () {
      final jsonMap = <String, dynamic>{};

      final response = FreshyApiResponse.fromJson(jsonMap);

      expect(response.success, false);
      expect(response.intentName, 'UNKNOWN');
      expect(response.confidence, 0.0);
      expect(response.actionExecuted, false);
    });
  });
}
