from chirpstack/chirpstack-sqlite:4

COPY ./chirpstack/* /etc/chirpstack/
# COPY --from=solution_config ./* /etc/chirpstack/