import 'dart:math' as math;
import 'package:flutter/material.dart';

enum OrbState { idle, listening, thinking, speaking, offline }

class FreshyVoiceOrb extends StatefulWidget {
  final OrbState state;
  final VoidCallback? onTap;
  final double size;
  final double audioLevel;
  final String liveText;
  final bool preparingResponse;

  const FreshyVoiceOrb({
    Key? key,
    required this.state,
    this.onTap,
    this.size = 260.0,
    this.audioLevel = 0,
    this.liveText = '',
    this.preparingResponse = false,
  }) : super(key: key);

  @override
  State<FreshyVoiceOrb> createState() => _FreshyVoiceOrbState();
}

class _FreshyVoiceOrbState extends State<FreshyVoiceOrb>
    with TickerProviderStateMixin {
  late final AnimationController _motion;
  late final AnimationController _glow;

  @override
  void initState() {
    super.initState();
    _motion = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3400),
    )..repeat();
    _glow = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1150),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _motion.dispose();
    _glow.dispose();
    super.dispose();
  }

  String get _label {
    switch (widget.state) {
      case OrbState.idle:
        return 'READY';
      case OrbState.listening:
        return widget.preparingResponse ? 'LISTENING + PREPARING' : 'LISTENING';
      case OrbState.thinking:
        return 'THINKING';
      case OrbState.speaking:
        return 'SPEAKING — TALK TO INTERRUPT';
      case OrbState.offline:
        return 'CORE OFFLINE';
    }
  }

  String get _hint {
    if (widget.liveText.trim().isNotEmpty) return widget.liveText.trim();
    switch (widget.state) {
      case OrbState.idle:
        return 'Tap the orb or say “Hello Freshy”';
      case OrbState.listening:
        return 'I am hearing every word…';
      case OrbState.thinking:
        return 'Preparing the quickest safe answer';
      case OrbState.speaking:
        return 'Start speaking anytime — I will stop';
      case OrbState.offline:
        return 'Start Freshy Core to continue';
    }
  }

  Color get _color {
    switch (widget.state) {
      case OrbState.idle:
        return const Color(0xFF2DD4BF);
      case OrbState.listening:
        return const Color(0xFF22D3EE);
      case OrbState.thinking:
        return const Color(0xFF8B5CF6);
      case OrbState.speaking:
        return const Color(0xFF38BDF8);
      case OrbState.offline:
        return const Color(0xFFEF4444);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_motion, _glow]),
      builder: (context, _) {
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            GestureDetector(
              onTap: widget.onTap,
              behavior: HitTestBehavior.opaque,
              child: MouseRegion(
                cursor: widget.onTap == null
                    ? SystemMouseCursors.basic
                    : SystemMouseCursors.click,
                child: CustomPaint(
                  size: Size.square(widget.size),
                  painter: _FreshyOrbPainter(
                    state: widget.state,
                    motion: _motion.value,
                    glow: _glow.value,
                    color: _color,
                    audioLevel: widget.audioLevel.clamp(0.0, 1.0).toDouble(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 18),
            AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: _color.withOpacity(0.08),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: _color.withOpacity(0.42)),
                boxShadow: [
                  BoxShadow(color: _color.withOpacity(0.14), blurRadius: 18),
                ],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: _color,
                      shape: BoxShape.circle,
                      boxShadow: [BoxShadow(color: _color, blurRadius: 7)],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _label,
                    style: TextStyle(
                      color: _color,
                      fontSize: 10.5,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.45,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            ConstrainedBox(
              constraints: BoxConstraints(maxWidth: widget.size * 1.22),
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 220),
                child: Text(
                  _hint,
                  key: ValueKey(_hint),
                  textAlign: TextAlign.center,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF9FB4D2),
                    fontSize: 12.5,
                    height: 1.45,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _FreshyOrbPainter extends CustomPainter {
  final OrbState state;
  final double motion;
  final double glow;
  final Color color;
  final double audioLevel;

  const _FreshyOrbPainter({
    required this.state,
    required this.motion,
    required this.glow,
    required this.color,
    required this.audioLevel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseRadius = size.shortestSide * 0.255;
    final listeningEnergy = state == OrbState.listening
        ? math.max(audioLevel, 0.18 + glow * 0.42)
        : 0.0;
    final speakingEnergy = state == OrbState.speaking
        ? 0.25 + (math.sin(motion * math.pi * 8).abs() * 0.45)
        : 0.0;
    final energy = math.max(listeningEnergy, speakingEnergy);

    if (state == OrbState.offline) {
      canvas.drawCircle(
        center,
        baseRadius,
        Paint()..color = const Color(0xFF1E293B),
      );
      canvas.drawCircle(
        center,
        baseRadius + 10,
        Paint()
          ..color = color.withOpacity(0.75)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
      return;
    }

    // Deep outer atmospheric glow: dim -> bright -> dim.
    final breathe = 0.92 + glow * 0.16 + energy * 0.24;
    final auraRadius = baseRadius * (2.25 + energy * 0.8) * breathe;
    final aura = RadialGradient(
      colors: [
        Colors.white.withOpacity(0.10 + glow * 0.06),
        color.withOpacity(0.34 + energy * 0.28),
        color.withOpacity(0.08),
        Colors.transparent,
      ],
      stops: const [0.0, 0.24, 0.60, 1.0],
    );
    canvas.drawCircle(
      center,
      auraRadius,
      Paint()..shader = aura.createShader(Rect.fromCircle(center: center, radius: auraRadius)),
    );

    // Expanding rings make listening feel alive and responsive.
    final ringCount = state == OrbState.listening ? 5 : 3;
    for (var i = 0; i < ringCount; i++) {
      final phase = (motion + i / ringCount) % 1.0;
      final radius = baseRadius * (1.18 + phase * (1.15 + energy * 0.5));
      final opacity = (1 - phase) * (state == OrbState.listening ? 0.34 : 0.18);
      canvas.drawCircle(
        center,
        radius,
        Paint()
          ..color = color.withOpacity(opacity)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2 + energy * 2.0,
      );
    }

    // Orbiting particles.
    final particlePaint = Paint()..color = color.withOpacity(0.80);
    for (var i = 0; i < 22; i++) {
      final angle = motion * math.pi * 2 + i * (math.pi * 2 / 22);
      final wobble = math.sin(angle * 3 + glow * math.pi) * 7;
      final radius = baseRadius * 1.42 + wobble + energy * 18;
      final point = center + Offset(math.cos(angle), math.sin(angle)) * radius;
      final dot = 0.8 + ((i % 4) * 0.32) + energy * 1.4;
      canvas.drawCircle(point, dot, particlePaint);
    }

    if (state == OrbState.thinking) {
      final arcPaint = Paint()
        ..color = color.withOpacity(0.95)
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 3;
      for (var i = 0; i < 4; i++) {
        canvas.drawArc(
          Rect.fromCircle(center: center, radius: baseRadius * (1.25 + i * 0.08)),
          motion * math.pi * 2 + i * 1.25,
          0.72,
          false,
          arcPaint..color = color.withOpacity(0.85 - i * 0.13),
        );
      }
    }

    // Glass shell.
    final shellRadius = baseRadius * (0.93 + glow * 0.08 + energy * 0.12);
    final shell = RadialGradient(
      center: const Alignment(-0.36, -0.42),
      radius: 0.95,
      colors: [
        Colors.white.withOpacity(0.98),
        color.withOpacity(0.95),
        Color.lerp(color, const Color(0xFF10233D), 0.52)!,
        const Color(0xFF07111F),
      ],
      stops: const [0.0, 0.18, 0.61, 1.0],
    );
    canvas.drawCircle(
      center,
      shellRadius,
      Paint()..shader = shell.createShader(Rect.fromCircle(center: center, radius: shellRadius)),
    );

    // Bright inner light that grows dramatically while listening.
    final lightRadius = baseRadius * (0.31 + glow * 0.12 + energy * 0.30);
    final light = RadialGradient(
      colors: [
        Colors.white,
        Colors.white.withOpacity(0.92),
        color.withOpacity(0.72),
        Colors.transparent,
      ],
      stops: const [0.0, 0.22, 0.58, 1.0],
    );
    canvas.drawCircle(
      center,
      lightRadius * 2.0,
      Paint()..shader = light.createShader(Rect.fromCircle(center: center, radius: lightRadius * 2.0)),
    );

    // Speaking waveform floats inside the core.
    if (state == OrbState.speaking) {
      final barPaint = Paint()
        ..color = Colors.white.withOpacity(0.94)
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 4;
      for (var i = -3; i <= 3; i++) {
        final phase = motion * math.pi * 10 + i * 0.85;
        final height = 10 + math.sin(phase).abs() * (20 + energy * 18);
        final x = center.dx + i * 10.0;
        canvas.drawLine(
          Offset(x, center.dy - height / 2),
          Offset(x, center.dy + height / 2),
          barPaint,
        );
      }
    }

    // Fine shell highlight.
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: shellRadius * 0.92),
      -2.62,
      1.75,
      false,
      Paint()
        ..color = Colors.white.withOpacity(0.36)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.1,
    );
  }

  @override
  bool shouldRepaint(covariant _FreshyOrbPainter oldDelegate) {
    return oldDelegate.state != state ||
        oldDelegate.motion != motion ||
        oldDelegate.glow != glow ||
        oldDelegate.color != color ||
        oldDelegate.audioLevel != audioLevel;
  }
}
