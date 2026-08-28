# Stage 1: Build React static assets
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY ./setup/ui/package*.json ./
RUN npm install
COPY ./setup/ui/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.13

COPY ./setup/requirements.txt /
RUN pip3 install --no-cache-dir -r /requirements.txt
WORKDIR /app
COPY --from=solution_config module_config/ /app/module_config
ADD ./setup/ /app

# Copy compiled React dist folder from Stage 1
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

CMD [ "python3", "/app/main.py"]