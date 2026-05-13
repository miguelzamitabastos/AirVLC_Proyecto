import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/chat_response.dart';
import '../../core/storage/settings_storage.dart';
import '../../core/theme/airvlc_theme.dart';
import '../../core/voice/tts_service.dart';
import '../map/map_risk_screen.dart';
import '../timeseries/timeseries_screen.dart';
import '../stations_compare/compare_screen.dart';

/// Sprint 7 — Chat mejorado con soporte `ui_payload`.
///
/// Cuando el backend devuelve un `ui_payload`, se muestra un botón
/// de acción rápida que navega a la vista correspondiente (mapa,
/// serie temporal, comparación).
class ChatScreen extends StatefulWidget {
  final AirVLCApiClient api;
  const ChatScreen({super.key, required this.api});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messages = <_ChatMsg>[
    const _ChatMsg(
      isUser: false,
      text:
          'Hola, soy AirVLC. Pregúntame por la calidad del aire de cualquier estación de Valencia.',
    ),
  ];
  final _textController = TextEditingController();
  final _scroll = ScrollController();
  final TtsService _tts = TtsService();
  final SettingsStorage _settings = SettingsStorage();
  bool _loading = false;
  bool _canSend = false;
  bool _ttsEnabled = false;

  @override
  void dispose() {
    _textController.dispose();
    _scroll.dispose();
    _tts.stop();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _tts.init();
    _settings.getTtsEnabled(defaultValue: false).then((v) {
      if (mounted) setState(() => _ttsEnabled = v);
    });
    _textController.addListener(() {
      final next = _textController.text.trim().isNotEmpty;
      if (next != _canSend && mounted) {
        setState(() => _canSend = next);
      }
    });
  }

  Future<void> _send(String text) async {
    if (text.trim().isEmpty) return;
    _textController.clear();
    setState(() {
      _messages.add(_ChatMsg(isUser: true, text: text));
      _loading = true;
    });
    _scrollDown();
    try {
      final ChatResponse r = await widget.api.chat(message: text);
      setState(() {
        _messages.add(_ChatMsg(
          isUser: false,
          text: r.reply,
          intent: r.intent,
          uiPayload: r.uiPayload,
        ));
      });
      if (_ttsEnabled) {
        _tts.speak(r.reply);
      }
    } catch (e) {
      setState(() {
        _messages.add(_ChatMsg(
          isUser: false,
          text: 'No pude conectar con el backend: $e',
          isError: true,
        ));
      });
    } finally {
      setState(() => _loading = false);
      _scrollDown();
    }
  }

  void _scrollDown() {
    Future.delayed(const Duration(milliseconds: 80), () {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  /// Sprint 7: Navega según el ui_payload del backend.
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat'),
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
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (_, i) => _bubble(_messages[i]),
            ),
          ),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: LinearProgressIndicator(minHeight: 2),
            ),
          _input(),
        ],
      ),
    );
  }

  Widget _bubble(_ChatMsg m) {
    final bg = m.isUser
        ? AirVLCTheme.primaryBlue
        : (m.isError ? AirVLCTheme.levelDangerous : Colors.white);
    final fg = m.isUser || m.isError ? Colors.white : AirVLCTheme.textDark;
    return Align(
      alignment: m.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(m.isUser ? 16 : 0),
            bottomRight: Radius.circular(m.isUser ? 0 : 16),
          ),
          boxShadow: const [
            BoxShadow(
              color: Color(0x14000000),
              blurRadius: 6,
              offset: Offset(0, 2),
            )
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (m.intent != null && !m.isUser)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  m.intent!,
                  style: TextStyle(
                    color: fg.withOpacity(0.55),
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            Text(m.text, style: TextStyle(color: fg, fontSize: 15)),
            // Sprint 7: CTA button from ui_payload
            if (m.uiPayload != null && !m.isUser)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: OutlinedButton.icon(
                  onPressed: () => _handleUiPayload(m.uiPayload!),
                  icon: Icon(_iconForAction(m.uiPayload!.action), size: 16),
                  label: Text(
                    _labelForAction(m.uiPayload!.action),
                    style: const TextStyle(fontSize: 12),
                  ),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AirVLCTheme.primaryBlue,
                    side: BorderSide(color: AirVLCTheme.primaryBlue.withOpacity(0.5)),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    minimumSize: const Size(0, 32),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
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

  Widget _input() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _textController,
                decoration: InputDecoration(
                  hintText: 'Pregunta sobre PM2.5, NO₂, O₃...',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(28),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18, vertical: 12),
                ),
                onSubmitted: _send,
              ),
            ),
            const SizedBox(width: 8),
            FloatingActionButton.small(
              onPressed: (!_loading && _canSend)
                  ? () => _send(_textController.text)
                  : null,
              backgroundColor:
                  (!_loading && _canSend) ? AirVLCTheme.primaryBlue : Colors.grey,
              child: const Icon(Icons.send, color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatMsg {
  final bool isUser;
  final String text;
  final String? intent;
  final bool isError;
  final ChatUiPayload? uiPayload;
  const _ChatMsg({
    required this.isUser,
    required this.text,
    this.intent,
    this.isError = false,
    this.uiPayload,
  });
}
