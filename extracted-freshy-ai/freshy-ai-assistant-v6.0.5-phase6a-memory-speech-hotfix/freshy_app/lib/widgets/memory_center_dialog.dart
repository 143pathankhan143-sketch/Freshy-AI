import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/memory_models.dart';
import '../services/freshy_api_service.dart';

class MemoryCenterDialog extends StatefulWidget {
  final FreshyApiService apiService;

  const MemoryCenterDialog({
    Key? key,
    required this.apiService,
  }) : super(key: key);

  @override
  State<MemoryCenterDialog> createState() => _MemoryCenterDialogState();
}

class _MemoryCenterDialogState extends State<MemoryCenterDialog> {
  static const _cyan = Color(0xFF22D3EE);
  static const _panel = Color(0xFF0D1729);
  static const _panelLight = Color(0xFF121F35);
  static const _border = Color(0xFF263B57);
  static const _muted = Color(0xFF94A8C4);

  final TextEditingController _searchController = TextEditingController();
  bool _loading = true;
  bool _savingSettings = false;
  String _category = 'all';
  List<MemoryItem> _items = const [];
  int _total = 0;
  MemoryStatusModel _status = const MemoryStatusModel();
  MemorySettingsModel _settings = const MemorySettingsModel();

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    if (mounted) setState(() => _loading = true);
    final status = await widget.apiService.getMemoryStatus();
    final settings = await widget.apiService.getMemorySettings();
    final result = await widget.apiService.getMemories(
      query: _searchController.text.trim(),
      category: _category,
    );
    if (!mounted) return;
    setState(() {
      if (status != null) _status = status;
      if (settings != null) _settings = settings;
      _items = result.items;
      _total = result.total;
      _loading = false;
    });
  }

  void _showMessage(String message, {bool error = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor:
            error ? const Color(0xFFB91C1C) : const Color(0xFF075985),
      ),
    );
  }

  Future<void> _saveSettings(MemorySettingsModel settings) async {
    setState(() {
      _settings = settings;
      _savingSettings = true;
    });
    final result = await widget.apiService.updateMemorySettings(settings);
    if (!mounted) return;
    setState(() => _savingSettings = false);
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _editMemory([MemoryItem? existing]) async {
    final keyController = TextEditingController(text: existing?.key ?? 'note');
    final valueController = TextEditingController(text: existing?.value ?? '');
    final tagsController = TextEditingController(
      text: existing?.tags.join(', ') ?? '',
    );
    String category = existing?.category ?? 'note';
    int importance = existing?.importance ?? 3;
    bool pinned = existing?.pinned ?? false;

    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setLocalState) {
            return AlertDialog(
              backgroundColor: _panel,
              title: Text(
                existing == null ? 'Add Memory' : 'Edit Memory',
                style: const TextStyle(color: Colors.white),
              ),
              content: SizedBox(
                width: 500,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      DropdownButtonFormField<String>(
                        value: category,
                        dropdownColor: _panelLight,
                        decoration: _inputDecoration('Category'),
                        items: const [
                          DropdownMenuItem(
                            value: 'profile',
                            child: Text('Profile'),
                          ),
                          DropdownMenuItem(
                            value: 'preference',
                            child: Text('Preference'),
                          ),
                          DropdownMenuItem(
                            value: 'project',
                            child: Text('Project'),
                          ),
                          DropdownMenuItem(
                            value: 'note',
                            child: Text('Note'),
                          ),
                        ],
                        onChanged: (value) {
                          if (value != null) {
                            setLocalState(() => category = value);
                          }
                        },
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: keyController,
                        decoration: _inputDecoration(
                          'Key, for example name or active_project',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: valueController,
                        minLines: 3,
                        maxLines: 7,
                        decoration: _inputDecoration('Memory value'),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: tagsController,
                        decoration: _inputDecoration(
                          'Tags separated by commas',
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'Importance',
                              style: TextStyle(color: _muted),
                            ),
                          ),
                          DropdownButton<int>(
                            value: importance,
                            dropdownColor: _panelLight,
                            items: List.generate(
                              5,
                              (index) => DropdownMenuItem(
                                value: index + 1,
                                child: Text('${index + 1}'),
                              ),
                            ),
                            onChanged: (value) {
                              if (value != null) {
                                setLocalState(() => importance = value);
                              }
                            },
                          ),
                          const SizedBox(width: 24),
                          const Text('Pinned', style: TextStyle(color: _muted)),
                          Switch(
                            value: pinned,
                            activeColor: _cyan,
                            onChanged: (value) {
                              setLocalState(() => pinned = value);
                            },
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    if (keyController.text.trim().isEmpty ||
                        valueController.text.trim().isEmpty) {
                      return;
                    }
                    Navigator.pop(dialogContext, true);
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );

    if (accepted != true) {
      keyController.dispose();
      valueController.dispose();
      tagsController.dispose();
      return;
    }

    final tags = tagsController.text
        .split(',')
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
    final result = existing == null
        ? await widget.apiService.createMemory(
            category: category,
            key: keyController.text.trim(),
            value: valueController.text.trim(),
            tags: tags,
            importance: importance,
            pinned: pinned,
          )
        : await widget.apiService.updateMemoryItem(
            existing.id,
            category: category,
            key: keyController.text.trim(),
            value: valueController.text.trim(),
            tags: tags,
            importance: importance,
            pinned: pinned,
          );
    keyController.dispose();
    valueController.dispose();
    tagsController.dispose();
    if (!mounted) return;
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _confirmDelete(MemoryItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _panel,
        title: const Text('Delete memory?'),
        content: Text(
          item.value,
          maxLines: 5,
          overflow: TextOverflow.ellipsis,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton.tonal(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final result = await widget.apiService.deleteMemoryItem(item.id);
    if (!mounted) return;
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _clearAll() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _panel,
        title: const Text('Clear all permanent memories?'),
        content: const Text(
          'This removes saved profile, preference, project and note memories. '
          'It does not delete your API keys or voice settings.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFB91C1C),
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final result = await widget.apiService.clearAllMemories();
    if (!mounted) return;
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _copyBackup() async {
    final result = await widget.apiService.exportMemories();
    if (!mounted) return;
    if (!result.success) {
      _showMessage(result.message, error: true);
      return;
    }
    await Clipboard.setData(ClipboardData(text: result.jsonText));
    if (!mounted) return;
    _showMessage('Memory backup JSON copied to clipboard.');
  }

  Future<void> _importBackup() async {
    final clipboard = await Clipboard.getData(Clipboard.kTextPlain);
    final text = clipboard?.text?.trim() ?? '';
    if (!mounted) return;
    if (text.isEmpty) {
      _showMessage('Clipboard is empty.', error: true);
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _panel,
        title: const Text('Import memory backup?'),
        content: const Text(
          'Freshy will merge safe, non-duplicate memories from the JSON backup. '
          'Existing memories will not be deleted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Import'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final result = await widget.apiService.importMemoriesFromJson(text);
    if (!mounted) return;
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _clearConversationHistory() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _panel,
        title: const Text('Clear saved conversation history?'),
        content: const Text(
          'This deletes persisted chat sessions and messages. Permanent profile, '
          'preference, project and note memories remain saved.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton.tonal(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear History'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final result = await widget.apiService.clearPersistedConversations();
    if (!mounted) return;
    _showMessage(result.message, error: !result.success);
    if (result.success) await _loadAll();
  }

  Future<void> _handleMoreAction(String action) async {
    switch (action) {
      case 'copy_backup':
        await _copyBackup();
        break;
      case 'import_backup':
        await _importBackup();
        break;
      case 'clear_conversations':
        await _clearConversationHistory();
        break;
    }
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: _muted),
      filled: true,
      fillColor: _panelLight,
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _cyan),
      ),
    );
  }

  Widget _summaryCard(
    IconData icon,
    String label,
    String value,
    Color color,
  ) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _panelLight,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(color: _muted, fontSize: 10)),
                const SizedBox(height: 3),
                Text(
                  value,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _settingsPanel() {
    const modes = <String, String>{
      'ask_before_saving': 'Ask Before Saving',
      'auto_safe': 'Automatically Save Safe Preferences',
      'manual_only': 'Manual Memory Only',
      'disabled': 'Memory Disabled',
    };
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _panelLight.withOpacity(0.72),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
      ),
      child: Column(
        children: [
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Persistent memory'),
            subtitle: const Text(
              'Store only approved profile, preference, project and note memories.',
              style: TextStyle(color: _muted, fontSize: 11),
            ),
            value: _settings.enabled,
            activeColor: _cyan,
            onChanged: _savingSettings
                ? null
                : (value) => _saveSettings(
                      _settings.copyWith(enabled: value),
                    ),
          ),
          const Divider(color: _border),
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Saving mode'),
                    SizedBox(height: 3),
                    Text(
                      'Ask before saving is the recommended privacy setting.',
                      style: TextStyle(color: _muted, fontSize: 11),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              DropdownButton<String>(
                value: modes.containsKey(_settings.mode)
                    ? _settings.mode
                    : 'ask_before_saving',
                dropdownColor: _panelLight,
                items: modes.entries
                    .map(
                      (entry) => DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                    )
                    .toList(),
                onChanged: _savingSettings
                    ? null
                    : (value) {
                        if (value != null) {
                          _saveSettings(_settings.copyWith(mode: value));
                        }
                      },
              ),
            ],
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Remember conversation history'),
            subtitle: const Text(
              'Recent session messages can survive a backend restart and expire automatically.',
              style: TextStyle(color: _muted, fontSize: 11),
            ),
            value: _settings.persistConversations,
            activeColor: _cyan,
            onChanged: _savingSettings
                ? null
                : (value) => _saveSettings(
                      _settings.copyWith(persistConversations: value),
                    ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Detect safe profile facts'),
            subtitle: const Text(
              'For example, “My name is Pathan” can trigger a save confirmation.',
              style: TextStyle(color: _muted, fontSize: 11),
            ),
            value: _settings.autoProfileDetection,
            activeColor: _cyan,
            onChanged: _savingSettings
                ? null
                : (value) => _saveSettings(
                      _settings.copyWith(autoProfileDetection: value),
                    ),
          ),
          if (_savingSettings)
            const LinearProgressIndicator(minHeight: 2, color: _cyan),
        ],
      ),
    );
  }

  Widget _memoryCard(MemoryItem item) {
    final categoryColors = <String, Color>{
      'profile': const Color(0xFF38BDF8),
      'preference': const Color(0xFFA78BFA),
      'project': const Color(0xFF34D399),
      'note': const Color(0xFFFBBF24),
    };
    final color = categoryColors[item.category] ?? _cyan;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _panelLight,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(
          color: item.pinned ? color.withOpacity(0.75) : _border,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withOpacity(0.13),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              item.pinned ? Icons.push_pin_rounded : Icons.psychology_rounded,
              color: color,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        item.key.replaceAll('_', ' ').toUpperCase(),
                        style: TextStyle(
                          color: color,
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ),
                    Text(
                      item.category.toUpperCase(),
                      style: const TextStyle(color: _muted, fontSize: 9),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  item.value,
                  style: const TextStyle(
                    color: Colors.white,
                    height: 1.35,
                    fontSize: 12.5,
                  ),
                ),
                if (item.tags.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 5,
                    runSpacing: 5,
                    children: item.tags
                        .take(6)
                        .map(
                          (tag) => Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 7,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: const Color(0xFF172A43),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              tag,
                              style: const TextStyle(
                                color: _muted,
                                fontSize: 9,
                              ),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            children: [
              IconButton(
                tooltip: item.pinned ? 'Unpin' : 'Pin',
                onPressed: () async {
                  final result = await widget.apiService
                      .setMemoryPinned(item.id, !item.pinned);
                  if (!mounted) return;
                  _showMessage(result.message, error: !result.success);
                  if (result.success) await _loadAll();
                },
                icon: Icon(
                  item.pinned
                      ? Icons.push_pin_rounded
                      : Icons.push_pin_outlined,
                  color: item.pinned ? color : _muted,
                  size: 18,
                ),
              ),
              IconButton(
                tooltip: 'Edit',
                onPressed: () => _editMemory(item),
                icon: const Icon(Icons.edit_outlined, color: _muted, size: 18),
              ),
              IconButton(
                tooltip: 'Delete',
                onPressed: () => _confirmDelete(item),
                icon: const Icon(
                  Icons.delete_outline_rounded,
                  color: Color(0xFFF87171),
                  size: 18,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(24),
      child: Container(
        width: 860,
        height: 720,
        decoration: BoxDecoration(
          color: _panel,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: const Color(0xFF2A4B68)),
          boxShadow: const [
            BoxShadow(
              color: Color(0x99000000),
              blurRadius: 40,
              offset: Offset(0, 20),
            ),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.fromLTRB(20, 16, 12, 16),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: _border)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [_cyan, Color(0xFF6366F1)],
                      ),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: const Icon(
                      Icons.psychology_alt_rounded,
                      color: Color(0xFF06101F),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'MEMORY CENTER',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.3,
                          ),
                        ),
                        SizedBox(height: 3),
                        Text(
                          'Private local memory • secrets and API keys are rejected',
                          style: TextStyle(color: _muted, fontSize: 10.5),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Refresh',
                    onPressed: _loadAll,
                    icon: const Icon(Icons.refresh_rounded, color: _cyan),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close_rounded, color: _muted),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _loading
                  ? const Center(
                      child: CircularProgressIndicator(color: _cyan),
                    )
                  : Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              _summaryCard(
                                Icons.memory_rounded,
                                'SAVED MEMORIES',
                                '${_status.memoryCount}',
                                _cyan,
                              ),
                              const SizedBox(width: 10),
                              _summaryCard(
                                Icons.push_pin_rounded,
                                'PINNED',
                                '${_status.pinnedCount}',
                                const Color(0xFFFBBF24),
                              ),
                              const SizedBox(width: 10),
                              _summaryCard(
                                Icons.forum_outlined,
                                'SAVED MESSAGES',
                                '${_status.conversationMessageCount}',
                                const Color(0xFFA78BFA),
                              ),
                            ],
                          ),
                          const SizedBox(height: 14),
                          _settingsPanel(),
                          const SizedBox(height: 14),
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _searchController,
                                  decoration: InputDecoration(
                                    hintText: 'Search saved memory…',
                                    prefixIcon: const Icon(
                                      Icons.search_rounded,
                                      color: _muted,
                                    ),
                                    filled: true,
                                    fillColor: _panelLight,
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(13),
                                      borderSide: BorderSide.none,
                                    ),
                                  ),
                                  onSubmitted: (_) => _loadAll(),
                                ),
                              ),
                              const SizedBox(width: 10),
                              DropdownButton<String>(
                                value: _category,
                                dropdownColor: _panelLight,
                                items: const [
                                  DropdownMenuItem(
                                    value: 'all',
                                    child: Text('All categories'),
                                  ),
                                  DropdownMenuItem(
                                    value: 'profile',
                                    child: Text('Profile'),
                                  ),
                                  DropdownMenuItem(
                                    value: 'preference',
                                    child: Text('Preferences'),
                                  ),
                                  DropdownMenuItem(
                                    value: 'project',
                                    child: Text('Projects'),
                                  ),
                                  DropdownMenuItem(
                                    value: 'note',
                                    child: Text('Notes'),
                                  ),
                                ],
                                onChanged: (value) {
                                  if (value == null) return;
                                  setState(() => _category = value);
                                  _loadAll();
                                },
                              ),
                              const SizedBox(width: 10),
                              FilledButton.icon(
                                onPressed: () => _editMemory(),
                                icon: const Icon(Icons.add_rounded),
                                label: const Text('Add'),
                              ),
                              const SizedBox(width: 8),
                              PopupMenuButton<String>(
                                tooltip: 'Memory backup and history',
                                color: _panelLight,
                                onSelected: _handleMoreAction,
                                itemBuilder: (_) => const [
                                  PopupMenuItem(
                                    value: 'copy_backup',
                                    child: ListTile(
                                      dense: true,
                                      leading: Icon(Icons.copy_all_rounded),
                                      title: Text('Copy backup JSON'),
                                    ),
                                  ),
                                  PopupMenuItem(
                                    value: 'import_backup',
                                    child: ListTile(
                                      dense: true,
                                      leading: Icon(Icons.content_paste_go_rounded),
                                      title: Text('Import from clipboard'),
                                    ),
                                  ),
                                  PopupMenuItem(
                                    value: 'clear_conversations',
                                    child: ListTile(
                                      dense: true,
                                      leading: Icon(Icons.comments_disabled_outlined),
                                      title: Text('Clear saved conversations'),
                                    ),
                                  ),
                                ],
                                child: const Padding(
                                  padding: EdgeInsets.all(10),
                                  child: Icon(
                                    Icons.more_horiz_rounded,
                                    color: _muted,
                                  ),
                                ),
                              ),
                              IconButton(
                                tooltip: 'Clear all permanent memories',
                                onPressed: _total == 0 ? null : _clearAll,
                                icon: const Icon(
                                  Icons.delete_sweep_outlined,
                                  color: Color(0xFFF87171),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Expanded(
                            child: _items.isEmpty
                                ? const Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          Icons.psychology_outlined,
                                          size: 48,
                                          color: Color(0xFF48617E),
                                        ),
                                        SizedBox(height: 10),
                                        Text(
                                          'No matching memories yet.',
                                          style: TextStyle(color: _muted),
                                        ),
                                        SizedBox(height: 4),
                                        Text(
                                          'Say “Freshy, remember that…” or add one here.',
                                          style: TextStyle(
                                            color: Color(0xFF607896),
                                            fontSize: 11,
                                          ),
                                        ),
                                      ],
                                    ),
                                  )
                                : ListView.builder(
                                    itemCount: _items.length,
                                    itemBuilder: (_, index) =>
                                        _memoryCard(_items[index]),
                                  ),
                          ),
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
