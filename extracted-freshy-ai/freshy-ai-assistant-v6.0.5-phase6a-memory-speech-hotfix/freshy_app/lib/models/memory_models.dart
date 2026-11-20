class MemoryItem {
  final String id;
  final String category;
  final String key;
  final String value;
  final List<String> tags;
  final int importance;
  final bool pinned;
  final String source;
  final String createdAt;
  final String updatedAt;
  final int accessCount;

  const MemoryItem({
    required this.id,
    required this.category,
    required this.key,
    required this.value,
    this.tags = const [],
    this.importance = 3,
    this.pinned = false,
    this.source = 'user',
    this.createdAt = '',
    this.updatedAt = '',
    this.accessCount = 0,
  });

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id']?.toString() ?? '',
      category: json['category']?.toString() ?? 'note',
      key: json['key']?.toString() ?? 'note',
      value: json['value']?.toString() ?? '',
      tags: (json['tags'] as List?)
              ?.map((item) => item.toString())
              .where((item) => item.isNotEmpty)
              .toList() ??
          const [],
      importance: (json['importance'] as num?)?.toInt() ?? 3,
      pinned: json['pinned'] == true,
      source: json['source']?.toString() ?? 'user',
      createdAt: json['created_at']?.toString() ?? '',
      updatedAt: json['updated_at']?.toString() ?? '',
      accessCount: (json['access_count'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toUpdateJson() {
    return {
      'category': category,
      'key': key,
      'value': value,
      'tags': tags,
      'importance': importance,
      'pinned': pinned,
    };
  }
}

class MemorySettingsModel {
  final bool enabled;
  final String mode;
  final bool persistConversations;
  final bool autoProfileDetection;
  final int maxItems;
  final int maxItemCharacters;
  final int recallLimit;
  final int recallCharacters;
  final int conversationRetentionDays;

  const MemorySettingsModel({
    this.enabled = true,
    this.mode = 'ask_before_saving',
    this.persistConversations = true,
    this.autoProfileDetection = true,
    this.maxItems = 500,
    this.maxItemCharacters = 2000,
    this.recallLimit = 6,
    this.recallCharacters = 2500,
    this.conversationRetentionDays = 30,
  });

  factory MemorySettingsModel.fromJson(Map<String, dynamic> json) {
    return MemorySettingsModel(
      enabled: json['enabled'] != false,
      mode: json['mode']?.toString() ?? 'ask_before_saving',
      persistConversations: json['persist_conversations'] != false,
      autoProfileDetection: json['auto_profile_detection'] != false,
      maxItems: (json['max_items'] as num?)?.toInt() ?? 500,
      maxItemCharacters:
          (json['max_item_characters'] as num?)?.toInt() ?? 2000,
      recallLimit: (json['recall_limit'] as num?)?.toInt() ?? 6,
      recallCharacters:
          (json['recall_characters'] as num?)?.toInt() ?? 2500,
      conversationRetentionDays:
          (json['conversation_retention_days'] as num?)?.toInt() ?? 30,
    );
  }

  MemorySettingsModel copyWith({
    bool? enabled,
    String? mode,
    bool? persistConversations,
    bool? autoProfileDetection,
    int? maxItems,
    int? maxItemCharacters,
    int? recallLimit,
    int? recallCharacters,
    int? conversationRetentionDays,
  }) {
    return MemorySettingsModel(
      enabled: enabled ?? this.enabled,
      mode: mode ?? this.mode,
      persistConversations:
          persistConversations ?? this.persistConversations,
      autoProfileDetection:
          autoProfileDetection ?? this.autoProfileDetection,
      maxItems: maxItems ?? this.maxItems,
      maxItemCharacters: maxItemCharacters ?? this.maxItemCharacters,
      recallLimit: recallLimit ?? this.recallLimit,
      recallCharacters: recallCharacters ?? this.recallCharacters,
      conversationRetentionDays:
          conversationRetentionDays ?? this.conversationRetentionDays,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'enabled': enabled,
      'mode': mode,
      'persist_conversations': persistConversations,
      'auto_profile_detection': autoProfileDetection,
      'max_items': maxItems,
      'max_item_characters': maxItemCharacters,
      'recall_limit': recallLimit,
      'recall_characters': recallCharacters,
      'conversation_retention_days': conversationRetentionDays,
    };
  }
}

class MemoryStatusModel {
  final bool enabled;
  final String mode;
  final bool databaseReady;
  final int memoryCount;
  final int pinnedCount;
  final int pendingCount;
  final int conversationSessionCount;
  final int conversationMessageCount;
  final bool persistConversations;

  const MemoryStatusModel({
    this.enabled = false,
    this.mode = 'disabled',
    this.databaseReady = false,
    this.memoryCount = 0,
    this.pinnedCount = 0,
    this.pendingCount = 0,
    this.conversationSessionCount = 0,
    this.conversationMessageCount = 0,
    this.persistConversations = false,
  });

  factory MemoryStatusModel.fromJson(Map<String, dynamic> json) {
    return MemoryStatusModel(
      enabled: json['enabled'] == true,
      mode: json['mode']?.toString() ?? 'disabled',
      databaseReady: json['database_ready'] == true,
      memoryCount: (json['memory_count'] as num?)?.toInt() ?? 0,
      pinnedCount: (json['pinned_count'] as num?)?.toInt() ?? 0,
      pendingCount: (json['pending_count'] as num?)?.toInt() ?? 0,
      conversationSessionCount:
          (json['conversation_session_count'] as num?)?.toInt() ?? 0,
      conversationMessageCount:
          (json['conversation_message_count'] as num?)?.toInt() ?? 0,
      persistConversations: json['persist_conversations'] == true,
    );
  }
}

class MemoryListResult {
  final List<MemoryItem> items;
  final int total;

  const MemoryListResult({this.items = const [], this.total = 0});
}

class MemoryActionResult {
  final bool success;
  final String message;
  final MemoryItem? item;

  const MemoryActionResult({
    required this.success,
    this.message = '',
    this.item,
  });
}

class MemoryExportResult {
  final bool success;
  final String jsonText;
  final String message;

  const MemoryExportResult({
    required this.success,
    this.jsonText = '',
    this.message = '',
  });
}
