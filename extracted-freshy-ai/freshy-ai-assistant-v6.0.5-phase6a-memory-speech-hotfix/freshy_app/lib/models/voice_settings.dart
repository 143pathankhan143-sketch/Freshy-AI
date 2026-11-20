class VoiceSettings {
  final int? deviceIndex;
  final String recognitionEngine;
  final String whisperModel;
  final String speechLanguage;
  final String vadEngine;
  final bool wakeWordEnabled;
  final bool continuousListening;
  final bool hotkeyEnabled;
  final bool interruptWhileSpeaking;
  final String interruptionSensitivity;
  final bool adaptiveSilence;
  final double responseSilenceSeconds;
  final bool partialProcessing;
  final bool fastResponsePreparation;
  final double listeningTimeout;
  final bool muted;
  final double noiseThreshold;
  final bool modelLoaded;
  final bool voskModelLoaded;
  final bool whisperAvailable;
  final bool whisperModelLoaded;
  final bool micAvailable;
  final String activeEngine;
  final String vadActiveEngine;

  const VoiceSettings({
    this.deviceIndex,
    this.recognitionEngine = 'auto',
    this.whisperModel = 'base',
    this.speechLanguage = 'auto',
    this.vadEngine = 'auto',
    this.wakeWordEnabled = true,
    this.continuousListening = false,
    this.hotkeyEnabled = true,
    this.interruptWhileSpeaking = true,
    this.interruptionSensitivity = 'normal',
    this.adaptiveSilence = true,
    this.responseSilenceSeconds = 3.0,
    this.partialProcessing = true,
    this.fastResponsePreparation = true,
    this.listeningTimeout = 12.0,
    this.muted = false,
    this.noiseThreshold = 0.02,
    this.modelLoaded = false,
    this.voskModelLoaded = false,
    this.whisperAvailable = false,
    this.whisperModelLoaded = false,
    this.micAvailable = false,
    this.activeEngine = 'unavailable',
    this.vadActiveEngine = 'adaptive_rms',
  });

  factory VoiceSettings.fromJson(Map<String, dynamic> json) {
    final nested = json['settings'] is Map
        ? Map<String, dynamic>.from(json['settings'] as Map)
        : json;
    return VoiceSettings(
      deviceIndex: nested['selected_device'] as int? ?? nested['device_index'] as int?,
      recognitionEngine: nested['recognition_engine']?.toString() ?? 'auto',
      whisperModel: nested['whisper_model']?.toString() ?? 'base',
      speechLanguage: nested['speech_language']?.toString() ?? 'auto',
      vadEngine: nested['vad_engine']?.toString() ?? 'auto',
      wakeWordEnabled: nested['wake_word_enabled'] ?? true,
      continuousListening: nested['continuous_listening'] ?? false,
      hotkeyEnabled: nested['hotkey_enabled'] ?? true,
      interruptWhileSpeaking: nested['interrupt_while_speaking'] ?? true,
      interruptionSensitivity:
          nested['interruption_sensitivity']?.toString() ?? 'normal',
      adaptiveSilence: nested['adaptive_silence'] ?? true,
      responseSilenceSeconds:
          (nested['response_silence_seconds'] as num?)?.toDouble() ?? 3.0,
      partialProcessing: nested['partial_processing'] ?? true,
      fastResponsePreparation: nested['fast_response_preparation'] ?? true,
      listeningTimeout:
          (nested['listening_timeout'] as num?)?.toDouble() ?? 12.0,
      muted: nested['muted'] ?? false,
      noiseThreshold:
          (nested['noise_threshold'] as num?)?.toDouble() ?? 0.02,
      modelLoaded: json['model_loaded'] ?? nested['model_loaded'] ?? false,
      voskModelLoaded:
          json['vosk_model_loaded'] ?? nested['vosk_model_loaded'] ?? false,
      whisperAvailable:
          json['whisper_available'] ?? nested['whisper_available'] ?? false,
      whisperModelLoaded:
          json['whisper_model_loaded'] ?? nested['whisper_model_loaded'] ?? false,
      micAvailable: json['mic_available'] ?? nested['mic_available'] ?? false,
      activeEngine: json['recognition_engine_active']?.toString() ??
          nested['recognition_engine_active']?.toString() ??
          'unavailable',
      vadActiveEngine: json['vad_engine']?.toString() ??
          nested['vad_engine_active']?.toString() ??
          'adaptive_rms',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'device_index': deviceIndex,
      'recognition_engine': recognitionEngine,
      'whisper_model': whisperModel,
      'speech_language': speechLanguage,
      'vad_engine': vadEngine,
      'wake_word_enabled': wakeWordEnabled,
      'continuous_listening': continuousListening,
      'hotkey_enabled': hotkeyEnabled,
      'interrupt_while_speaking': interruptWhileSpeaking,
      'interruption_sensitivity': interruptionSensitivity,
      'adaptive_silence': adaptiveSilence,
      'response_silence_seconds': responseSilenceSeconds,
      'partial_processing': partialProcessing,
      'fast_response_preparation': fastResponsePreparation,
      'listening_timeout': listeningTimeout,
      'muted': muted,
      'noise_threshold': noiseThreshold,
    };
  }

  VoiceSettings copyWith({
    int? deviceIndex,
    bool clearDeviceIndex = false,
    String? recognitionEngine,
    String? whisperModel,
    String? speechLanguage,
    String? vadEngine,
    bool? wakeWordEnabled,
    bool? continuousListening,
    bool? hotkeyEnabled,
    bool? interruptWhileSpeaking,
    String? interruptionSensitivity,
    bool? adaptiveSilence,
    double? responseSilenceSeconds,
    bool? partialProcessing,
    bool? fastResponsePreparation,
    double? listeningTimeout,
    bool? muted,
    double? noiseThreshold,
    bool? modelLoaded,
    bool? voskModelLoaded,
    bool? whisperAvailable,
    bool? whisperModelLoaded,
    bool? micAvailable,
    String? activeEngine,
    String? vadActiveEngine,
  }) {
    return VoiceSettings(
      deviceIndex: clearDeviceIndex ? null : (deviceIndex ?? this.deviceIndex),
      recognitionEngine: recognitionEngine ?? this.recognitionEngine,
      whisperModel: whisperModel ?? this.whisperModel,
      speechLanguage: speechLanguage ?? this.speechLanguage,
      vadEngine: vadEngine ?? this.vadEngine,
      wakeWordEnabled: wakeWordEnabled ?? this.wakeWordEnabled,
      continuousListening: continuousListening ?? this.continuousListening,
      hotkeyEnabled: hotkeyEnabled ?? this.hotkeyEnabled,
      interruptWhileSpeaking:
          interruptWhileSpeaking ?? this.interruptWhileSpeaking,
      interruptionSensitivity:
          interruptionSensitivity ?? this.interruptionSensitivity,
      adaptiveSilence: adaptiveSilence ?? this.adaptiveSilence,
      responseSilenceSeconds:
          responseSilenceSeconds ?? this.responseSilenceSeconds,
      partialProcessing: partialProcessing ?? this.partialProcessing,
      fastResponsePreparation:
          fastResponsePreparation ?? this.fastResponsePreparation,
      listeningTimeout: listeningTimeout ?? this.listeningTimeout,
      muted: muted ?? this.muted,
      noiseThreshold: noiseThreshold ?? this.noiseThreshold,
      modelLoaded: modelLoaded ?? this.modelLoaded,
      voskModelLoaded: voskModelLoaded ?? this.voskModelLoaded,
      whisperAvailable: whisperAvailable ?? this.whisperAvailable,
      whisperModelLoaded: whisperModelLoaded ?? this.whisperModelLoaded,
      micAvailable: micAvailable ?? this.micAvailable,
      activeEngine: activeEngine ?? this.activeEngine,
      vadActiveEngine: vadActiveEngine ?? this.vadActiveEngine,
    );
  }
}

class VoiceDevice {
  final int id;
  final String name;
  final int channels;
  final int sampleRate;
  final bool isDefault;

  const VoiceDevice({
    required this.id,
    required this.name,
    required this.channels,
    required this.sampleRate,
    required this.isDefault,
  });

  factory VoiceDevice.fromJson(Map<String, dynamic> json) {
    return VoiceDevice(
      id: json['id'] ?? 0,
      name: json['name'] ?? 'Microphone',
      channels: json['channels'] ?? 1,
      sampleRate: json['sample_rate'] ?? 16000,
      isDefault: json['is_default'] ?? false,
    );
  }
}
