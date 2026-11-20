import 'dart:async';
import 'package:flutter/material.dart';
import 'models/chat_message.dart';
import 'models/freshy_status.dart';
import 'services/freshy_api_service.dart';
import 'widgets/action_chips.dart';
import 'widgets/chat_bubble.dart';
import 'widgets/freshy_voice_orb.dart';
import 'widgets/status_indicator.dart';
import 'widgets/tts_settings_dialog.dart';
import 'widgets/voice_settings_dialog.dart';
import 'widgets/memory_center_dialog.dart';
import 'widgets/live_voice_settings_dialog.dart';

void main() => runApp(const FreshyApp());

class FreshyApp extends StatelessWidget {
  const FreshyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Freshy AI Assistant',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF06101F),
        primaryColor: const Color(0xFF22D3EE),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF22D3EE),
          secondary: Color(0xFF3B82F6),
          surface: Color(0xFF101A2D),
        ),
        textSelectionTheme: const TextSelectionThemeData(
          cursorColor: Color(0xFF22D3EE),
          selectionColor: Color(0x553B82F6),
        ),
      ),
      home: const FreshyHomeScreen(),
    );
  }
}

class FreshyHomeScreen extends StatefulWidget {
  const FreshyHomeScreen({Key? key}) : super(key: key);

  @override
  State<FreshyHomeScreen> createState() => _FreshyHomeScreenState();
}

class _FreshyHomeScreenState extends State<FreshyHomeScreen> {
  static const _cyan = Color(0xFF22D3EE);
  static const _blue = Color(0xFF3B82F6);
  static const _panel = Color(0xFF0D1729);
  static const _panelLight = Color(0xFF121F35);
  static const _border = Color(0xFF223753);
  static const _muted = Color(0xFF8EA3C2);

  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FreshyApiService _apiService = FreshyApiService();

  final List<ChatMessage> _messages = [];
  FreshyStatus _status = FreshyStatus.idle;
  bool _isConnected = false;
  bool _healthPolling = false;
  bool _voicePolling = false;
  Timer? _healthTimer;
  Timer? _voiceTimer;

  int _lastProcessedResultId = 0;
  String _lastProcessedResultToken = '';
  String _livePartialTranscript = '';
  double _inputLevel = 0;
  bool _preparingResponse = false;
  String _activeEngine = 'offline';
  String _activeVad = 'adaptive_rms';
  double _silenceWindow = 3.0;
  int _memoryCount = 0;
  bool _memoryEnabled = false;
  bool _liveMode = false;
  bool _liveConnected = false;
  String _liveModel = '';
  String _liveVoice = '';
  double? _liveLatencySeconds;

  @override
  void initState() {
    super.initState();
    _addInitialGreeting();
    _checkCoreConnection();
    _healthTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _checkCoreConnection(),
    );
    _voiceTimer = Timer.periodic(
      const Duration(milliseconds: 250),
      (_) => _pollVoiceState(),
    );
  }

  @override
  void dispose() {
    _healthTimer?.cancel();
    _voiceTimer?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _addInitialGreeting() {
    _messages.add(
      ChatMessage(
        id: 'welcome',
        sender: 'freshy',
        text:
            'Freshy Phase 6A is ready with safer chat actions, URL-free spoken confirmations, persistent memory, Standard voice mode, and an optional low-latency Gemini Live voice agent.',
        timestamp: DateTime.now(),
        intentName: 'NATURAL_VOICE_READY',
      ),
    );
  }

  Future<void> _checkCoreConnection() async {
    if (_healthPolling) return;
    _healthPolling = true;
    try {
      final connected = await _apiService.checkHealth();
      if (!mounted) return;
      if (connected != _isConnected) {
        setState(() {
          _isConnected = connected;
          if (!connected) {
            _status = FreshyStatus.idle;
            _livePartialTranscript = '';
            _inputLevel = 0;
            _activeEngine = 'offline';
          }
        });
      }
      if (connected) {
        await _pollVoiceState();
        if (!_memoryEnabled && _memoryCount == 0) {
          await _refreshMemoryStatus();
        }
      }
    } finally {
      _healthPolling = false;
    }
  }

  Future<void> _pollVoiceState() async {
    if (!_isConnected || _voicePolling) return;
    _voicePolling = true;
    try {
      final voiceStatus = await _apiService.getVoiceStatus();
      if (!mounted || voiceStatus['backend_available'] == false) return;

      final isListening = voiceStatus['is_listening'] == true;
      final isCalibrating = voiceStatus['is_calibrating'] == true;
      final freshyStatus = voiceStatus['freshy_status']?.toString() ?? 'idle';
      final partial = voiceStatus['partial_transcript']?.toString() ?? '';
      final currentResultId = (voiceStatus['result_id'] as num?)?.toInt() ?? 0;
      final currentResultToken = voiceStatus['result_token']?.toString() ?? '';
      final ttsSpeaking = voiceStatus['tts_is_speaking'] == true;
      final ttsQueue = (voiceStatus['tts_queue_size'] as num?)?.toInt() ?? 0;
      final level = (voiceStatus['input_level'] as num?)?.toDouble() ?? 0;
      final conversationMode = voiceStatus['conversation_mode']?.toString() ?? 'standard';
      final liveMetrics = voiceStatus['live_metrics'] is Map
          ? Map<String, dynamic>.from(voiceStatus['live_metrics'] as Map)
          : <String, dynamic>{};
      final durations = liveMetrics['durations'] is Map
          ? Map<String, dynamic>.from(liveMetrics['durations'] as Map)
          : <String, dynamic>{};

      var addedVoiceResult = false;
      var memoryChanged = false;
      setState(() {
        _livePartialTranscript = partial == 'Transcribing…' ? '' : partial;
        _inputLevel = level.clamp(0.0, 1.0).toDouble();
        _preparingResponse = voiceStatus['preparing_response'] == true ||
            voiceStatus['prepared_response_ready'] == true;
        _activeEngine =
            voiceStatus['recognition_engine_active']?.toString() ?? _activeEngine;
        _activeVad = voiceStatus['vad_engine']?.toString() ?? _activeVad;
        _silenceWindow =
            (voiceStatus['adaptive_silence_seconds'] as num?)?.toDouble() ??
                _silenceWindow;
        _liveMode = conversationMode == 'live';
        _liveConnected = voiceStatus['live_connected'] == true;
        _liveModel = voiceStatus['live_model']?.toString() ?? '';
        _liveVoice = voiceStatus['live_voice']?.toString() ?? '';
        _liveLatencySeconds =
            (durations['speech_to_first_audio_seconds'] as num?)?.toDouble();

        final isNewResult = currentResultId > 0 &&
            (currentResultToken.isNotEmpty
                ? currentResultToken != _lastProcessedResultToken
                : currentResultId != _lastProcessedResultId);
        if (isNewResult) {
          _lastProcessedResultId = currentResultId;
          _lastProcessedResultToken = currentResultToken;
          final transcript = voiceStatus['final_transcript']?.toString() ?? '';
          final reply = voiceStatus['assistant_reply']?.toString() ?? '';
          final intent = voiceStatus['intent']?.toString() ?? 'UNKNOWN';
          final actionExecuted = voiceStatus['action_executed'] == true;
          memoryChanged = intent.toUpperCase() == 'MEMORY';
          if (transcript.trim().isNotEmpty) {
            _messages.add(
              ChatMessage(
                id: 'voice-user-$currentResultId',
                sender: 'user',
                text: transcript,
                timestamp: DateTime.now(),
              ),
            );
            addedVoiceResult = true;
          }
          if (reply.trim().isNotEmpty) {
            _messages.add(
              ChatMessage(
                id: 'voice-freshy-$currentResultId',
                sender: 'freshy',
                text: reply,
                timestamp: DateTime.now(),
                intentName: intent,
                actionExecuted: actionExecuted,
              ),
            );
            addedVoiceResult = true;
          }
        }

        if (isListening || isCalibrating || freshyStatus == 'listening') {
          _status = FreshyStatus.listening;
        } else if (freshyStatus == 'thinking') {
          _status = FreshyStatus.thinking;
        } else if (ttsSpeaking || ttsQueue > 0 || freshyStatus == 'speaking') {
          _status = FreshyStatus.speaking;
        } else {
          _status = FreshyStatus.idle;
        }
      });
      if (addedVoiceResult) _scrollToBottom();
      if (memoryChanged) await _refreshMemoryStatus();
    } finally {
      _voicePolling = false;
    }
  }

  Future<void> _sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    _textController.clear();
    setState(() {
      _messages.add(
        ChatMessage(
          id: 'typed-${DateTime.now().microsecondsSinceEpoch}',
          sender: 'user',
          text: trimmed,
          timestamp: DateTime.now(),
        ),
      );
      _status = FreshyStatus.thinking;
    });
    _scrollToBottom();

    try {
      if (_liveMode) {
        final liveResult = await _apiService.sendLiveText(trimmed);
        if (!mounted) return;
        if (!liveResult.accepted) {
          setState(() => _status = FreshyStatus.idle);
          _showError(liveResult.reason);
        }
        return;
      }
      final response = await _apiService.sendMessage(trimmed);
      if (!mounted) return;
      setState(() {
        _messages.add(
          ChatMessage(
            id: 'reply-${DateTime.now().microsecondsSinceEpoch}',
            sender: 'freshy',
            text: response.reply,
            timestamp: DateTime.now(),
            intentName: response.intentName,
            actionExecuted: response.actionExecuted,
          ),
        );
        _status = response.freshyStatus == 'speaking'
            ? FreshyStatus.speaking
            : FreshyStatus.idle;
      });
      _scrollToBottom();
      if (response.memoryUsed || response.memoryPending ||
          response.provider == 'memory') {
        await _refreshMemoryStatus();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _status = FreshyStatus.idle;
        _messages.add(
          ChatMessage(
            id: 'error-${DateTime.now().microsecondsSinceEpoch}',
            sender: 'freshy',
            text: 'Freshy Core could not complete that request: $error',
            timestamp: DateTime.now(),
            intentName: 'CONNECTION_ERROR',
          ),
        );
      });
      _scrollToBottom();
    }
  }

  void _openTtsSettings() {
    showDialog(
      context: context,
      builder: (_) => TtsSettingsDialog(apiService: _apiService),
    );
  }

  void _openVoiceSettings() {
    showDialog(
      context: context,
      builder: (_) => VoiceSettingsDialog(apiService: _apiService),
    ).then((_) => _pollVoiceState());
  }

  void _openLiveVoiceSettings() {
    showDialog(
      context: context,
      builder: (_) => LiveVoiceSettingsDialog(apiService: _apiService),
    ).then((_) => _pollVoiceState());
  }

  Future<void> _refreshMemoryStatus() async {
    final status = await _apiService.getMemoryStatus();
    if (!mounted || status == null) return;
    setState(() {
      _memoryCount = status.memoryCount;
      _memoryEnabled = status.enabled;
    });
  }

  void _openMemoryCenter() {
    showDialog(
      context: context,
      builder: (_) => MemoryCenterDialog(apiService: _apiService),
    ).then((_) => _refreshMemoryStatus());
  }

  Future<void> _toggleMicListening() async {
    if (!_isConnected) return;
    if (_liveMode) {
      final result = _liveConnected
          ? await _apiService.stopLiveSession()
          : await _apiService.startLiveSession();
      if (!mounted) return;
      if (!result.accepted) _showError(result.reason);
      await Future<void>.delayed(const Duration(milliseconds: 300));
      await _pollVoiceState();
      return;
    }
    if (_status == FreshyStatus.listening) {
      final result = await _apiService.stopVoiceListening();
      if (!mounted) return;
      if (result.accepted) {
        setState(() {
          _status = FreshyStatus.idle;
          _livePartialTranscript = '';
        });
      } else {
        _showError(result.reason);
      }
      return;
    }

    setState(() => _status = FreshyStatus.listening);
    final result = await _apiService.startVoiceListening();
    if (!mounted) return;
    if (!result.accepted) {
      setState(() => _status = FreshyStatus.idle);
      _showError(result.reason);
    }
  }

  Future<void> _onOrbTap() async {
    if (!_isConnected) return;
    if (_liveMode) {
      if (_status == FreshyStatus.speaking) {
        await _apiService.interruptLiveSession();
      } else {
        await _toggleMicListening();
      }
      await _pollVoiceState();
      return;
    }
    if (_status == FreshyStatus.speaking) {
      await _apiService.stopTtsSpeech();
      final result = await _apiService.startVoiceListening();
      if (!mounted) return;
      setState(() => _status =
          result.accepted ? FreshyStatus.listening : FreshyStatus.idle);
      if (!result.accepted) _showError(result.reason);
    } else {
      await _toggleMicListening();
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: const Color(0xFFB91C1C),
      ),
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  OrbState get _orbState {
    if (!_isConnected) return OrbState.offline;
    switch (_status) {
      case FreshyStatus.idle:
        return OrbState.idle;
      case FreshyStatus.listening:
        return OrbState.listening;
      case FreshyStatus.thinking:
        return OrbState.thinking;
      case FreshyStatus.speaking:
        return OrbState.speaking;
    }
  }

  Widget _header() {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      decoration: const BoxDecoration(
        color: Color(0xE90A1425),
        border: Border(bottom: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(13),
              gradient: const LinearGradient(colors: [_cyan, _blue]),
              boxShadow: const [
                BoxShadow(color: Color(0x5522D3EE), blurRadius: 18),
              ],
            ),
            child: const Icon(Icons.auto_awesome_rounded,
                color: Color(0xFF06101F), size: 22),
          ),
          const SizedBox(width: 12),
          const Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'FRESHY AI',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.7,
                ),
              ),
              SizedBox(height: 2),
              Text(
                'Real-Time Live Voice Agent • Phase 6A',
                style: TextStyle(color: _muted, fontSize: 10.5),
              ),
            ],
          ),
          const Spacer(),
          IconButton(
            tooltip: 'Live Voice Agent settings',
            onPressed: _openLiveVoiceSettings,
            icon: Icon(
              Icons.wifi_tethering_rounded,
              color: _liveConnected ? const Color(0xFF38EF7D) : _cyan,
            ),
          ),
          Stack(
            clipBehavior: Clip.none,
            children: [
              IconButton(
                tooltip: 'Memory Center',
                onPressed: _openMemoryCenter,
                icon: Icon(
                  Icons.psychology_alt_rounded,
                  color: _memoryEnabled ? _cyan : _muted,
                ),
              ),
              if (_memoryCount > 0)
                Positioned(
                  right: 1,
                  top: 1,
                  child: Container(
                    constraints: const BoxConstraints(minWidth: 17, minHeight: 17),
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF7C3AED),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: const Color(0xFF0A1425), width: 1.5),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      _memoryCount > 99 ? '99+' : '$_memoryCount',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 8,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ),
            ],
          ),
          IconButton(
            tooltip: 'Natural conversation settings',
            onPressed: _openVoiceSettings,
            icon: const Icon(Icons.hearing_rounded, color: _cyan),
          ),
          IconButton(
            tooltip: 'Natural voice settings',
            onPressed: _openTtsSettings,
            icon: const Icon(Icons.record_voice_over_rounded, color: _cyan),
          ),
          const SizedBox(width: 8),
          StatusIndicator(status: _status, isConnected: _isConnected),
        ],
      ),
    );
  }

  Widget _metric({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: _panelLight.withOpacity(0.72),
          borderRadius: BorderRadius.circular(13),
          border: Border.all(color: _border),
        ),
        child: Row(
          children: [
            Icon(icon, color: _cyan, size: 17),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: const TextStyle(color: _muted, fontSize: 9.5)),
                  const SizedBox(height: 2),
                  Text(value,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 11.5,
                          fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _assistantPanel(double orbSize) {
    return Container(
      margin: const EdgeInsets.fromLTRB(18, 18, 9, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: const Color(0xFF204563)),
        gradient: const RadialGradient(
          center: Alignment(0, -0.15),
          radius: 1.15,
          colors: [Color(0xFF112D43), Color(0xFF0B182A), Color(0xFF07111F)],
        ),
        boxShadow: const [
          BoxShadow(color: Color(0x55000000), blurRadius: 32, offset: Offset(0, 16)),
        ],
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(painter: _GridPainter()),
          ),
          Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                Row(
                  children: [
                    const Text('VOICE CORE',
                        style: TextStyle(
                            color: Color(0xFFBDEDFC),
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.6)),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                      decoration: BoxDecoration(
                        color: _cyan.withOpacity(0.09),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: _cyan.withOpacity(0.30)),
                      ),
                      child: Text(
                        _liveMode ? (_liveConnected ? 'LIVE SESSION' : 'LIVE READY') : (_isConnected ? 'STANDARD' : 'OFFLINE'),
                        style: TextStyle(
                            color: _isConnected ? _cyan : const Color(0xFFEF4444),
                            fontSize: 9.5,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.2),
                      ),
                    ),
                  ],
                ),
                Expanded(
                  child: Center(
                    child: FreshyVoiceOrb(
                      state: _orbState,
                      onTap: _onOrbTap,
                      size: orbSize,
                      audioLevel: _inputLevel,
                      liveText: _livePartialTranscript,
                      preparingResponse: _preparingResponse,
                    ),
                  ),
                ),
                Row(
                  children: [
                    _metric(
                      icon: Icons.translate_rounded,
                      label: 'RECOGNITION',
                      value: _liveMode ? 'GEMINI LIVE' : _activeEngine.toUpperCase(),
                    ),
                    const SizedBox(width: 8),
                    _metric(
                      icon: Icons.graphic_eq_rounded,
                      label: 'VOICE ACTIVITY',
                      value: _liveMode ? 'LIVE AAD + LOCAL' : _activeVad.toUpperCase(),
                    ),
                    const SizedBox(width: 8),
                    _metric(
                      icon: Icons.timer_outlined,
                      label: _liveMode ? 'FIRST AUDIO' : 'SILENCE WAIT',
                      value: _liveMode
                          ? (_liveLatencySeconds == null ? '--' : '${_liveLatencySeconds!.toStringAsFixed(2)} SEC')
                          : '${_silenceWindow.toStringAsFixed(1)} SEC',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chatPanel() {
    return Container(
      margin: const EdgeInsets.fromLTRB(9, 18, 18, 18),
      decoration: BoxDecoration(
        color: _panel,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: _border),
        boxShadow: const [
          BoxShadow(color: Color(0x55000000), blurRadius: 32, offset: Offset(0, 16)),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(18, 14, 12, 10),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: _border)),
            ),
            child: Row(
              children: [
                const Icon(Icons.forum_rounded, color: _cyan, size: 19),
                const SizedBox(width: 9),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Conversation',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            fontWeight: FontWeight.w800)),
                    Text('Voice and typed messages stay in one session',
                        style: TextStyle(color: _muted, fontSize: 10)),
                  ],
                ),
                const Spacer(),
                IconButton(
                  tooltip: 'Clear this conversation',
                  onPressed: () async {
                    final cleared = await _apiService.clearConversation();
                    if (!mounted) return;
                    if (cleared) {
                      setState(() {
                        _messages.clear();
                        _addInitialGreeting();
                      });
                    }
                  },
                  icon: const Icon(Icons.delete_sweep_outlined, color: _muted),
                ),
              ],
            ),
          ),
          ActionChips(onChipTap: _sendMessage),
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.only(bottom: 8),
              itemCount: _messages.length,
              itemBuilder: (_, index) => ChatBubble(message: _messages[index]),
            ),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 180),
            child: (_status == FreshyStatus.listening ||
                    _livePartialTranscript.isNotEmpty)
                ? Container(
                    width: double.infinity,
                    margin: const EdgeInsets.fromLTRB(14, 6, 14, 8),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0B2C3D),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFF1E667B)),
                    ),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            value: _inputLevel <= 0 ? null : _inputLevel,
                            color: _cyan,
                            backgroundColor: const Color(0xFF164E63),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            _livePartialTranscript.isNotEmpty
                                ? _livePartialTranscript
                                : 'Listening… speak naturally and pause when finished.',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFFBDEDFC),
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ),
                        if (_preparingResponse)
                          const Padding(
                            padding: EdgeInsets.only(left: 8),
                            child: Tooltip(
                              message: 'Preparing one safe draft in the background',
                              child: Icon(Icons.bolt_rounded, color: Color(0xFFFBBF24), size: 18),
                            ),
                          ),
                      ],
                    ),
                  )
                : const SizedBox.shrink(),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            decoration: const BoxDecoration(
              color: Color(0xFF0A1425),
              border: Border(top: BorderSide(color: _border)),
            ),
            child: Row(
              children: [
                Container(
                  decoration: BoxDecoration(
                    color: _status == FreshyStatus.listening
                        ? const Color(0xFF3A1630)
                        : _panelLight,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: _status == FreshyStatus.listening
                          ? const Color(0xFFF43F5E)
                          : _border,
                    ),
                  ),
                  child: IconButton(
                    onPressed: _toggleMicListening,
                    tooltip: _status == FreshyStatus.listening
                        ? 'Stop listening'
                        : 'Start listening',
                    icon: Icon(
                      _status == FreshyStatus.listening
                          ? Icons.mic_rounded
                          : Icons.mic_none_rounded,
                      color: _status == FreshyStatus.listening
                          ? const Color(0xFFFF6B87)
                          : _cyan,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _textController,
                    style: const TextStyle(color: Colors.white, fontSize: 13.5),
                    decoration: InputDecoration(
                      hintText: 'Ask Freshy anything…',
                      hintStyle: const TextStyle(color: Color(0xFF607896)),
                      filled: true,
                      fillColor: _panelLight,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
                    ),
                    onSubmitted: _sendMessage,
                  ),
                ),
                const SizedBox(width: 9),
                Container(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: const LinearGradient(colors: [_cyan, _blue]),
                    boxShadow: const [BoxShadow(color: Color(0x4422D3EE), blurRadius: 14)],
                  ),
                  child: IconButton(
                    onPressed: () => _sendMessage(_textController.text),
                    icon: const Icon(Icons.arrow_upward_rounded, color: Color(0xFF06101F)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          _header(),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 920;
                if (wide) {
                  final orbSize = (constraints.maxHeight * 0.47)
                      .clamp(230.0, 340.0)
                      .toDouble();
                  return Row(
                    children: [
                      Expanded(flex: 5, child: _assistantPanel(orbSize)),
                      Expanded(flex: 6, child: _chatPanel()),
                    ],
                  );
                }
                return Column(
                  children: [
                    SizedBox(
                      height: (constraints.maxHeight * 0.48)
                          .clamp(330.0, 470.0)
                          .toDouble(),
                      child: _assistantPanel(210),
                    ),
                    Expanded(child: _chatPanel()),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF4DC7E3).withOpacity(0.045)
      ..strokeWidth = 1;
    const spacing = 34.0;
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
