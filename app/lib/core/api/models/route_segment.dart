import 'pollutant_reading.dart';
import 'prediction.dart';

/// Un tramo de la ruta saludable (estación intermedia + ICA).
class RouteSegment {
  final String station;
  final Prediction predictions;
  final Map<String, PollutantReading> pollutants;
  final WorstPollutant worst;
  final double? lat;
  final double? lon;

  const RouteSegment({
    required this.station,
    required this.predictions,
    required this.pollutants,
    required this.worst,
    this.lat,
    this.lon,
  });

  factory RouteSegment.fromJson(Map<String, dynamic> j) {
    final pollutantsRaw = (j['pollutants'] as Map?)?.cast<String, dynamic>() ?? {};
    final readings = <String, PollutantReading>{};
    pollutantsRaw.forEach((k, v) {
      readings[k] = PollutantReading.fromJson(
          k, (v as Map).cast<String, dynamic>());
    });

    final loc = (j['location'] as Map?)?.cast<String, dynamic>();
    return RouteSegment(
      station: j['station']?.toString() ?? '',
      predictions: Prediction.fromJson(
          (j['predictions'] as Map).cast<String, dynamic>()),
      pollutants: readings,
      worst:
          WorstPollutant.fromJson((j['worst'] as Map).cast<String, dynamic>()),
      lat: (loc?['lat'] as num?)?.toDouble(),
      lon: (loc?['lon'] as num?)?.toDouble(),
    );
  }
}

/// Respuesta completa de `/api/v2/route`.
class RouteResponse {
  final String fromStation;
  final String toStation;
  final List<RouteSegment> segments;
  final int worstSegmentIndex;
  final String? replyText;

  const RouteResponse({
    required this.fromStation,
    required this.toStation,
    required this.segments,
    required this.worstSegmentIndex,
    this.replyText,
  });

  factory RouteResponse.fromJson(Map<String, dynamic> j) {
    final segs = (j['segments'] as List? ?? [])
        .map((e) => RouteSegment.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
    return RouteResponse(
      fromStation: j['from_station']?.toString() ?? '',
      toStation: j['to_station']?.toString() ?? '',
      segments: segs,
      worstSegmentIndex: (j['worst_segment_index'] as num?)?.toInt() ?? -1,
      replyText: j['reply_text']?.toString(),
    );
  }
}
