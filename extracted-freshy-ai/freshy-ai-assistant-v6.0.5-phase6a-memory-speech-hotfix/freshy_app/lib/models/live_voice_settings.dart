class LiveVoiceSettings {
  final bool enabled;
  final String conversationMode;
  final String model;
  final String voiceName;
  final String languageHint;
  final bool autoStart;
  final bool toolsEnabled;
  final bool memoryContextEnabled;
  final bool inputTranscription;
  final bool outputTranscription;
  final bool automaticActivityDetection;
  final bool interruptionEnabled;
  final bool localBargeIn;
  final bool echoGuardEnabled;
  final String startSensitivity;
  final String endSensitivity;
  final int prefixPaddingMs;
  final int silenceDurationMs;
  final int microphoneChunkMs;
  final int outputBufferMs;
  final bool sessionResumption;
  final bool contextCompression;
  final String fallbackMode;
  final double noiseThreshold;

  const LiveVoiceSettings({
    this.enabled = true,
    this.conversationMode = 'standard',
    this.model = 'gemini-3.1-flash-live-preview',
    this.voiceName = 'Kore',
    this.languageHint = 'auto',
    this.autoStart = false,
    this.toolsEnabled = true,
    this.memoryContextEnabled = true,
    this.inputTranscription = true,
    this.outputTranscription = true,
    this.automaticActivityDetection = true,
    this.interruptionEnabled = true,
    this.localBargeIn = true,
    this.echoGuardEnabled = true,
    this.startSensitivity = 'normal',
    this.endSensitivity = 'normal',
    this.prefixPaddingMs = 120,
    this.silenceDurationMs = 700,
    this.microphoneChunkMs = 40,
    this.outputBufferMs = 80,
    this.sessionResumption = true,
    this.contextCompression = true,
    this.fallbackMode = 'standard',
    this.noiseThreshold = 0.018,
  });

  factory LiveVoiceSettings.fromJson(Map<String, dynamic> json) {
    return LiveVoiceSettings(
      enabled: json['enabled'] as bool? ?? true,
      conversationMode: json['conversation_mode']?.toString() ?? 'standard',
      model: json['model']?.toString() ?? 'gemini-3.1-flash-live-preview',
      voiceName: json['voice_name']?.toString() ?? 'Kore',
      languageHint: json['language_hint']?.toString() ?? 'auto',
      autoStart: json['auto_start'] as bool? ?? false,
      toolsEnabled: json['tools_enabled'] as bool? ?? true,
      memoryContextEnabled: json['memory_context_enabled'] as bool? ?? true,
      inputTranscription: json['input_transcription'] as bool? ?? true,
      outputTranscription: json['output_transcription'] as bool? ?? true,
      automaticActivityDetection:
          json['automatic_activity_detection'] as bool? ?? true,
      interruptionEnabled: json['interruption_enabled'] as bool? ?? true,
      localBargeIn: json['local_barge_in'] as bool? ?? true,
      echoGuardEnabled: json['echo_guard_enabled'] as bool? ?? true,
      startSensitivity: json['start_sensitivity']?.toString() ?? 'normal',
      endSensitivity: json['end_sensitivity']?.toString() ?? 'normal',
      prefixPaddingMs: (json['prefix_padding_ms'] as num?)?.toInt() ?? 120,
      silenceDurationMs:
          (json['silence_duration_ms'] as num?)?.toInt() ?? 700,
      microphoneChunkMs:
          (json['microphone_chunk_ms'] as num?)?.toInt() ?? 40,
      outputBufferMs: (json['output_buffer_ms'] as num?)?.toInt() ?? 80,
      sessionResumption: json['session_resumption'] as bool? ?? true,
      contextCompression: json['context_compression'] as bool? ?? true,
      fallbackMode: json['fallback_mode']?.toString() ?? 'standard',
      noiseThreshold:
          (json['noise_threshold'] as num?)?.toDouble() ?? 0.018,
    );
  }

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        'conversation_mode': conversationMode,
        'model': model,
        'voice_name': voiceName,
        'language_hint': languageHint,
        'auto_start': autoStart,
        'tools_enabled': toolsEnabled,
        'memory_context_enabled': memoryContextEnabled,
        'input_transcription': inputTranscription,
        'output_transcription': outputTranscription,
        'automatic_activity_detection': automaticActivityDetection,
        'interruption_enabled': interruptionEnabled,
        'local_barge_in': localBargeIn,
        'echo_guard_enabled': echoGuardEnabled,
        'start_sensitivity': startSensitivity,
        'end_sensitivity': endSensitivity,
        'prefix_padding_ms': prefixPaddingMs,
        'silence_duration_ms': silenceDurationMs,
        'microphone_chunk_ms': microphoneChunkMs,
        'input_sample_rate': 16000,
        'output_sample_rate': 24000,
        'output_buffer_ms': outputBufferMs,
        'session_resumption': sessionResumption,
        'context_compression': contextCompression,
        'fallback_mode': fallbackMode,
        'noise_threshold': noiseThreshold,
      };

  LiveVoiceSettings copyWith({
    bool? enabled,
    String? conversationMode,
    String? model,
    String? voiceName,
    String? languageHint,
    bool? autoStart,
    bool? toolsEnabled,
    bool? memoryContextEnabled,
    bool? inputTranscription,
    bool? outputTranscription,
    bool? automaticActivityDetection,
    bool? interruptionEnabled,
    bool? localBargeIn,
    bool? echoGuardEnabled,
    String? startSensitivity,
    String? endSensitivity,
    int? prefixPaddingMs,
    int? silenceDurationMs,
    int? microphoneChunkMs,
    int? outputBufferMs,
    bool? sessionResumption,
    bool? contextCompression,
    String? fallbackMode,
    double? noiseThreshold,
  }) {
    return LiveVoiceSettings(
      enabled: enabled ?? this.enabled,
      conversationMode: conversationMode ?? this.conversationMode,
      model: model ?? this.model,
      voiceName: voiceName ?? this.voiceName,
      languageHint: languageHint ?? this.languageHint,
      autoStart: autoStart ?? this.autoStart,
      toolsEnabled: toolsEnabled ?? this.toolsEnabled,
      memoryContextEnabled: memoryContextEnabled ?? this.memoryContextEnabled,
      inputTranscription: inputTranscription ?? this.inputTranscription,
      outputTranscription: outputTranscription ?? this.outputTranscription,
      automaticActivityDetection:
          automaticActivityDetection ?? this.automaticActivityDetection,
      interruptionEnabled: interruptionEnabled ?? this.interruptionEnabled,
      localBargeIn: localBargeIn ?? this.localBargeIn,
      echoGuardEnabled: echoGuardEnabled ?? this.echoGuardEnabled,
      startSensitivity: startSensitivity ?? this.startSensitivity,
      endSensitivity: endSensitivity ?? this.endSensitivity,
      prefixPaddingMs: prefixPaddingMs ?? this.prefixPaddingMs,
      silenceDurationMs: silenceDurationMs ?? this.silenceDurationMs,
      microphoneChunkMs: microphoneChunkMs ?? this.microphoneChunkMs,
      outputBufferMs: outputBufferMs ?? this.outputBufferMs,
      sessionResumption: sessionResumption ?? this.sessionResumption,
      contextCompression: contextCompression ?? this.contextCompression,
      fallbackMode: fallbackMode ?? this.fallbackMode,
      noiseThreshold: noiseThreshold ?? this.noiseThreshold,
    );
  }
}

class LiveVoiceStatus {
  final bool configured;
  final String conversationMode;
  final String state;
  final bool connected;
  final bool connecting;
  final bool microphoneActive;
  final bool microphoneMuted;
  final bool outputPlaying;
  final String model;
  final String voiceName;
  final String lastInputTranscript;
  final String lastOutputTranscript;
  final String lastError;
  final double inputLevel;
  final double outputLevel;
  final Map<String, dynamic> metrics;

  const LiveVoiceStatus({
    this.configured = false,
    this.conversationMode = 'standard',
    this.state = 'idle',
    this.connected = false,
    this.connecting = false,
    this.microphoneActive = false,
    this.microphoneMuted = false,
    this.outputPlaying = false,
    this.model = '',
    this.voiceName = '',
    this.lastInputTranscript = '',
    this.lastOutputTranscript = '',
    this.lastError = '',
    this.inputLevel = 0,
    this.outputLevel = 0,
    this.metrics = const {},
  });

  factory LiveVoiceStatus.fromJson(Map<String, dynamic> json) => LiveVoiceStatus(
        configured: json['configured'] as bool? ?? false,
        conversationMode: json['conversation_mode']?.toString() ?? 'standard',
        state: json['state']?.toString() ?? 'idle',
        connected: json['connected'] as bool? ?? false,
        connecting: json['connecting'] as bool? ?? false,
        microphoneActive: json['microphone_active'] as bool? ?? false,
        microphoneMuted: json['microphone_muted'] as bool? ?? false,
        outputPlaying: json['output_playing'] as bool? ?? false,
        model: json['model']?.toString() ?? '',
        voiceName: json['voice_name']?.toString() ?? '',
        lastInputTranscript: json['last_input_transcript']?.toString() ?? '',
        lastOutputTranscript: json['last_output_transcript']?.toString() ?? '',
        lastError: json['last_error']?.toString() ?? '',
        inputLevel: (json['input_level'] as num?)?.toDouble() ?? 0,
        outputLevel: (json['output_level'] as num?)?.toDouble() ?? 0,
        metrics: json['metrics'] is Map
            ? Map<String, dynamic>.from(json['metrics'] as Map)
            : const {},
      );
}
