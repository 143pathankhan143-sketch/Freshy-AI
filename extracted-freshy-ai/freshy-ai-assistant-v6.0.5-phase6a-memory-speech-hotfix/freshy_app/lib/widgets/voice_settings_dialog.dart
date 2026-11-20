import 'package:flutter/material.dart';
import '../models/voice_settings.dart';
import '../services/freshy_api_service.dart';

class VoiceSettingsDialog extends StatefulWidget {
  final FreshyApiService apiService;

  const VoiceSettingsDialog({Key? key, required this.apiService}) : super(key: key);

  @override
  State<VoiceSettingsDialog> createState() => _VoiceSettingsDialogState();
}

class _VoiceSettingsDialogState extends State<VoiceSettingsDialog> {
  static const _cyan = Color(0xFF22D3EE);
  static const _blue = Color(0xFF3B82F6);
  static const _panel = Color(0xFF111A2E);
  static const _panelLight = Color(0xFF17233B);
  static const _border = Color(0xFF263753);
  static const _muted = Color(0xFF8EA3C2);

  VoiceSettings? _settings;
  List<VoiceDevice> _devices = [];
  bool _isLoading = true;
  bool _isSaving = false;
  bool _isCalibrating = false;
  bool _backendAvailable = true;
  String? _calibrationMessage;
  String _activeEngine = 'unavailable';
  String _activeVad = 'adaptive_rms';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    final results = await Future.wait([
      widget.apiService.getVoiceSettings(),
      widget.apiService.getVoiceDevices(),
      widget.apiService.getVoiceStatus(),
    ]);
    if (!mounted) return;

    final settings = results[0] as VoiceSettings?;
    final devices = results[1] as List<VoiceDevice>;
    final status = results[2] as Map<String, dynamic>;
    setState(() {
      _backendAvailable = status['backend_available'] != false && settings != null;
      _settings = settings == null
          ? null
          : VoiceSettings.fromJson({
              ...settings.toJson(),
              ...status,
              'settings': settings.toJson(),
            });
      _devices = devices;
      _activeEngine = status['recognition_engine_active']?.toString() ??
          settings?.activeEngine ??
          'unavailable';
      _activeVad = status['vad_engine']?.toString() ??
          settings?.vadActiveEngine ??
          'adaptive_rms';
      _isLoading = false;
    });
  }

  Future<void> _saveSettings() async {
    final settings = _settings;
    if (settings == null) return;
    setState(() => _isSaving = true);
    final result = await widget.apiService.updateVoiceSettingsResult(settings);
    if (!mounted) return;
    setState(() => _isSaving = false);

    if (result.success && result.settings != null) {
      setState(() => _settings = result.settings);
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Phase 4.3 conversation settings saved.')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result.error.isEmpty ? 'Could not save voice settings.' : result.error),
          backgroundColor: const Color(0xFFB91C1C),
        ),
      );
    }
  }

  Future<void> _calibrateNoise() async {
    setState(() {
      _isCalibrating = true;
      _calibrationMessage = 'Stay quiet for a few seconds…';
    });
    final result = await widget.apiService.calibrateVoiceNoise();
    if (!mounted) return;
    setState(() {
      _isCalibrating = false;
      if (result.success) {
        _calibrationMessage =
            'Calibrated: ${(result.calibratedThreshold ?? 0).toStringAsFixed(4)}';
        final current = _settings;
        if (current != null) {
          _settings = current.copyWith(
            noiseThreshold: result.calibratedThreshold ?? current.noiseThreshold,
          );
        }
      } else {
        _calibrationMessage = result.reason;
      }
    });
  }

  Widget _section({
    required String title,
    required String subtitle,
    required IconData icon,
    required List<Widget> children,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _panel,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
        boxShadow: const [
          BoxShadow(color: Color(0x26000000), blurRadius: 18, offset: Offset(0, 8)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  gradient: const LinearGradient(colors: [_cyan, _blue]),
                ),
                child: Icon(icon, color: const Color(0xFF06111E), size: 21),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(subtitle,
                        style: const TextStyle(color: _muted, fontSize: 11.5)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 15),
          ...children,
        ],
      ),
    );
  }

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(text,
            style: const TextStyle(
                color: Color(0xFFD8E7FA),
                fontSize: 12.5,
                fontWeight: FontWeight.w600)),
      );

  Widget _dropdown({
    required String value,
    required List<DropdownMenuItem<String>> items,
    required ValueChanged<String?> onChanged,
  }) {
    final safeValue = items.any((item) => item.value == value)
        ? value
        : items.first.value!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: _panelLight,
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: _border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: safeValue,
          isExpanded: true,
          dropdownColor: _panelLight,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }

  Widget _switch({
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      activeColor: _cyan,
      title: Text(title,
          style: const TextStyle(
              color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle,
          style: const TextStyle(color: _muted, fontSize: 11)),
      value: value,
      onChanged: onChanged,
    );
  }

  Widget _statusChip(String label, bool ready) {
    final color = ready ? const Color(0xFF34D399) : const Color(0xFFF59E0B);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.45)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: color, fontSize: 10.5, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final settings = _settings;
    final controlsEnabled = _backendAvailable && !_isSaving && settings != null;

    return Dialog(
      backgroundColor: const Color(0xFF091222),
      insetPadding: const EdgeInsets.all(24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: const BorderSide(color: Color(0xFF275077), width: 1.2),
      ),
      child: SizedBox(
        width: 660,
        height: 760,
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.fromLTRB(20, 18, 12, 16),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: _border)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 45,
                    height: 45,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      gradient: const LinearGradient(colors: [_cyan, _blue]),
                      boxShadow: const [BoxShadow(color: Color(0x5522D3EE), blurRadius: 18)],
                    ),
                    child: const Icon(Icons.hearing_rounded, color: Color(0xFF06111E)),
                  ),
                  const SizedBox(width: 13),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Natural Conversation Settings',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 19,
                                fontWeight: FontWeight.w800)),
                        SizedBox(height: 3),
                        Text('Whisper/Vosk • VAD • Barge-in • Adaptive silence',
                            style: TextStyle(color: _muted, fontSize: 11.5)),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close_rounded, color: _muted),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator(color: _cyan))
                  : settings == null
                      ? Center(
                          child: TextButton.icon(
                            onPressed: _loadData,
                            icon: const Icon(Icons.refresh, color: _cyan),
                            label: const Text('Freshy Core unavailable — Retry',
                                style: TextStyle(color: _cyan)),
                          ),
                        )
                      : SingleChildScrollView(
                          padding: const EdgeInsets.all(18),
                          child: Column(
                            children: [
                              Container(
                                width: double.infinity,
                                padding: const EdgeInsets.all(13),
                                margin: const EdgeInsets.only(bottom: 14),
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(14),
                                  gradient: const LinearGradient(
                                    colors: [Color(0xFF102B43), Color(0xFF11213B)],
                                  ),
                                  border: Border.all(color: const Color(0xFF24516E)),
                                ),
                                child: Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    _statusChip('Active: ${_activeEngine.toUpperCase()}',
                                        _activeEngine != 'unavailable'),
                                    _statusChip('VAD: ${_activeVad.toUpperCase()}', true),
                                    _statusChip('Vosk', settings.voskModelLoaded),
                                    _statusChip('Whisper', settings.whisperAvailable),
                                    _statusChip('Microphone', settings.micAvailable),
                                  ],
                                ),
                              ),
                              _section(
                                title: 'Speech Recognition',
                                subtitle: 'Choose accuracy, speed and language behavior.',
                                icon: Icons.translate_rounded,
                                children: [
                                  _label('Recognition engine'),
                                  _dropdown(
                                    value: settings.recognitionEngine,
                                    items: const [
                                      DropdownMenuItem(value: 'auto', child: Text('Auto — Vosk while Whisper warms, then Whisper')),
                                      DropdownMenuItem(value: 'whisper', child: Text('Whisper — Natural Hindi / Hinglish')),
                                      DropdownMenuItem(value: 'vosk', child: Text('Vosk — Lightweight offline')),
                                    ],
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(recognitionEngine: value))
                                        : (_) {},
                                  ),
                                  if (settings.recognitionEngine != 'vosk') ...[
                                    const SizedBox(height: 13),
                                    _label('Whisper model'),
                                    _dropdown(
                                      value: settings.whisperModel,
                                      items: const [
                                        DropdownMenuItem(value: 'tiny', child: Text('Tiny — Fastest')),
                                        DropdownMenuItem(value: 'base', child: Text('Base — Recommended for 8 GB RAM')),
                                        DropdownMenuItem(value: 'small', child: Text('Small — Better accuracy, slower')),
                                      ],
                                      onChanged: controlsEnabled
                                          ? (value) => setState(() => _settings = settings.copyWith(whisperModel: value))
                                          : (_) {},
                                    ),
                                  ],
                                  const SizedBox(height: 13),
                                  _label('Recognition language'),
                                  _dropdown(
                                    value: settings.speechLanguage,
                                    items: const [
                                      DropdownMenuItem(value: 'auto', child: Text('Auto — Hindi, Hinglish & English')),
                                      DropdownMenuItem(value: 'hi-IN', child: Text('Hindi / Hinglish — India')),
                                      DropdownMenuItem(value: 'en-IN', child: Text('English — India')),
                                    ],
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(speechLanguage: value))
                                        : (_) {},
                                  ),
                                  const SizedBox(height: 13),
                                  _label('Voice activity detector'),
                                  _dropdown(
                                    value: settings.vadEngine,
                                    items: const [
                                      DropdownMenuItem(
                                        value: 'auto',
                                        child: Text('Auto — WebRTC preferred, RMS fallback'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'webrtc',
                                        child: Text('WebRTC VAD — speech-focused'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'adaptive_rms',
                                        child: Text('Adaptive RMS — compatibility mode'),
                                      ),
                                    ],
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(vadEngine: value))
                                        : (_) {},
                                  ),
                                ],
                              ),
                              _section(
                                title: 'Live Interruption & Listening',
                                subtitle: 'Freshy stops speaking as soon as you begin talking.',
                                icon: Icons.multitrack_audio_rounded,
                                children: [
                                  _switch(
                                    title: 'Interrupt Freshy while speaking',
                                    subtitle: 'VAD stops current audio, clears queued speech and preserves your first words.',
                                    value: settings.interruptWhileSpeaking,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(interruptWhileSpeaking: value))
                                        : (_) {},
                                  ),
                                  _label('Interruption sensitivity'),
                                  _dropdown(
                                    value: settings.interruptionSensitivity,
                                    items: const [
                                      DropdownMenuItem(value: 'low', child: Text('Low — Fewer accidental interruptions')),
                                      DropdownMenuItem(value: 'normal', child: Text('Normal — Recommended')),
                                      DropdownMenuItem(value: 'high', child: Text('High — Fastest response')),
                                    ],
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(interruptionSensitivity: value))
                                        : (_) {},
                                  ),
                                  const SizedBox(height: 8),
                                  _switch(
                                    title: 'Continuous background listening',
                                    subtitle: 'Resume listening automatically after Freshy finishes speaking.',
                                    value: settings.continuousListening,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(continuousListening: value))
                                        : (_) {},
                                  ),
                                  _switch(
                                    title: 'Wake word “Hello Freshy”',
                                    subtitle: 'Uses the lightweight local Vosk wake detector when available.',
                                    value: settings.wakeWordEnabled,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(wakeWordEnabled: value))
                                        : (_) {},
                                  ),
                                ],
                              ),
                              _section(
                                title: 'Fast Response Preparation',
                                subtitle: 'Build the question live, but execute only after you finish.',
                                icon: Icons.bolt_rounded,
                                children: [
                                  _switch(
                                    title: 'Live partial transcription',
                                    subtitle: 'Shows stable words while you are still speaking.',
                                    value: settings.partialProcessing,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(partialProcessing: value))
                                        : (_) {},
                                  ),
                                  _switch(
                                    title: 'Prepare one safe draft in the background',
                                    subtitle: 'Only non-tool questions; stale drafts are discarded to protect actions and tokens.',
                                    value: settings.fastResponsePreparation,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(fastResponsePreparation: value))
                                        : (_) {},
                                  ),
                                  _switch(
                                    title: 'Adaptive silence',
                                    subtitle: 'Wait longer after unfinished phrases and respond sooner to clear questions.',
                                    value: settings.adaptiveSilence,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(adaptiveSilence: value))
                                        : (_) {},
                                  ),
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      const Text('Reply after silence', style: TextStyle(color: Colors.white, fontSize: 12.5)),
                                      Text('${settings.responseSilenceSeconds.toStringAsFixed(1)} sec',
                                          style: const TextStyle(color: _cyan, fontWeight: FontWeight.w700)),
                                    ],
                                  ),
                                  Slider(
                                    value: settings.responseSilenceSeconds,
                                    min: 1,
                                    max: 5,
                                    divisions: 8,
                                    activeColor: _cyan,
                                    inactiveColor: _border,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(responseSilenceSeconds: value))
                                        : null,
                                  ),
                                ],
                              ),
                              _section(
                                title: 'Microphone & Noise',
                                subtitle: 'Select the input device and tune ambient-noise detection.',
                                icon: Icons.mic_rounded,
                                children: [
                                  _label('Input microphone'),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 12),
                                    decoration: BoxDecoration(
                                      color: _panelLight,
                                      borderRadius: BorderRadius.circular(11),
                                      border: Border.all(color: _border),
                                    ),
                                    child: DropdownButtonHideUnderline(
                                      child: DropdownButton<int?>(
                                        value: settings.deviceIndex != null && _devices.any((d) => d.id == settings.deviceIndex)
                                            ? settings.deviceIndex
                                            : null,
                                        isExpanded: true,
                                        dropdownColor: _panelLight,
                                        style: const TextStyle(color: Colors.white, fontSize: 13),
                                        items: [
                                          const DropdownMenuItem<int?>(value: null, child: Text('Default system microphone')),
                                          ..._devices.map((device) => DropdownMenuItem<int?>(
                                                value: device.id,
                                                child: Text(device.name),
                                              )),
                                        ],
                                        onChanged: controlsEnabled
                                            ? (value) => setState(() => _settings = value == null
                                                ? settings.copyWith(clearDeviceIndex: true)
                                                : settings.copyWith(deviceIndex: value))
                                            : null,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  _switch(
                                    title: 'Win + J push-to-talk',
                                    subtitle: 'Start a fresh listening turn from anywhere in Windows.',
                                    value: settings.hotkeyEnabled,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(hotkeyEnabled: value))
                                        : (_) {},
                                  ),
                                  _switch(
                                    title: 'Mute microphone',
                                    subtitle: 'Temporarily block all audio capture.',
                                    value: settings.muted,
                                    onChanged: controlsEnabled
                                        ? (value) => setState(() => _settings = settings.copyWith(muted: value))
                                        : (_) {},
                                  ),
                                  const SizedBox(height: 8),
                                  SizedBox(
                                    width: double.infinity,
                                    child: OutlinedButton.icon(
                                      onPressed: _isCalibrating ? null : _calibrateNoise,
                                      icon: _isCalibrating
                                          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: _cyan))
                                          : const Icon(Icons.graphic_eq_rounded, color: _cyan),
                                      label: Text(_isCalibrating ? 'Calibrating…' : 'Calibrate ambient noise'),
                                      style: OutlinedButton.styleFrom(
                                        foregroundColor: _cyan,
                                        side: const BorderSide(color: Color(0xFF2E7087)),
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
                                      ),
                                    ),
                                  ),
                                  if (_calibrationMessage != null) ...[
                                    const SizedBox(height: 8),
                                    Text(_calibrationMessage!, style: const TextStyle(color: Color(0xFF7DD3FC), fontSize: 11.5)),
                                  ],
                                ],
                              ),
                            ],
                          ),
                        ),
            ),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: const BoxDecoration(border: Border(top: BorderSide(color: _border))),
              child: Row(
                children: [
                  TextButton(
                    onPressed: _loadData,
                    child: const Text('Reload', style: TextStyle(color: _muted)),
                  ),
                  const Spacer(),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel', style: TextStyle(color: _muted)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: controlsEnabled ? _saveSettings : null,
                    icon: _isSaving
                        ? const SizedBox(width: 15, height: 15, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF06111E)))
                        : const Icon(Icons.save_rounded, size: 18),
                    label: const Text('Save Settings'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _cyan,
                      foregroundColor: const Color(0xFF06111E),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
