import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/chat_response.dart';
import '../../core/storage/profile_storage.dart';
import '../../core/storage/settings_storage.dart';
import '../../core/theme/airvlc_theme.dart';
import '../../core/voice/stt_service.dart';
import '../../core/voice/tts_service.dart';
import '../map/map_risk_screen.dart';
import '../stations_compare/compare_screen.dart';
import '../timeseries/timeseries_screen.dart';

class VoiceModeScreen extends StatefulWidget {
  final AirVLCApiClient api;
  final ProfileStorage profileStorage;

  const VoiceModeScreen({
    super.key,
    required this.api,
    required this.profileStorage,
  });

  @override
  State<VoiceModeScreen> createState() => _VoiceModeScreenState();
}

class _VoiceModeScreenState extends State<VoiceModeScreen>
    with SingleTickerProviderStateMixin {
  final SttService _stt = SttService();
  final TtsService _tts = TtsService();
  final SettingsStorage _settings = SettingsStorage();

  late final AnimationController _pulse;

  String _heardText = '';
  String _replyText = '';
  String _intent = '';
  ChatUiPayload? _uiPayload;
  bool _busy = false;
  String? _errorBanner;
  bool _ttsEnabled = true;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);
    _tts.init();
    _settings.getTtsEnabled(defaultValue: false).then((v) {
      if (mounted) setState(() => _ttsEnabled = v);
    });
  }

  @override
  void dispose() {
    _pulse.dispose();
    _tts.stop();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _toggleListen() async {
    if (_busy) return;
    setState(() {
      _errorBanner = null;
    });

    final ready = await _stt.init(
      onError: (e) =>
          setState(() => _errorBanner = 'Error reconocedor de voz: $e'),
    );
    if (!ready) {
      setState(() => _errorBanner =
          'speech_to_text no se pudo inicializar (¿simulador iOS?)');
      return;
    }

    setState(() {
      _busy = true;
      _heardText = '';
      _replyText = '';
      _intent = '';
      _uiPayload = null;
    });

    try {
      // Importante:
      // - iOS solo muestra el popup de permisos cuando *speech_to_text* intenta escuchar
      //   por primera vez. Por eso no forzamos redirección a Ajustes aquí: primero
      //   intentamos escuchar y dejamos que el sistema pida permisos.
      final spoken = await _stt.listenOnce(
        onPartial: (p) => setState(() => _heardText = p),
      );
      if (spoken.trim().isEmpty) {
        setState(() => _errorBanner = 'No te he entendido. Inténtalo otra vez.');
        return;
      }
      setState(() => _heardText = spoken);

      final ChatResponse r =
          await widget.api.chat(message: spoken, sessionId: 'voice_mode');
      setState(() {
        _replyText = r.reply;
        _intent = r.intent;
        _uiPayload = r.uiPayload;
      });
      if (_ttsEnabled) {
        await _tts.speak(r.reply);
      }
    } catch (e) {
      // Si faltan permisos, speech_to_text suele fallar aquí. Mostramos un mensaje accionable.
      final msg = e.toString();
      final looksLikePerm = msg.toLowerCase().contains('permission') ||
          msg.toLowerCase().contains('denied') ||
          msg.toLowerCase().contains('not authorized');
      setState(() => _errorBanner = looksLikePerm
          ? 'No tenemos permisos de micrófono/reconocimiento de voz. Ve a Ajustes → Privacidad y seguridad → Micrófono / Reconocimiento de voz y habilita AirVLC.'
          : 'No pude completar la consulta: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Modo voz'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _ttsEnabled ? Icons.volume_up : Icons.volume_off,
                  color: _ttsEnabled ? AirVLCTheme.primaryBlue : Colors.grey,
                ),
                Switch(
                  value: _ttsEnabled,
                  onChanged: (v) async {
                    setState(() => _ttsEnabled = v);
                    await _settings.setTtsEnabled(v);
                    if (!v) await _tts.stop();
                  },
                  activeColor: AirVLCTheme.primaryBlue,
                ),
              ],
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              if (_errorBanner != null)
                Card(
                  color: AirVLCTheme.levelDangerous.withOpacity(0.08),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline,
                            color: AirVLCTheme.levelDangerous),
                        const SizedBox(width: 8),
                        Expanded(child: Text(_errorBanner!)),
                      ],
                    ),
                  ),
                ),
              Expanded(child: _buildResponseArea()),
              const SizedBox(height: 16),
              _buildBigButton(),
              const SizedBox(height: 8),
              Text(
                _busy
                    ? 'Escuchando... toca para parar'
                    : 'Toca y habla. Te respondemos en voz alta.',
                style: const TextStyle(color: AirVLCTheme.textDark),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Misma navegación que [ChatScreen] cuando el backend envía `ui_payload`.
  void _handleUiPayload(ChatUiPayload payload) {
    switch (payload.action) {
      case 'open_map':
        final h = _horizonFromPayload(payload);
        Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => MapRiskScreen(
            api: widget.api,
            initialPollutant: payload.pollutant ?? 'pm25',
            initialHorizon: h,
          ),
        ));
        break;
      case 'open_station_detail':
        if (payload.station != null) {
          Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => TimeseriesScreen(
              api: widget.api,
              station: payload.station!,
              pollutant: payload.pollutant ?? 'pm25',
            ),
          ));
        }
        break;
      case 'open_comparison':
        Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => CompareScreen(api: widget.api),
        ));
        break;
      case 'open_advice':
        if (payload.cta == 'ver_mapa') {
          Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => MapRiskScreen(api: widget.api),
          ));
        }
        break;
    }
  }

  int _horizonFromPayload(ChatUiPayload p) {
    final h = p.horizon;
    if (h == null || h == 'now') return 0;
    return int.tryParse(h) ?? 0;
  }

  IconData _iconForAction(String action) {
    switch (action) {
      case 'open_map':
        return Icons.map;
      case 'open_station_detail':
        return Icons.show_chart;
      case 'open_comparison':
        return Icons.compare_arrows;
      case 'open_advice':
        return Icons.map;
      default:
        return Icons.arrow_forward;
    }
  }

  String _labelForAction(String action) {
    switch (action) {
      case 'open_map':
        return 'Ver mapa';
      case 'open_station_detail':
        return 'Ver serie temporal';
      case 'open_comparison':
        return 'Ver comparación';
      case 'open_advice':
        return 'Ver mapa de riesgo';
      default:
        return 'Abrir';
    }
  }

  Widget _buildResponseArea() {
    return ListView(
      children: [
        if (_heardText.isNotEmpty)
          Card(
            child: ListTile(
              leading: const Icon(Icons.record_voice_over),
              title: const Text('Has dicho:'),
              subtitle: Text(_heardText),
            ),
          ),
        if (_replyText.isNotEmpty)
          Card(
            color: AirVLCTheme.primaryBlue.withOpacity(0.06),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.assistant, color: AirVLCTheme.primaryBlue),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _intent.isEmpty ? 'AirVLC' : _intent,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: AirVLCTheme.textDark,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _replyText,
                          style: const TextStyle(
                            color: AirVLCTheme.textDark,
                            fontSize: 15,
                          ),
                        ),
                        if (_uiPayload != null) ...[
                          const SizedBox(height: 10),
                          OutlinedButton.icon(
                            onPressed: () => _handleUiPayload(_uiPayload!),
                            icon: Icon(_iconForAction(_uiPayload!.action),
                                size: 16),
                            label: Text(
                              _labelForAction(_uiPayload!.action),
                              style: const TextStyle(fontSize: 12),
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AirVLCTheme.primaryBlue,
                              side: BorderSide(
                                color:
                                    AirVLCTheme.primaryBlue.withOpacity(0.5),
                              ),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 4,
                              ),
                              minimumSize: const Size(0, 32),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildBigButton() {
    return GestureDetector(
      onTap: _toggleListen,
      child: AnimatedBuilder(
        animation: _pulse,
        builder: (context, child) {
          final scale = _busy ? 1 + 0.06 * _pulse.value : 1.0;
          return Transform.scale(
            scale: scale,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                color: _busy
                    ? AirVLCTheme.levelDangerous
                    : AirVLCTheme.valenciaOrange,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: (_busy
                            ? AirVLCTheme.levelDangerous
                            : AirVLCTheme.valenciaOrange)
                        .withOpacity(0.35),
                    blurRadius: 24,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Icon(
                _busy ? Icons.stop : Icons.mic,
                color: Colors.white,
                size: 64,
              ),
            ),
          );
        },
      ),
    );
  }
}
