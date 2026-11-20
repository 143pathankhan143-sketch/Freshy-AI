import 'package:flutter/material.dart';
import '../models/live_voice_settings.dart';
import '../services/freshy_api_service.dart';

class LiveVoiceSettingsDialog extends StatefulWidget {
  final FreshyApiService apiService;
  const LiveVoiceSettingsDialog({super.key, required this.apiService});

  @override
  State<LiveVoiceSettingsDialog> createState() => _LiveVoiceSettingsDialogState();
}

class _LiveVoiceSettingsDialogState extends State<LiveVoiceSettingsDialog> {
  static const cyan = Color(0xFF22D3EE);
  LiveVoiceSettings settings = const LiveVoiceSettings();
  LiveVoiceStatus status = const LiveVoiceStatus();
  bool loading = true;
  bool saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final loaded = await widget.apiService.getLiveVoiceSettings();
    final liveStatus = await widget.apiService.getLiveVoiceStatus();
    if (!mounted) return;
    setState(() {
      settings = loaded ?? settings;
      status = liveStatus ?? status;
      loading = false;
    });
  }

  Future<void> _save() async {
    setState(() => saving = true);
    final result = await widget.apiService.updateLiveVoiceSettings(settings);
    if (!mounted) return;
    setState(() => saving = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(result.accepted ? 'Live voice settings saved.' : result.reason),
    ));
    if (result.accepted) await _load();
  }

  Future<void> _toggleSession() async {
    final result = status.connected || status.connecting
        ? await widget.apiService.stopLiveSession()
        : await widget.apiService.startLiveSession();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result.reason)));
    await Future<void>.delayed(const Duration(milliseconds: 350));
    await _load();
  }

  Widget _switch(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
      subtitle: Text(subtitle, style: const TextStyle(color: Color(0xFF8EA3C2), fontSize: 11)),
      value: value,
      activeColor: cyan,
      onChanged: onChanged,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: const Color(0xFF0D1729),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: const BorderSide(color: Color(0xFF24516A)),
      ),
      child: SizedBox(
        width: 620,
        height: 720,
        child: loading
            ? const Center(child: CircularProgressIndicator(color: cyan))
            : Column(children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(22, 18, 12, 12),
                  child: Row(children: [
                    const Icon(Icons.wifi_tethering_rounded, color: cyan),
                    const SizedBox(width: 10),
                    const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Live Voice Agent', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
                      Text('Persistent Gemini Live session • streaming audio • true barge-in', style: TextStyle(color: Color(0xFF8EA3C2), fontSize: 11)),
                    ])),
                    IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close, color: Color(0xFF8EA3C2))),
                  ]),
                ),
                const Divider(color: Color(0xFF223753), height: 1),
                Expanded(child: ListView(padding: const EdgeInsets.all(22), children: [
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: status.connected ? const Color(0xFF0C332F) : const Color(0xFF151F32),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: status.connected ? const Color(0xFF1EA97C) : const Color(0xFF334155)),
                    ),
                    child: Row(children: [
                      Icon(status.connected ? Icons.check_circle : Icons.radio_button_unchecked, color: status.connected ? const Color(0xFF38EF7D) : const Color(0xFF8EA3C2)),
                      const SizedBox(width: 10),
                      Expanded(child: Text(
                        status.connected ? 'Connected • ${status.model} • ${status.voiceName}' : status.connecting ? 'Connecting to Gemini Live…' : 'Live session is stopped',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                      )),
                      FilledButton.tonal(onPressed: _toggleSession, child: Text(status.connected || status.connecting ? 'Stop' : 'Start')),
                    ]),
                  ),
                  const SizedBox(height: 18),
                  DropdownButtonFormField<String>(
                    value: settings.conversationMode,
                    decoration: const InputDecoration(labelText: 'Conversation Mode'),
                    items: const [
                      DropdownMenuItem(value: 'standard', child: Text('Standard — Whisper/Vosk + Multi-provider')),
                      DropdownMenuItem(value: 'live', child: Text('Live — Gemini native streaming audio')),
                    ],
                    onChanged: (v) => setState(() => settings = settings.copyWith(conversationMode: v)),
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    initialValue: settings.model,
                    decoration: const InputDecoration(labelText: 'Gemini Live Model'),
                    onChanged: (v) => settings = settings.copyWith(model: v.trim()),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    value: settings.voiceName,
                    decoration: const InputDecoration(labelText: 'Live Voice'),
                    items: const ['Kore', 'Puck', 'Charon', 'Fenrir', 'Aoede']
                        .map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
                    onChanged: (v) => setState(() => settings = settings.copyWith(voiceName: v)),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    value: settings.languageHint,
                    decoration: const InputDecoration(labelText: 'Language Style'),
                    items: const [
                      DropdownMenuItem(value: 'auto', child: Text('Auto — Hindi / Hinglish / English')),
                      DropdownMenuItem(value: 'hi-IN', child: Text('Hindi / Hinglish — India')),
                      DropdownMenuItem(value: 'en-IN', child: Text('English — India')),
                    ],
                    onChanged: (v) => setState(() => settings = settings.copyWith(languageHint: v)),
                  ),
                  const SizedBox(height: 8),
                  _switch('True Barge-in', 'Speaking ke beech user bolte hi old playback clear kare.', settings.interruptionEnabled,
                      (v) => setState(() => settings = settings.copyWith(interruptionEnabled: v))),
                  _switch('Local Instant Stop', 'Network event ka wait kiye bina speaker queue flush kare.', settings.localBargeIn,
                      (v) => setState(() => settings = settings.copyWith(localBargeIn: v))),
                  _switch('Echo Guard', 'Speaker ki apni awaaz ko user interruption samajhne se bachaye.', settings.echoGuardEnabled,
                      (v) => setState(() => settings = settings.copyWith(echoGuardEnabled: v))),
                  _switch('Safe Tools', 'Tool calls Freshy ke existing validated allowlist se execute hon.', settings.toolsEnabled,
                      (v) => setState(() => settings = settings.copyWith(toolsEnabled: v))),
                  _switch('Persistent Memory Context', 'User-approved profile/preferences ko Live session prompt mein de.', settings.memoryContextEnabled,
                      (v) => setState(() => settings = settings.copyWith(memoryContextEnabled: v))),
                  _switch('Session Resumption', 'Temporary disconnect ke baad available handle se session resume kare.', settings.sessionResumption,
                      (v) => setState(() => settings = settings.copyWith(sessionResumption: v))),
                  _switch('Context Compression', 'Long Live sessions ko bounded sliding context ke saath continue rakhe.', settings.contextCompression,
                      (v) => setState(() => settings = settings.copyWith(contextCompression: v))),
                  _switch('Gemini Activity Detection', 'Gemini ko speech start/end detect karne dein; off par local boundaries bheji jayengi.', settings.automaticActivityDetection,
                      (v) => setState(() => settings = settings.copyWith(automaticActivityDetection: v))),
                  _switch('Input Transcript', 'Tumhari Live speech ko side chat aur memory history mein dikhaye.', settings.inputTranscription,
                      (v) => setState(() => settings = settings.copyWith(inputTranscription: v))),
                  _switch('Output Transcript', 'Native audio reply ka text side chat mein dikhaye.', settings.outputTranscription,
                      (v) => setState(() => settings = settings.copyWith(outputTranscription: v))),
                  _switch('Auto-start Live Mode', 'Freshy launch par Live session start kare; extra Gemini usage ho sakti hai.', settings.autoStart,
                      (v) => setState(() => settings = settings.copyWith(autoStart: v))),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: settings.fallbackMode,
                    decoration: const InputDecoration(labelText: 'Live Failure Behaviour'),
                    items: const [
                      DropdownMenuItem(value: 'standard', child: Text('Return to Standard mode')),
                      DropdownMenuItem(value: 'text_only', child: Text('Stay text-only / silent')),
                    ],
                    onChanged: (v) => setState(() => settings = settings.copyWith(fallbackMode: v)),
                  ),
                  const SizedBox(height: 8),
                  Text('End-of-speech silence: ${settings.silenceDurationMs} ms', style: const TextStyle(color: Colors.white)),
                  Slider(
                    value: settings.silenceDurationMs.toDouble(), min: 300, max: 2000, divisions: 17,
                    label: '${settings.silenceDurationMs} ms',
                    onChanged: (v) => setState(() => settings = settings.copyWith(silenceDurationMs: v.round())),
                  ),
                  Text('Output buffer: ${settings.outputBufferMs} ms', style: const TextStyle(color: Colors.white)),
                  Slider(
                    value: settings.outputBufferMs.toDouble(), min: 40, max: 240, divisions: 10,
                    label: '${settings.outputBufferMs} ms',
                    onChanged: (v) => setState(() => settings = settings.copyWith(outputBufferMs: v.round())),
                  ),
                  if (status.lastError.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(status.lastError, style: const TextStyle(color: Color(0xFFFF8A9B), fontSize: 11)),
                  ],
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: saving ? null : _save,
                    icon: saving ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_rounded),
                    label: const Text('Save Live Voice Settings'),
                  ),
                ])),
              ]),
      ),
    );
  }
}
