import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import '../models/tts_settings.dart';
import '../models/voice_settings.dart';
import '../models/memory_models.dart';
import '../models/live_voice_settings.dart';

class FreshyApiResponse {
  final bool success;
  final String reply;
  final String intentName;
  final double confidence;
  final bool actionExecuted;
  final String freshyStatus;
  final Map<String, dynamic> details;
  final String provider;
  final String? model;
  final bool usedWebSearch;
  final List<Map<String, dynamic>> sources;
  final List<Map<String, dynamic>> fallbackChain;
  final String? toolUsed;
  final bool ttsRequested;
  final String? errorCode;
  final bool memoryUsed;
  final int memoryCount;
  final bool memoryPending;

  FreshyApiResponse({
    required this.success,
    required this.reply,
    required this.intentName,
    required this.confidence,
    required this.actionExecuted,
    required this.freshyStatus,
    required this.details,
    this.provider = 'local',
    this.model,
    this.usedWebSearch = false,
    this.sources = const [],
    this.fallbackChain = const [],
    this.toolUsed,
    this.ttsRequested = true,
    this.errorCode,
    this.memoryUsed = false,
    this.memoryCount = 0,
    this.memoryPending = false,
  });

  factory FreshyApiResponse.fromJson(Map<String, dynamic> json) {
    return FreshyApiResponse(
      success: json['success'] ?? false,
      reply: json['reply'] ?? 'No response received from Freshy Core.',
      intentName: json['intent_name'] ?? 'UNKNOWN',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      actionExecuted: json['action_executed'] ?? false,
      freshyStatus: json['freshy_status'] ?? 'idle',
      details: json['details'] != null ? Map<String, dynamic>.from(json['details']) : {},
      provider: json['provider']?.toString() ?? 'local',
      model: json['model']?.toString(),
      usedWebSearch: json['used_web_search'] == true,
      sources: (json['sources'] as List?)
              ?.whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList() ??
          const [],
      fallbackChain: (json['fallback_chain'] as List?)
              ?.whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList() ??
          const [],
      toolUsed: json['tool_used']?.toString(),
      ttsRequested: json['tts_requested'] != false,
      errorCode: json['error_code']?.toString(),
      memoryUsed: json['memory_used'] == true || json['details']?['memory_used'] == true,
      memoryCount: (json['memory_count'] as num?)?.toInt() ??
          (json['details']?['memory_count'] as num?)?.toInt() ??
          0,
      memoryPending: json['memory_pending'] == true ||
          json['details']?['memory_pending'] == true,
    );
  }
}

class TTSActionResult {
  final bool accepted;
  final String reason;

  TTSActionResult({required this.accepted, required this.reason});

  factory TTSActionResult.fromJson(Map<String, dynamic> json) {
    final bool ok = json.containsKey('accepted')
        ? (json['accepted'] == true)
        : (json['status'] == 'ok');
    return TTSActionResult(
      accepted: ok,
      reason: json['reason'] ?? (ok ? 'Operation successful' : 'Request rejected by Freshy Core'),
    );
  }
}

enum TTSUpdateFailureType {
  none,
  validationError,
  serviceUnavailable,
  connectionError,
}

class TTSUpdateResult {
  final bool success;
  final TTSSettings? settings;
  final String error;
  final TTSUpdateFailureType failureType;

  TTSUpdateResult({
    required this.success,
    this.settings,
    this.error = '',
    this.failureType = TTSUpdateFailureType.none,
  });
}

enum VoiceUpdateFailureType {
  none,
  validationError,
  serviceUnavailable,
  connectionError,
}

class VoiceUpdateResult {
  final bool success;
  final VoiceSettings? settings;
  final String error;
  final VoiceUpdateFailureType failureType;

  const VoiceUpdateResult({
    required this.success,
    this.settings,
    this.error = '',
    this.failureType = VoiceUpdateFailureType.none,
  });
}

class VoiceCalibrationResult {
  final bool success;
  final String reason;
  final double? calibratedThreshold;
  final int? calibrationId;

  const VoiceCalibrationResult({
    required this.success,
    required this.reason,
    this.calibratedThreshold,
    this.calibrationId,
  });

  factory VoiceCalibrationResult.fromJson(Map<String, dynamic> json) {
    return VoiceCalibrationResult(
      success: json['success'] == true,
      reason: json['reason']?.toString() ?? '',
      calibratedThreshold:
          (json['calibrated_threshold'] as num?)?.toDouble(),
      calibrationId: (json['calibration_id'] as num?)?.toInt(),
    );
  }
}

class FreshyApiService {
  final String baseUrl;
  final String sessionId;
  final bool allowWebSearch;

  FreshyApiService({
    this.baseUrl = 'http://127.0.0.1:8000',
    String? sessionId,
    this.allowWebSearch = true,
  }) : sessionId = sessionId ?? _createSessionId();

  static String _createSessionId() {
    final timestamp = DateTime.now().microsecondsSinceEpoch;
    final randomPart = Random().nextInt(1 << 32).toRadixString(16);
    return 'freshy-$timestamp-$randomPart';
  }

  /// Checks if Freshy Core Python FastAPI server is online on localhost
  Future<bool> checkHealth() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Sends user message to Freshy Core Python backend with finite timeout
  Future<FreshyApiResponse> sendMessage(String message) async {
    final url = Uri.parse('$baseUrl/api/chat');
    final response = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'message': message,
        'session_id': sessionId,
        'allow_web_search': allowWebSearch,
      }),
    ).timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return FreshyApiResponse.fromJson(data);
    } else {
      throw Exception('Failed to connect to Freshy Core (HTTP ${response.statusCode})');
    }
  }


  /// Clears bounded conversation history for this app session.
  Future<bool> clearConversation() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/conversation/clear'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'session_id': sessionId}),
      ).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Gets TTS settings from backend, returning null if connection fails
  Future<TTSSettings?> getTtsSettings() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/tts/settings'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return TTSSettings.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return null;
  }

  /// Updates TTS settings on backend returning typed result
  Future<TTSUpdateResult> updateTtsSettingsResult(TTSSettings settings) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/tts/settings'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(settings.toJson()),
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final updated = TTSSettings.fromJson(jsonDecode(response.body));
        return TTSUpdateResult(success: true, settings: updated);
      } else if (response.statusCode == 400) {
        String detail = 'Invalid TTS settings parameter';
        try {
          final data = jsonDecode(response.body);
          if (data['detail'] != null) detail = data['detail'].toString();
        } catch (_) {}
        return TTSUpdateResult(
          success: false,
          error: detail,
          failureType: TTSUpdateFailureType.validationError,
        );
      } else if (response.statusCode == 503) {
        String detail = 'TTS service is unavailable or shutting down';
        try {
          final data = jsonDecode(response.body);
          if (data['detail'] != null) detail = data['detail'].toString();
        } catch (_) {}
        return TTSUpdateResult(
          success: false,
          error: detail,
          failureType: TTSUpdateFailureType.serviceUnavailable,
        );
      } else {
        return TTSUpdateResult(
          success: false,
          error: 'Freshy Core returned HTTP ${response.statusCode}',
          failureType: TTSUpdateFailureType.serviceUnavailable,
        );
      }
    } catch (e) {
      return TTSUpdateResult(
        success: false,
        error: 'Could not connect to Freshy Core backend (${e.toString()})',
        failureType: TTSUpdateFailureType.connectionError,
      );
    }
  }

  /// Updates TTS settings on backend, returning null if connection fails (backward compatibility wrapper)
  Future<TTSSettings?> updateTtsSettings(TTSSettings settings) async {
    final res = await updateTtsSettingsResult(settings);
    return res.success ? res.settings : null;
  }

  /// Fetches installed Windows voices and consented XTTS human profiles.
  Future<TTSVoiceCatalog> getTtsVoiceCatalog() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/tts/voices'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final system = (data['voices'] as List?)
                ?.whereType<Map>()
                .map((v) => TTSVoice.fromJson(Map<String, dynamic>.from(v)))
                .toList() ??
            <TTSVoice>[];
        system.sort((a, b) {
          final aPriority = a.isDavid ? 0 : (a.isZira ? 1 : 2);
          final bPriority = b.isDavid ? 0 : (b.isZira ? 1 : 2);
          if (aPriority != bPriority) return aPriority.compareTo(bPriority);
          return a.name.compareTo(b.name);
        });
        final human = (data['human_voices'] as List?)
                ?.whereType<Map>()
                .map((v) => TTSHumanVoice.fromJson(Map<String, dynamic>.from(v)))
                .where((v) => v.id.isNotEmpty)
                .toList() ??
            <TTSHumanVoice>[];
        return TTSVoiceCatalog(systemVoices: system, humanVoices: human);
      }
    } catch (_) {}
    return const TTSVoiceCatalog();
  }

  /// Backward-compatible system voice list.
  Future<List<TTSVoice>> getTtsVoices() async {
    return (await getTtsVoiceCatalog()).systemVoices;
  }

  /// Gets current TTS speech status
  Future<Map<String, dynamic>> getTtsStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/tts/status'))
          .timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (_) {}
    return {'is_speaking': false, 'queue_size': 0, 'enabled': false, 'engine_available': false};
  }

  /// Triggers a test phrase output and returns typed result with accepted boolean and reason
  Future<TTSActionResult> testTtsVoice([String? phrase]) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/tts/test'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'text': phrase ?? 'This is a Freshy AI offline voice test.'}),
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return TTSActionResult.fromJson(data);
      } else {
        return TTSActionResult(
          accepted: false,
          reason: 'Freshy Core returned HTTP ${response.statusCode}',
        );
      }
    } catch (e) {
      return TTSActionResult(
        accepted: false,
        reason: 'Could not connect to Freshy Core backend (${e.toString()})',
      );
    }
  }

  /// Stops current speech output and clears pending queue
  Future<TTSActionResult> stopTtsSpeech() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/tts/stop'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return TTSActionResult.fromJson(data);
      } else {
        return TTSActionResult(
          accepted: false,
          reason: 'Freshy Core returned HTTP ${response.statusCode}',
        );
      }
    } catch (e) {
      return TTSActionResult(
        accepted: false,
        reason: 'Could not connect to Freshy Core backend (${e.toString()})',
      );
    }
  }

  /// Gets voice input settings from backend
  Future<VoiceSettings?> getVoiceSettings() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/voice/settings'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return VoiceSettings.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return null;
  }

  /// Updates voice input settings with typed validation/offline errors.
  Future<VoiceUpdateResult> updateVoiceSettingsResult(
    VoiceSettings settings,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/voice/settings'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(settings.toJson()),
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        return VoiceUpdateResult(
          success: true,
          settings: VoiceSettings.fromJson(jsonDecode(response.body)),
        );
      }
      String detail = 'Freshy Core returned HTTP ${response.statusCode}';
      try {
        final data = jsonDecode(response.body);
        if (data['detail'] != null) detail = data['detail'].toString();
      } catch (_) {}
      return VoiceUpdateResult(
        success: false,
        error: detail,
        failureType: response.statusCode == 400
            ? VoiceUpdateFailureType.validationError
            : VoiceUpdateFailureType.serviceUnavailable,
      );
    } catch (error) {
      return VoiceUpdateResult(
        success: false,
        error: 'Could not connect to Freshy Core (${error.toString()})',
        failureType: VoiceUpdateFailureType.connectionError,
      );
    }
  }

  /// Backward-compatible wrapper.
  Future<VoiceSettings?> updateVoiceSettings(VoiceSettings settings) async {
    final result = await updateVoiceSettingsResult(settings);
    return result.success ? result.settings : null;
  }

  /// Gets list of available microphone input devices
  Future<List<VoiceDevice>> getVoiceDevices() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/voice/devices'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final list = data['devices'] as List?;
        if (list != null) {
          return list.map((d) => VoiceDevice.fromJson(d)).toList();
        }
      }
    } catch (_) {}
    return [];
  }

  /// Gets current voice input state (listening, status, model/mic availability)
  Future<Map<String, dynamic>> getVoiceStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/voice/status'))
          .timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body));
        data['backend_available'] = true;
        return data;
      }
    } catch (_) {}
    return {
      'backend_available': false,
      'is_listening': false,
      'is_calibrating': false,
      'model_loaded': false,
      'mic_available': false,
      'freshy_status': 'idle',
      'error_status': 'Freshy Core voice endpoint is unavailable',
    };
  }

  /// Triggers push-to-talk speech input session
  Future<TTSActionResult> startVoiceListening() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/voice/listen/start'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return TTSActionResult.fromJson(data);
      } else {
        String reason = 'Listening request rejected';
        try {
          final data = jsonDecode(response.body);
          if (data['detail'] != null) reason = data['detail'].toString();
        } catch (_) {}
        return TTSActionResult(accepted: false, reason: reason);
      }
    } catch (e) {
      return TTSActionResult(
        accepted: false,
        reason: 'Could not connect to Freshy Core backend (${e.toString()})',
      );
    }
  }

  /// Stops voice listening session
  Future<TTSActionResult> stopVoiceListening() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/voice/listen/stop'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return TTSActionResult.fromJson(data);
      } else {
        return TTSActionResult(accepted: false, reason: 'Failed to stop voice listening');
      }
    } catch (e) {
      return TTSActionResult(
        accepted: false,
        reason: 'Could not connect to Freshy Core backend (${e.toString()})',
      );
    }
  }

  /// Calibrates ambient noise floor
  Future<VoiceCalibrationResult> calibrateVoiceNoise() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/voice/calibrate'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        return VoiceCalibrationResult.fromJson(jsonDecode(response.body));
      } else {
        String detail = 'Noise calibration failed';
        try {
          final data = jsonDecode(response.body);
          if (data['detail'] != null) detail = data['detail'].toString();
        } catch (_) {}
        return VoiceCalibrationResult(success: false, reason: detail);
      }
    } catch (e) {
      return VoiceCalibrationResult(
        success: false,
        reason: 'Connection error: ${e.toString()}',
      );
    }
  }

  Future<LiveVoiceSettings?> getLiveVoiceSettings() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/live/settings'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return LiveVoiceSettings.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
    } catch (_) {}
    return null;
  }

  Future<TTSActionResult> updateLiveVoiceSettings(
    LiveVoiceSettings settings,
  ) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/live/settings'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(settings.toJson()),
          )
          .timeout(const Duration(seconds: 6));
      if (response.statusCode == 200) {
        return TTSActionResult(accepted: true, reason: 'Live voice settings saved.');
      }
      return TTSActionResult(
        accepted: false,
        reason: _responseDetail(response, 'Could not save live voice settings.'),
      );
    } catch (error) {
      return TTSActionResult(accepted: false, reason: 'Connection error: $error');
    }
  }

  Future<LiveVoiceStatus?> getLiveVoiceStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/live/status'))
          .timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        return LiveVoiceStatus.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
    } catch (_) {}
    return null;
  }

  Future<TTSActionResult> startLiveSession() async {
    try {
      final response = await http
          .post(Uri.parse('$baseUrl/api/live/session/start'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        return TTSActionResult.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
      return TTSActionResult(
        accepted: false,
        reason: _responseDetail(response, 'Live session could not start.'),
      );
    } catch (error) {
      return TTSActionResult(accepted: false, reason: 'Connection error: $error');
    }
  }

  Future<TTSActionResult> stopLiveSession() async {
    try {
      final response = await http
          .post(Uri.parse('$baseUrl/api/live/session/stop'))
          .timeout(const Duration(seconds: 6));
      if (response.statusCode == 200) {
        return TTSActionResult.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
      return TTSActionResult(accepted: false, reason: 'Live session could not stop.');
    } catch (error) {
      return TTSActionResult(accepted: false, reason: 'Connection error: $error');
    }
  }

  Future<TTSActionResult> interruptLiveSession() async {
    try {
      final response = await http
          .post(Uri.parse('$baseUrl/api/live/interrupt'))
          .timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        return TTSActionResult.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
    } catch (_) {}
    return TTSActionResult(accepted: false, reason: 'Live interruption failed.');
  }

  Future<TTSActionResult> sendLiveText(String text) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/live/text'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return TTSActionResult.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
      return TTSActionResult(
        accepted: false,
        reason: _responseDetail(response, 'Live text could not be sent.'),
      );
    } catch (error) {
      return TTSActionResult(accepted: false, reason: 'Connection error: $error');
    }
  }

  Future<TTSActionResult> muteLiveSession(bool muted) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/live/mute'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'muted': muted}),
          )
          .timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        return TTSActionResult(accepted: true, reason: muted ? 'Live microphone muted.' : 'Live microphone active.');
      }
    } catch (_) {}
    return TTSActionResult(accepted: false, reason: 'Live microphone update failed.');
  }

  Future<MemoryStatusModel?> getMemoryStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/memory/status'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return MemoryStatusModel.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
    } catch (_) {}
    return null;
  }

  Future<MemorySettingsModel?> getMemorySettings() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/memory/settings'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return MemorySettingsModel.fromJson(
          Map<String, dynamic>.from(jsonDecode(response.body)),
        );
      }
    } catch (_) {}
    return null;
  }

  Future<MemoryActionResult> updateMemorySettings(
    MemorySettingsModel settings,
  ) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/memory/settings'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(settings.toJson()),
          )
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return const MemoryActionResult(
          success: true,
          message: 'Memory settings saved.',
        );
      }
      return MemoryActionResult(
        success: false,
        message: _responseDetail(response, 'Could not save memory settings.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryListResult> getMemories({
    String query = '',
    String? category,
    int limit = 100,
  }) async {
    try {
      final params = <String, String>{
        'query': query,
        'limit': '$limit',
      };
      if (category != null && category.isNotEmpty && category != 'all') {
        params['category'] = category;
      }
      final uri = Uri.parse('$baseUrl/api/memory').replace(queryParameters: params);
      final response = await http.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body));
        final items = (data['items'] as List?)
                ?.whereType<Map>()
                .map((item) =>
                    MemoryItem.fromJson(Map<String, dynamic>.from(item)))
                .toList() ??
            <MemoryItem>[];
        return MemoryListResult(
          items: items,
          total: (data['total'] as num?)?.toInt() ?? items.length,
        );
      }
    } catch (_) {}
    return const MemoryListResult();
  }

  Future<MemoryActionResult> createMemory({
    required String category,
    required String key,
    required String value,
    List<String> tags = const [],
    int importance = 3,
    bool pinned = false,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/memory'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'category': category,
              'key': key,
              'value': value,
              'tags': tags,
              'importance': importance,
              'pinned': pinned,
            }),
          )
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body));
        final item = data['item'] is Map
            ? MemoryItem.fromJson(
                Map<String, dynamic>.from(data['item'] as Map),
              )
            : null;
        return MemoryActionResult(
          success: true,
          message: data['created'] == false
              ? 'That memory already existed.'
              : 'Memory saved.',
          item: item,
        );
      }
      return MemoryActionResult(
        success: false,
        message: _responseDetail(response, 'Could not save memory.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> updateMemoryItem(
    String memoryId, {
    required String category,
    required String key,
    required String value,
    List<String> tags = const [],
    int importance = 3,
    bool pinned = false,
  }) async {
    try {
      final response = await http
          .put(
            Uri.parse('$baseUrl/api/memory/$memoryId'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'category': category,
              'key': key,
              'value': value,
              'tags': tags,
              'importance': importance,
              'pinned': pinned,
            }),
          )
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return MemoryActionResult(
          success: true,
          message: 'Memory updated.',
          item: MemoryItem.fromJson(
            Map<String, dynamic>.from(jsonDecode(response.body)),
          ),
        );
      }
      return MemoryActionResult(
        success: false,
        message: _responseDetail(response, 'Could not update memory.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> deleteMemoryItem(String memoryId) async {
    try {
      final response = await http
          .delete(Uri.parse('$baseUrl/api/memory/$memoryId'))
          .timeout(const Duration(seconds: 5));
      return MemoryActionResult(
        success: response.statusCode == 200,
        message: response.statusCode == 200
            ? 'Memory deleted.'
            : _responseDetail(response, 'Could not delete memory.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> setMemoryPinned(
    String memoryId,
    bool pinned,
  ) async {
    try {
      final uri = Uri.parse('$baseUrl/api/memory/$memoryId/pin')
          .replace(queryParameters: {'pinned': '$pinned'});
      final response = await http
          .post(uri, headers: {'Content-Type': 'application/json'})
          .timeout(const Duration(seconds: 5));
      return MemoryActionResult(
        success: response.statusCode == 200,
        message: response.statusCode == 200
            ? (pinned ? 'Memory pinned.' : 'Memory unpinned.')
            : _responseDetail(response, 'Could not update pin.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> clearAllMemories() async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/memory/clear'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'confirm': true}),
          )
          .timeout(const Duration(seconds: 6));
      return MemoryActionResult(
        success: response.statusCode == 200,
        message: response.statusCode == 200
            ? 'All permanent memories were deleted.'
            : _responseDetail(response, 'Could not clear memories.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> clearPersistedConversations() async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/memory/conversations/clear'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'confirm': true}),
          )
          .timeout(const Duration(seconds: 6));
      return MemoryActionResult(
        success: response.statusCode == 200,
        message: response.statusCode == 200
            ? 'Saved conversation history was cleared.'
            : _responseDetail(response, 'Could not clear conversation history.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryExportResult> exportMemories() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/memory/export'))
          .timeout(const Duration(seconds: 6));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        return MemoryExportResult(
          success: true,
          jsonText: const JsonEncoder.withIndent('  ').convert(decoded),
          message: 'Memory backup copied.',
        );
      }
      return MemoryExportResult(
        success: false,
        message: _responseDetail(response, 'Could not export memories.'),
      );
    } catch (error) {
      return MemoryExportResult(
        success: false,
        message: 'Memory service connection failed: $error',
      );
    }
  }

  Future<MemoryActionResult> importMemoriesFromJson(
    String jsonText, {
    bool replaceExisting = false,
  }) async {
    try {
      final decoded = jsonDecode(jsonText);
      if (decoded is! Map || decoded['items'] is! List) {
        return const MemoryActionResult(
          success: false,
          message: 'Clipboard does not contain a valid Freshy memory backup.',
        );
      }
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/memory/import'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'items': decoded['items'],
              'replace_existing': replaceExisting,
            }),
          )
          .timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body));
        return MemoryActionResult(
          success: true,
          message:
              'Imported ${data['imported'] ?? 0} memories; skipped ${data['skipped'] ?? 0}.',
        );
      }
      return MemoryActionResult(
        success: false,
        message: _responseDetail(response, 'Could not import memories.'),
      );
    } catch (error) {
      return MemoryActionResult(
        success: false,
        message: 'Invalid backup or memory service error: $error',
      );
    }
  }

  static String _responseDetail(http.Response response, String fallback) {
    try {
      final data = jsonDecode(response.body);
      if (data is Map && data['detail'] != null) {
        return data['detail'].toString();
      }
    } catch (_) {}
    return fallback;
  }

}
