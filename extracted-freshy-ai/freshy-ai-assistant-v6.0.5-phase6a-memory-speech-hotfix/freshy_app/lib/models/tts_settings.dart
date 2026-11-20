class TTSSettings {
  final bool enabled;
  final String provider;
  final String naturalVoice;
  final String humanVoiceProfile;
  final String speechLanguage;
  final String voiceStyle;
  final String selectedVoice;
  final int rate;
  final double volume;
  final bool startupGreeting;
  final bool fastStartEnabled;
  final bool prepareDuringSilence;
  final int fastChunkCharacters;
  final int firstChunkCharacters;
  final bool stableAudioEnabled;
  final bool trimBoundarySilence;
  final String failureBehavior;
  final String fallbackProvider;

  const TTSSettings({
    this.enabled = true,
    this.provider = 'gemini',
    this.naturalVoice = 'hindi_female',
    this.humanVoiceProfile = '',
    this.speechLanguage = 'auto',
    this.voiceStyle = 'natural',
    this.selectedVoice = '',
    this.rate = 175,
    this.volume = 1.0,
    this.startupGreeting = true,
    this.fastStartEnabled = true,
    this.prepareDuringSilence = true,
    this.fastChunkCharacters = 260,
    this.firstChunkCharacters = 150,
    this.stableAudioEnabled = true,
    this.trimBoundarySilence = true,
    this.failureBehavior = 'silent',
    this.fallbackProvider = 'none',
  });

  factory TTSSettings.fromJson(Map<String, dynamic> json) {
    return TTSSettings(
      enabled: json['enabled'] as bool? ?? true,
      provider: json['provider']?.toString() ?? 'gemini',
      naturalVoice: json['natural_voice']?.toString() ?? 'hindi_female',
      humanVoiceProfile: json['human_voice_profile']?.toString() ?? '',
      speechLanguage: json['speech_language']?.toString() ?? 'auto',
      voiceStyle: json['voice_style']?.toString() ?? 'natural',
      selectedVoice: json['selected_voice']?.toString() ?? '',
      rate: (json['rate'] as num?)?.toInt() ?? 175,
      volume: (json['volume'] as num?)?.toDouble() ?? 1.0,
      startupGreeting: json['startup_greeting'] as bool? ?? true,
      fastStartEnabled: json['fast_start_enabled'] as bool? ?? true,
      prepareDuringSilence: json['prepare_during_silence'] as bool? ?? true,
      fastChunkCharacters:
          (json['fast_chunk_characters'] as num?)?.toInt() ?? 260,
      firstChunkCharacters:
          (json['first_chunk_characters'] as num?)?.toInt() ?? 150,
      stableAudioEnabled: json['stable_audio_enabled'] as bool? ?? true,
      trimBoundarySilence: json['trim_boundary_silence'] as bool? ?? true,
      failureBehavior: json['failure_behavior']?.toString() ?? 'silent',
      fallbackProvider: json['fallback_provider']?.toString() ?? 'none',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'enabled': enabled,
      'provider': provider,
      'natural_voice': naturalVoice,
      'human_voice_profile': humanVoiceProfile,
      'speech_language': speechLanguage,
      'voice_style': voiceStyle,
      'selected_voice': selectedVoice,
      'rate': rate,
      'volume': volume,
      'startup_greeting': startupGreeting,
      'fast_start_enabled': fastStartEnabled,
      'prepare_during_silence': prepareDuringSilence,
      'fast_chunk_characters': fastChunkCharacters,
      'first_chunk_characters': firstChunkCharacters,
      'stable_audio_enabled': stableAudioEnabled,
      'trim_boundary_silence': trimBoundarySilence,
      'failure_behavior': failureBehavior,
      'fallback_provider': fallbackProvider,
    };
  }

  TTSSettings copyWith({
    bool? enabled,
    String? provider,
    String? naturalVoice,
    String? humanVoiceProfile,
    String? speechLanguage,
    String? voiceStyle,
    String? selectedVoice,
    int? rate,
    double? volume,
    bool? startupGreeting,
    bool? fastStartEnabled,
    bool? prepareDuringSilence,
    int? fastChunkCharacters,
    int? firstChunkCharacters,
    bool? stableAudioEnabled,
    bool? trimBoundarySilence,
    String? failureBehavior,
    String? fallbackProvider,
  }) {
    return TTSSettings(
      enabled: enabled ?? this.enabled,
      provider: provider ?? this.provider,
      naturalVoice: naturalVoice ?? this.naturalVoice,
      humanVoiceProfile: humanVoiceProfile ?? this.humanVoiceProfile,
      speechLanguage: speechLanguage ?? this.speechLanguage,
      voiceStyle: voiceStyle ?? this.voiceStyle,
      selectedVoice: selectedVoice ?? this.selectedVoice,
      rate: rate ?? this.rate,
      volume: volume ?? this.volume,
      startupGreeting: startupGreeting ?? this.startupGreeting,
      fastStartEnabled: fastStartEnabled ?? this.fastStartEnabled,
      prepareDuringSilence:
          prepareDuringSilence ?? this.prepareDuringSilence,
      fastChunkCharacters: fastChunkCharacters ?? this.fastChunkCharacters,
      firstChunkCharacters:
          firstChunkCharacters ?? this.firstChunkCharacters,
      stableAudioEnabled: stableAudioEnabled ?? this.stableAudioEnabled,
      trimBoundarySilence:
          trimBoundarySilence ?? this.trimBoundarySilence,
      failureBehavior: failureBehavior ?? this.failureBehavior,
      fallbackProvider: fallbackProvider ?? this.fallbackProvider,
    );
  }
}

class TTSVoice {
  final String id;
  final String name;
  final List<String> languages;

  const TTSVoice({
    required this.id,
    required this.name,
    this.languages = const [],
  });

  factory TTSVoice.fromJson(Map<String, dynamic> json) {
    return TTSVoice(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Unknown Voice',
      languages: (json['languages'] as List?)
              ?.map((item) => item.toString())
              .toList(growable: false) ??
          const [],
    );
  }

  bool get isDavid {
    final value = '$name $id'.toLowerCase();
    return value.contains('david');
  }

  bool get isZira {
    final value = '$name $id'.toLowerCase();
    return value.contains('zira');
  }

  String get displayName {
    if (languages.isEmpty) return name;
    return '$name — ${languages.join(', ')}';
  }
}

class TTSHumanVoice {
  final String id;
  final String label;
  final String language;
  final String description;
  final int referenceCount;
  final bool available;

  const TTSHumanVoice({
    required this.id,
    required this.label,
    this.language = 'hi',
    this.description = 'Custom consented XTTS voice',
    this.referenceCount = 0,
    this.available = true,
  });

  factory TTSHumanVoice.fromJson(Map<String, dynamic> json) {
    return TTSHumanVoice(
      id: json['id']?.toString() ?? '',
      label: json['label']?.toString() ?? 'Human Voice',
      language: json['language']?.toString() ?? 'hi',
      description: json['description']?.toString() ??
          'Custom consented XTTS voice',
      referenceCount: (json['reference_count'] as num?)?.toInt() ?? 0,
      available: json['available'] as bool? ?? true,
    );
  }
}

class TTSVoiceCatalog {
  final List<TTSVoice> systemVoices;
  final List<TTSHumanVoice> humanVoices;

  const TTSVoiceCatalog({
    this.systemVoices = const [],
    this.humanVoices = const [],
  });
}
