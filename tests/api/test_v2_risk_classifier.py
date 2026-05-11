from src.ml.risk_classifier_v2 import RiskClassifierV2


def test_risk_classifier_v2_worst_pollutant():
    rc = RiskClassifierV2()
    payload = rc.classify_multi(pm25=10, no2=120, o3=80, station="Politécnico")
    assert payload["worst"]["pollutant"] == "no2"
    assert payload["worst"]["level"] in {"moderado", "malo", "peligroso"}
    assert "reply_text" in payload
    assert "PM2.5" in payload["reply_text"]
    assert "NO₂" in payload["reply_text"]
    assert "O₃" in payload["reply_text"]

