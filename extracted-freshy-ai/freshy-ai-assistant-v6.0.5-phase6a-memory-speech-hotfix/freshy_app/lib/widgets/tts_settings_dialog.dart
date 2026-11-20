import 'package:flutter/material.dart';
import '../models/tts_settings.dart';
import '../services/freshy_api_service.dart';

class TtsSettingsDialog extends StatefulWidget {
  final FreshyApiService apiService;

  const TtsSettingsDialog({
    super.key,
    required this.apiService,
  });

  @override
  State<TtsSettingsDialog> createState() => _TtsSettingsDialogState();
}

class _TtsSettingsDialogState extends State<TtsSettingsDialog> {
  static const _cyan = Color(0xFF00F2FE);
  static const _panel = Color(0xFF131C2E);
  static const _border = Color(0xFF334155);

  TTSSettings _settings = TTSSettings();
  TTSSettings _confirmed = TTSSettings();
  List<TTSVoice> _systemVoices = [];
  List<TTSHumanVoice> _humanVoices = [];
  bool _loading = true;
  bool _saving = false;
  bool _testing = false;
  bool _backendAvailable = true;
  int _version = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final settings = await widget.apiService.getTtsSettings();
    final catalog = await widget.apiService.getTtsVoiceCatalog();
    if (!mounted) return;
    if (settings == null) {
      setState(() {
        _loading = false;
        _backendAvailable = false;
      });
      return;
    }
    setState(() {
      _settings = settings;
      _confirmed = settings;
      _systemVoices = catalog.systemVoices;
      _humanVoices = catalog.humanVoices;
      _loading = false;
      _backendAvailable = true;
    });
  }

  Future<void> _save(TTSSettings next) async {
    final request = ++_version;
    setState(() {
      _settings = next;
      _saving = true;
    });
    final result = await widget.apiService.updateTtsSettingsResult(next);
    if (!mounted || request != _version) return;
    if (result.success && result.settings != null) {
      setState(() {
        _settings = result.settings!;
        _confirmed = result.settings!;
        _saving = false;
        _backendAvailable = true;
      });
      return;
    }
    setState(() {
      _settings = _confirmed;
      _saving = false;
      if (result.failureType == TTSUpdateFailureType.connectionError ||
          result.failureType == TTSUpdateFailureType.serviceUnavailable) {
        _backendAvailable = false;
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Voice setting could not be saved: ${result.error}'),
        backgroundColor: Colors.redAccent,
      ),
    );
  }

  Future<void> _selectProvider(String provider) async {
    if (provider == 'xtts') {
      if (_humanVoices.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'No XTTS human voice profile is installed. Add a consented WAV profile first.',
            ),
            backgroundColor: Colors.orange,
          ),
        );
        return;
      }
      final profile = _humanVoices.any((v) => v.id == _settings.humanVoiceProfile)
          ? _settings.humanVoiceProfile
          : _humanVoices.first.id;
      await _save(_settings.copyWith(
        provider: provider,
        humanVoiceProfile: profile,
      ));
      return;
    }
    await _save(_settings.copyWith(provider: provider));
  }

  String _testPhrase() {
    if (_settings.provider == 'system') {
      return 'Hello, this is the selected Freshy Windows voice.';
    }
    if (_settings.speechLanguage == 'en-IN') {
      return 'Hello, I am Freshy. This is my natural human style voice.';
    }
    return 'नमस्ते, मैं Freshy हूँ। Main aapki madad ke liye taiyar hoon.';
  }

  Future<void> _testVoice() async {
    setState(() => _testing = true);
    final result = await widget.apiService.testTtsVoice(_testPhrase());
    if (!mounted) return;
    setState(() => _testing = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(result.reason),
        backgroundColor: result.accepted ? null : Colors.redAccent,
      ),
    );
  }

  Future<void> _stopVoice() async {
    final result = await widget.apiService.stopTtsSpeech();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result.reason)),
    );
  }

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(
          text,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      );

  Widget _dropdown({
    required String value,
    required List<DropdownMenuItem<String>> items,
    required ValueChanged<String?>? onChanged,
  }) {
    final safeValue = items.any((item) => item.value == value)
        ? value
        : (items.isEmpty ? null : items.first.value);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: _panel,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: safeValue,
          isExpanded: true,
          dropdownColor: _panel,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }

  Widget _info(String text, {IconData icon = Icons.info_outline_rounded}) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: const Color(0xFF082F49),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF0369A1)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: _cyan, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Color(0xFFBAE6FD), fontSize: 11.5),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final enabled = _backendAvailable && !_saving;
    final provider = _settings.provider;
    final isNeural = provider == 'gemini' || provider == 'xtts';

    return Dialog(
      backgroundColor: const Color(0xFF0B1220),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: _cyan, width: 1.3),
      ),
      child: Container(
        width: 560,
        constraints: const BoxConstraints(maxHeight: 760),
        padding: const EdgeInsets.all(22),
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _cyan))
            : SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: LinearGradient(
                              colors: [_cyan, Color(0xFF4FACFE)],
                            ),
                          ),
                          child: const Icon(
                            Icons.graphic_eq_rounded,
                            color: Colors.black,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Voice Studio',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                'Phase 4.3 • Exclusive stable audio output',
                                style: TextStyle(
                                  color: Color(0xFF94A3B8),
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close_rounded, color: Colors.white70),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      activeColor: _cyan,
                      value: _settings.enabled,
                      onChanged: enabled
                          ? (value) => _save(_settings.copyWith(enabled: value))
                          : null,
                      title: const Text(
                        'Enable Freshy Voice',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                      ),
                      subtitle: const Text(
                        'Only the selected engine is allowed to speak.',
                        style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
                      ),
                    ),
                    const Divider(color: Color(0xFF1E293B)),
                    _label('Voice Engine'),
                    _dropdown(
                      value: provider,
                      items: const [
                        DropdownMenuItem(
                          value: 'gemini',
                          child: Text('Gemini Natural Voice — Online'),
                        ),
                        DropdownMenuItem(
                          value: 'xtts',
                          child: Text('XTTS Human / Cloned Voice'),
                        ),
                        DropdownMenuItem(
                          value: 'system',
                          child: Text('Windows Voice — David, Zira & Installed Voices'),
                        ),
                        DropdownMenuItem(
                          value: 'text_only',
                          child: Text('Text Only — Stay Silent'),
                        ),
                      ],
                      onChanged: enabled
                          ? (value) {
                              if (value != null) _selectProvider(value);
                            }
                          : null,
                    ),
                    const SizedBox(height: 14),
                    if (provider == 'gemini') ...[
                      _label('Gemini Voice Profile'),
                      _dropdown(
                        value: _settings.naturalVoice,
                        items: const [
                          DropdownMenuItem(
                            value: 'hindi_female',
                            child: Text('Hindi / Hinglish — Female Natural'),
                          ),
                          DropdownMenuItem(
                            value: 'hindi_male',
                            child: Text('Hindi / Hinglish — Male Natural'),
                          ),
                        ],
                        onChanged: enabled
                            ? (value) {
                                if (value != null) {
                                  _save(_settings.copyWith(naturalVoice: value));
                                }
                              }
                            : null,
                      ),
                    ],
                    if (provider == 'xtts') ...[
                      _label('Consented Human Voice Profile'),
                      if (_humanVoices.isEmpty)
                        _info(
                          'No human profile is installed. Run voice_profile_manager.py with your own or a consented clean WAV, then refresh.',
                          icon: Icons.person_add_alt_1_rounded,
                        )
                      else
                        _dropdown(
                          value: _settings.humanVoiceProfile,
                          items: _humanVoices
                              .map(
                                (voice) => DropdownMenuItem(
                                  value: voice.id,
                                  child: Text(voice.label),
                                ),
                              )
                              .toList(),
                          onChanged: enabled
                              ? (value) {
                                  if (value != null) {
                                    _save(_settings.copyWith(humanVoiceProfile: value));
                                  }
                                }
                              : null,
                        ),
                      const SizedBox(height: 8),
                      _info(
                        'XTTS uses a separate optional voice server. Only use your own voice or a voice whose speaker gave clear permission.',
                        icon: Icons.verified_user_outlined,
                      ),
                    ],
                    if (provider == 'system') ...[
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _label('Windows Voice'),
                          IconButton(
                            tooltip: 'Refresh voices',
                            onPressed: _saving ? null : _load,
                            icon: const Icon(Icons.refresh_rounded, color: _cyan, size: 19),
                          ),
                        ],
                      ),
                      if (_systemVoices.isEmpty)
                        _info('No Windows voices were detected yet.')
                      else
                        _dropdown(
                          value: _systemVoices.any((v) => v.id == _settings.selectedVoice)
                              ? _settings.selectedVoice
                              : '',
                          items: [
                            const DropdownMenuItem(
                              value: '',
                              child: Text('System Default'),
                            ),
                            ..._systemVoices.map(
                              (voice) => DropdownMenuItem(
                                value: voice.id,
                                child: Text(
                                  voice.displayName,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ),
                          ],
                          onChanged: enabled
                              ? (value) {
                                  if (value != null) {
                                    _save(_settings.copyWith(selectedVoice: value));
                                  }
                                }
                              : null,
                        ),
                    ],
                    if (provider != 'text_only') ...[
                      const SizedBox(height: 14),
                      _label('Language / Pronunciation'),
                      _dropdown(
                        value: _settings.speechLanguage,
                        items: const [
                          DropdownMenuItem(value: 'auto', child: Text('Auto — Hindi, Hinglish & English')),
                          DropdownMenuItem(value: 'hi-IN', child: Text('Hindi / Hinglish — India')),
                          DropdownMenuItem(value: 'en-IN', child: Text('English — India')),
                        ],
                        onChanged: enabled
                            ? (value) {
                                if (value != null) {
                                  _save(_settings.copyWith(speechLanguage: value));
                                }
                              }
                            : null,
                      ),
                      const SizedBox(height: 14),
                      _label('Speaking Style'),
                      _dropdown(
                        value: _settings.voiceStyle,
                        items: const [
                          DropdownMenuItem(value: 'natural', child: Text('Natural Conversation')),
                          DropdownMenuItem(value: 'warm', child: Text('Warm & Friendly')),
                          DropdownMenuItem(value: 'calm', child: Text('Calm Assistant')),
                          DropdownMenuItem(value: 'professional', child: Text('Professional')),
                          DropdownMenuItem(value: 'cinematic', child: Text('Cinematic Assistant')),
                        ],
                        onChanged: enabled
                            ? (value) {
                                if (value != null) _save(_settings.copyWith(voiceStyle: value));
                              }
                            : null,
                      ),
                      const SizedBox(height: 10),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        activeColor: _cyan,
                        title: const Text(
                          'Fast Voice Start',
                          style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                        subtitle: const Text(
                          'Generate a short first clause, then prepare later audio while it is playing.',
                          style: TextStyle(color: Color(0xFF64748B), fontSize: 11.5),
                        ),
                        value: _settings.fastStartEnabled,
                        onChanged: enabled && isNeural
                            ? (value) => _save(_settings.copyWith(fastStartEnabled: value))
                            : null,
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        activeColor: _cyan,
                        title: const Text(
                          'Prepare Voice During Final Silence',
                          style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                        subtitle: const Text(
                          'Prepares the first audio while Freshy confirms that you finished speaking.',
                          style: TextStyle(color: Color(0xFF64748B), fontSize: 11.5),
                        ),
                        value: _settings.prepareDuringSilence,
                        onChanged: enabled && isNeural && _settings.fastStartEnabled
                            ? (value) => _save(_settings.copyWith(prepareDuringSilence: value))
                            : null,
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        activeColor: _cyan,
                        title: const Text(
                          'Trim Excess Chunk Silence',
                          style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                        subtitle: const Text(
                          'Removes only long generated padding at chunk boundaries to reduce cut-cut gaps.',
                          style: TextStyle(color: Color(0xFF64748B), fontSize: 11.5),
                        ),
                        value: _settings.trimBoundarySilence,
                        onChanged: enabled && isNeural
                            ? (value) => _save(_settings.copyWith(trimBoundarySilence: value))
                            : null,
                      ),
                      const SizedBox(height: 8),
                      _label('Voice Failure Behaviour'),
                      _dropdown(
                        value: _settings.failureBehavior,
                        items: const [
                          DropdownMenuItem(value: 'silent', child: Text('Show Text and Stay Silent — Recommended')),
                          DropdownMenuItem(value: 'retry_once', child: Text('Retry Selected Voice Once')),
                          DropdownMenuItem(value: 'selected_fallback', child: Text('Use My Selected Fallback')),
                        ],
                        onChanged: enabled
                            ? (value) {
                                if (value != null) _save(_settings.copyWith(failureBehavior: value));
                              }
                            : null,
                      ),
                      if (_settings.failureBehavior == 'selected_fallback') ...[
                        const SizedBox(height: 10),
                        _label('Fallback Voice Engine'),
                        _dropdown(
                          value: _settings.fallbackProvider,
                          items: [
                            const DropdownMenuItem(value: 'none', child: Text('None — Stay Silent')),
                            if (provider != 'gemini')
                              const DropdownMenuItem(value: 'gemini', child: Text('Gemini Natural Voice')),
                            if (provider != 'xtts' && _humanVoices.isNotEmpty)
                              const DropdownMenuItem(value: 'xtts', child: Text('XTTS Human Voice')),
                            if (provider != 'system')
                              const DropdownMenuItem(value: 'system', child: Text('Windows Selected Voice')),
                          ],
                          onChanged: enabled
                              ? (value) {
                                  if (value != null) _save(_settings.copyWith(fallbackProvider: value));
                                }
                              : null,
                        ),
                      ],
                      const SizedBox(height: 14),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Speech Speed', style: TextStyle(color: Colors.white, fontSize: 13)),
                          Text('${_settings.rate} WPM', style: const TextStyle(color: _cyan, fontWeight: FontWeight.bold)),
                        ],
                      ),
                      Slider(
                        value: _settings.rate.toDouble().clamp(50.0, 400.0).toDouble(),
                        min: 50,
                        max: 400,
                        divisions: 35,
                        activeColor: _cyan,
                        inactiveColor: _border,
                        onChanged: enabled
                            ? (value) => setState(() => _settings = _settings.copyWith(rate: value.round()))
                            : null,
                        onChangeEnd: enabled
                            ? (value) => _save(_settings.copyWith(rate: value.round()))
                            : null,
                      ),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Volume', style: TextStyle(color: Colors.white, fontSize: 13)),
                          Text('${(_settings.volume * 100).round()}%', style: const TextStyle(color: _cyan, fontWeight: FontWeight.bold)),
                        ],
                      ),
                      Slider(
                        value: _settings.volume.clamp(0.0, 1.0).toDouble(),
                        min: 0,
                        max: 1,
                        divisions: 20,
                        activeColor: _cyan,
                        inactiveColor: _border,
                        onChanged: enabled
                            ? (value) => setState(() => _settings = _settings.copyWith(volume: value))
                            : null,
                        onChangeEnd: enabled
                            ? (value) => _save(_settings.copyWith(volume: value))
                            : null,
                      ),
                    ],
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      activeColor: _cyan,
                      title: const Text(
                        'Startup Greeting',
                        style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                      value: _settings.startupGreeting,
                      onChanged: enabled
                          ? (value) => _save(_settings.copyWith(startupGreeting: value))
                          : null,
                    ),
                    const SizedBox(height: 10),
                    _info(
                      'The stable player keeps one PCM output stream open. Gemini, XTTS, and Windows voices are mutually exclusive, so a late response cannot collide with another engine.',
                      icon: Icons.multitrack_audio_rounded,
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: enabled && !_testing && provider != 'text_only'
                                ? _testVoice
                                : null,
                            icon: _testing
                                ? const SizedBox(
                                    width: 15,
                                    height: 15,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: _cyan),
                                  )
                                : const Icon(Icons.record_voice_over_rounded),
                            label: const Text('Test Selected Voice'),
                            style: OutlinedButton.styleFrom(foregroundColor: _cyan, side: const BorderSide(color: _cyan)),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _backendAvailable ? _stopVoice : null,
                            icon: const Icon(Icons.stop_circle_outlined),
                            label: const Text('Stop Speaking'),
                            style: OutlinedButton.styleFrom(foregroundColor: Colors.pinkAccent, side: const BorderSide(color: Colors.pinkAccent)),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}
