import os
import logging
import datetime
import re

import grpc
from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server
from chirpstack_api import api, common
from bottle import Bottle, request, response, static_file


import subprocess

HEX16_RE = re.compile(r"^[0-9a-fA-F]{16}$")
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

ALLOWED_DEVICE_TYPES = {
    "lht65n_vib",
    "rs485_npk",
    "cs01",
    "llms01",
    "lse01",
    "sw3l",
    "s31b",
    "tc01",
}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, force=True)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
CHIRPSTACK_SERVER = "lora-chirpstack:8080"
API_TOKEN = "YOUR_CHIRPSTACK_API_KEY"
DIST_DIR = os.path.abspath("/app/frontend/dist")

CERT_FILE = os.path.abspath("/app/data/cert.pem")
KEY_FILE = os.path.abspath("/app/data/key.pem")

channel = grpc.insecure_channel(CHIRPSTACK_SERVER)

login_resp = api.InternalServiceStub(channel).Login(
    api.LoginRequest(email="admin", password="admin")
)
metadata = [("authorization", f"Bearer {login_resp.jwt}")]

# Internal cache for auto-resolved IDs
config = {"tenant_id": None, "application_id": None, "device_profile_id": None}


def init_chirpstack():
    """Runs at startup to auto-detect active Tenant, Application, and Profile IDs."""
    try:
        # 1. Resolve or Create Tenant
        tenant_stub = api.TenantServiceStub(channel)
        tenants = tenant_stub.List(api.ListTenantsRequest(limit=1), metadata=metadata)

        if tenants.result:
            config["tenant_id"] = tenants.result[0].id
        else:
            logger.info("No tenants found. Creating 'Default-Tenant'...")
            create_tenant_req = api.CreateTenantRequest(
                tenant=api.Tenant(
                    name="Shoestring-Tenant",
                    can_have_gateways=True,
                )
            )
            tenant_resp = tenant_stub.Create(create_tenant_req, metadata=metadata)
            config["tenant_id"] = tenant_resp.id

        # 2. Resolve or Create Application
        app_stub = api.ApplicationServiceStub(channel)
        apps = app_stub.List(
            api.ListApplicationsRequest(tenant_id=config["tenant_id"], limit=1),
            metadata=metadata,
        )
        if apps.result:
            config["application_id"] = apps.result[0].id
        else:
            logger.info("No applications found. Creating 'Shoestring-Application'...")
            create_app_req = api.CreateApplicationRequest(
                application=api.Application(
                    name="Shoestring-Application",
                    description="Auto-created by provisioner app",
                    tenant_id=config["tenant_id"],
                )
            )
            app_resp = app_stub.Create(create_app_req, metadata=metadata)
            config["application_id"] = app_resp.id

        # 3. Resolve or Create Device Profile (EU868 Example)
        dp_stub = api.DeviceProfileServiceStub(channel)
        profiles = dp_stub.List(
            api.ListDeviceProfilesRequest(tenant_id=config["tenant_id"], limit=1),
            metadata=metadata,
        )
        if profiles.result:
            config["device_profile_id"] = profiles.result[0].id
        else:
            logger.info("No device profiles found. Creating 'Default-OTAA-Profile'...")
            create_dp_req = api.CreateDeviceProfileRequest(
                device_profile=api.DeviceProfile(
                    name="Default-OTAA-Profile",
                    tenant_id=config["tenant_id"],
                    region=common.Region.EU868,  # Match your region
                    mac_version=common.MacVersion.LORAWAN_1_0_3,
                    reg_params_revision=common.RegParamsRevision.A,
                    supports_otaa=True,
                )
            )
            dp_resp = dp_stub.Create(create_dp_req, metadata=metadata)
            config["device_profile_id"] = dp_resp.id

        logger.info(
            f"[Init Success] App ID: {config['application_id']} | Profile ID: {config['device_profile_id']}"
        )
    except Exception as e:
        logger.error(f"[Init Warning] Could not auto-resolve ChirpStack IDs: {e}")


# ==============================================================================
# WEB UI ROUTE
# ==============================================================================
app = Bottle()

@app.route("/")
def serve_index():
    return static_file("index.html", root=DIST_DIR)


@app.route("/<filename:path>")
def serve_static(filename):
    file_path = os.path.join(DIST_DIR, filename)
    if os.path.exists(file_path):
        return static_file(filename, root=DIST_DIR)
    return static_file("index.html", root=DIST_DIR)


# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.route("/api/devices", method="GET")
def get_devices():
    """Lists registered devices with tags for the edit and setup dropdowns."""
    if not config["application_id"]:
        return {"devices": []}

    dev_client = api.DeviceServiceStub(channel)
    try:
        req = api.ListDevicesRequest(application_id=config["application_id"], limit=100)
        resp = dev_client.List(req, metadata=metadata)

        devices = []
        for item in resp.result:
            dev_eui = item.dev_eui
            name = item.name
            tags_dict = {}

            # Fetch detailed device record to populate tags
            try:
                get_req = api.GetDeviceRequest(dev_eui=dev_eui)
                get_resp = dev_client.Get(get_req, metadata=metadata)

                if get_resp and get_resp.device and get_resp.device.tags:
                    tags_dict = dict(get_resp.device.tags)
            except grpc.RpcError:
                # Allow partial list loading if an individual device call fails
                pass

            devices.append(
                {
                    "dev_eui": dev_eui,
                    "name": name,
                    **tags_dict,
                }
            )

        return {"devices": devices}
    except grpc.RpcError as e:
        response.status = 500
        return {"detail": f"Failed to fetch devices: {e.details()}"}


@app.route("/api/add-device", method="POST")
def add_device():
    data = request.json or {}

    dev_eui = data.get("dev_eui", "").strip()
    join_eui = data.get("join_eui", "").strip()
    app_key = data.get("app_key", "").strip()
    identifier = data.get("identifier", "").strip()
    device_type = data.get("device_type", "").strip()
    manufacturer = data.get("manufacturer", "").strip()

    # --- INPUT VALIDATION ---
    errors = []

    if not HEX16_RE.match(dev_eui):
        errors.append("dev_eui must be exactly 16 hex characters (8 bytes).")

    if not HEX16_RE.match(join_eui):
        errors.append("join_eui must be exactly 16 hex characters (8 bytes).")

    if not HEX32_RE.match(app_key):
        errors.append("app_key must be exactly 32 hex characters (16 bytes).")

    if not identifier or not IDENTIFIER_RE.match(identifier):
        errors.append(
            "identifier is required and must contain only letters, numbers, hyphens, and underscores."
        )

    if not device_type or device_type not in ALLOWED_DEVICE_TYPES:
        errors.append(
            f"device_type is required and must be one of: {', '.join(sorted(ALLOWED_DEVICE_TYPES))}."
        )

    if errors:
        response.status = 400
        return {"status": "error", "errors": errors}

    # --- CHIRPSTACK REGISTRATION / UPDATE ---

    dev_client = api.DeviceServiceStub(channel)

    try:
        # Build Device object
        device = api.Device()
        device.dev_eui = dev_eui
        device.name = identifier
        device.application_id = config["application_id"]
        device.device_profile_id = config["device_profile_id"]
        device.join_eui = join_eui

        if device_type:
            device.tags["device_type"] = device_type

        if manufacturer:
            device.tags["manufacturer"] = manufacturer

        device.tags["register_date"] = (
            datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()
        )

        # 1. Check if device exists
        device_exists = False
        try:
            dev_client.Get(api.GetDeviceRequest(dev_eui=dev_eui), metadata=metadata)
            device_exists = True
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                raise e

        # 2. Register or Update Device
        if device_exists:
            dev_client.Update(api.UpdateDeviceRequest(device=device), metadata=metadata)
            action = "updated"
        else:
            dev_client.Create(api.CreateDeviceRequest(device=device), metadata=metadata)
            action = "created"

        # Build DeviceKeys object
        device_keys = api.DeviceKeys()
        device_keys.dev_eui = dev_eui
        device_keys.nwk_key = app_key
        device_keys.app_key = app_key

        # 3. Check if keys exist
        keys_exist = False
        try:
            dev_client.GetKeys(
                api.GetDeviceKeysRequest(dev_eui=dev_eui), metadata=metadata
            )
            keys_exist = True
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                raise e

        # 4. Register or Update OTAA Keys
        if keys_exist:
            dev_client.UpdateKeys(
                api.UpdateDeviceKeysRequest(device_keys=device_keys), metadata=metadata
            )
        else:
            dev_client.CreateKeys(
                api.CreateDeviceKeysRequest(device_keys=device_keys), metadata=metadata
            )

        return {
            "status": "success",
            "action": action,
            "dev_eui": dev_eui,
            "device_type": device_type,
        }

    except grpc.RpcError as e:
        response.status = 500
        return {"detail": f"ChirpStack gRPC error: {e.details()}"}


@app.route("/api/update-device", method="POST")
def update_device():
    data = request.json or {}

    dev_eui = data.get("dev_eui", "").strip()
    identifier = data.get("identifier", "").strip()
    device_type = data.get("device_type", "").strip()

    # --- INPUT VALIDATION ---
    errors = []

    if not HEX16_RE.match(dev_eui):
        errors.append("dev_eui must be exactly 16 hex characters (8 bytes).")

    if not identifier or not IDENTIFIER_RE.match(identifier):
        errors.append(
            "identifier is required and must contain only letters, numbers, hyphens, and underscores."
        )

    if not device_type or device_type not in ALLOWED_DEVICE_TYPES:
        errors.append(
            f"device_type is required and must be one of: {', '.join(sorted(ALLOWED_DEVICE_TYPES))}."
        )

    if errors:
        response.status = 400
        return {"status": "error", "errors": errors}

    # --- CHIRPSTACK UPDATE ---
    dev_client = api.DeviceServiceStub(channel)

    try:
        # 1. Fetch current device metadata to preserve other fields
        get_resp = dev_client.Get(
            api.GetDeviceRequest(dev_eui=dev_eui), metadata=metadata
        )
        device = get_resp.device

        # 2. Update identifier (name) and device_type tag
        device.name = identifier
        device.tags["device_type"] = device_type

        # 3. Push update back to ChirpStack
        dev_client.Update(api.UpdateDeviceRequest(device=device), metadata=metadata)

        return {
            "status": "success",
            "dev_eui": dev_eui,
            "identifier": identifier,
            "device_type": device_type,
        }

    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            response.status = 404
            return {"status": "error", "errors": [f"Device '{dev_eui}' not found."]}

        response.status = 500
        return {"detail": f"ChirpStack gRPC error: {e.details()}"}


@app.route("/api/device-types", method="GET")
def get_device_types():
    return {"status": "success", "device_types": sorted(list(ALLOWED_DEVICE_TYPES))}


@app.route("/api/queue-downlink", method="POST")
def queue_downlink():
    data = request.json or {}
    dev_eui = data.get("dev_eui")
    f_port = int(data.get("f_port", 1))
    hex_payload = data.get("hex_payload", "")

    if not dev_eui or not hex_payload:
        response.status = 400
        return {"detail": "Missing dev_eui or hex_payload"}

    dev_client = api.DeviceServiceStub(channel)

    try:
        req = api.EnqueueDeviceQueueItemRequest()
        req.queue_item.dev_eui = dev_eui
        req.queue_item.f_port = f_port
        req.queue_item.confirmed = True
        req.queue_item.data = bytes.fromhex(hex_payload)

        resp = dev_client.Enqueue(req, metadata=metadata)
        return {"status": "success", "id": resp.id}

    except grpc.RpcError as e:
        response.status = 500
        return {"detail": f"Downlink Queue error: {e.details()}"}
    except ValueError:
        response.status = 400
        return {"detail": "Invalid hex string in payload"}


# ==============================================================================
# SERVER EXECUTION
# ==============================================================================


def ensure_certificates(cert_path, key_path):
    """Generates a self-signed TLS certificate and private key if they do not exist."""
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        logger.info(
            "SSL certificates missing. Auto-generating self-signed certificate..."
        )
        try:
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-out",
                    cert_path,
                    "-keyout",
                    key_path,
                    "-days",
                    "3650",  # 10 years validity
                    "-subj",
                    "/CN=device-portal",
                ],
                check=True,
                capture_output=True,
            )
            logger.info(f"Successfully created '{cert_path}' and '{key_path}'.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Failed to generate SSL certificates via openssl: {e}")
            raise


if __name__ == "__main__":
    init_chirpstack()

    # Auto-create cert.pem and key.pem if missing
    ensure_certificates(CERT_FILE, KEY_FILE)

    # Instantiate Cheroot multi-threaded WSGI server
    server = Server(("0.0.0.0", 5000), app)

    # Bind the SSL certificate and private key
    server.ssl_adapter = BuiltinSSLAdapter(certificate=CERT_FILE, private_key=KEY_FILE)

    logger.info("Starting HTTPS portal on https://0.0.0.0:5000")

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Stopping portal server...")
        server.stop()
