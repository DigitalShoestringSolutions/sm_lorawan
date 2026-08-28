from chirpstack/chirpstack-sqlite:4

COPY ./chirpstack/chirpstack.toml /etc/chirpstack/00-core.toml
COPY --from=solution_config ./* /etc/chirpstack/