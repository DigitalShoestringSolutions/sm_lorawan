FROM eclipse-mosquitto:2.0

COPY ./chirpstack/mqtt.conf /mosquitto/config/mosquitto.conf