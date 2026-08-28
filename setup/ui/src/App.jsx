import { useState, useEffect, useRef } from 'react';
import { Container, Card, Nav, Form, Button, Alert } from 'react-bootstrap';
import { Html5Qrcode } from 'html5-qrcode';
import Select from 'react-select';
import { useDevices, useAddDevice, useQueueDownlink } from './api';

export default function App() {
    const [activeTab, setActiveTab] = useState('provision');
    const [lastProvisionedEui, setLastProvisionedEui] = useState('');

    const handleProvisionSuccess = (devEui) => {
        setLastProvisionedEui(devEui);
    };

    return (
        <Container className="py-4" style={{ maxWidth: '480px' }}>
            <Card className="shadow-sm">
                <Card.Header>
                    <Nav variant="tabs" activeKey={activeTab} onSelect={(k) => setActiveTab(k)}>
                        <Nav.Item className="flex-fill text-center">
                            <Nav.Link eventKey="provision">1. Provision</Nav.Link>
                        </Nav.Item>
                        <Nav.Item className="flex-fill text-center">
                            <Nav.Link eventKey="edit">2. Edit</Nav.Link>
                        </Nav.Item>
                        <Nav.Item className="flex-fill text-center">
                            <Nav.Link eventKey="setup">3. Downlink</Nav.Link>
                        </Nav.Item>
                    </Nav>
                </Card.Header>

                <Card.Body>
                    {activeTab === 'provision' && (
                        <ProvisionTab
                            onProvisionSuccess={handleProvisionSuccess}
                            onNavigateToSetup={() => setActiveTab('setup')}
                        />
                    )}

                    {activeTab === 'edit' && <UpdateTab />}

                    {activeTab === 'setup' && (
                        <SetupTab initialDevEui={lastProvisionedEui} />
                    )}
                </Card.Body>
            </Card>
        </Container>
    );
}

function ProvisionTab({ onProvisionSuccess, onNavigateToSetup }) {
    const [devEui, setDevEui] = useState('');
    const [joinEui, setJoinEui] = useState('');
    const [appKey, setAppKey] = useState('');
    const [identifier, setIdentifier] = useState('');
    const [deviceType, setDeviceType] = useState('');
    const [manufacturer, setManufacturer] = useState('');
    const [allowedDeviceTypes, setAllowedDeviceTypes] = useState([]);

    const [status, setStatus] = useState({
        variant: 'info',
        message: 'Scan TR005 QR code or fill details manually.',
        errors: []
    });
    const [isSuccess, setIsSuccess] = useState(false);
    const [isScanning, setIsScanning] = useState(false);

    const qrCodeInstanceRef = useRef(null);
    const addDeviceMutation = useAddDevice();

    useEffect(() => {
        fetch('/api/device-types')
            .then((res) => res.json())
            .then((data) => {
                if (data.device_types) {
                    setAllowedDeviceTypes(data.device_types);
                }
            })
            .catch((err) => console.error('Failed to load device types:', err));
    }, []);

    const startCamera = async () => {
        try {
            if (!qrCodeInstanceRef.current) {
                qrCodeInstanceRef.current = new Html5Qrcode('reader');
            }

            setIsScanning(true);
            await qrCodeInstanceRef.current.start(
                { facingMode: 'environment' },
                { fps: 10, qrbox: { width: 220, height: 220 } },
                (decodedText) => {
                    const text = decodedText.trim();

                    const MANUFACTURER_PREFIXES = {
                        'A84041': 'Dragino',
                        '24E124': 'Milesight',
                        '2CF7F1': 'SenseCAP',
                        'AC1F09': 'RAKWireless',
                        '60C5A8': 'RAKWireless',
                        '00137A': 'Netvox',
                        '70B3D5': 'MokoSmart',
                    };

                    const cleanHex = (str) => (str ? str.replace(/[^A-Fa-f0-9]/g, '').toUpperCase() : '');

                    const detectManufacturer = (eui) => {
                        if (!eui || eui.length < 6) return '';
                        const prefix = eui.substring(0, 6);
                        return MANUFACTURER_PREFIXES[prefix] || '';
                    };

                    let extractedDevEui = '';
                    let extractedJoinEui = '';
                    let extractedAppKey = '';
                    let formatLabel = '';

                    if (text.startsWith('LW:')) {
                        const parts = text.split(':');
                        if (parts.length >= 6) {
                            extractedJoinEui = cleanHex(parts[2]);
                            extractedDevEui = cleanHex(parts[3]);
                            extractedAppKey = cleanHex(parts[5]);
                            formatLabel = 'TR005 Standard';
                        }
                    } else if (text.startsWith('{') && text.endsWith('}')) {
                        try {
                            const json = JSON.parse(text);
                            extractedDevEui = cleanHex(json.devEui || json.dev_eui || json.devEUI || json.DevEUI);
                            extractedJoinEui = cleanHex(json.joinEui || json.join_eui || json.appEui || json.app_eui || json.AppEUI);
                            extractedAppKey = cleanHex(json.appKey || json.app_key || json.AppKey);
                            formatLabel = 'JSON';
                        } catch (e) { }
                    }

                    if (!extractedDevEui) {
                        const devMatch = text.match(/(?:DEV_?EUI|DEVEUI|DEV_?ID)[:=\s]+([0-9A-Fa-f]{16})/i);
                        const joinMatch = text.match(/(?:JOIN_?EUI|APP_?EUI|JOINEUI|APPEUI)[:=\s]+([0-9A-Fa-f]{16})/i);
                        const keyMatch = text.match(/(?:APP_?KEY|NWK_?KEY|APPKEY)[:=\s]+([0-9A-Fa-f]{32})/i);

                        if (devMatch) extractedDevEui = cleanHex(devMatch[1]);
                        if (joinMatch) extractedJoinEui = cleanHex(joinMatch[1]);
                        if (keyMatch) extractedAppKey = cleanHex(keyMatch[1]);

                        if (extractedDevEui) formatLabel = 'Key-Value Text';
                    }

                    if (!extractedDevEui) {
                        const tokens = text.split(/[,;\s\t\n|]+/).map(cleanHex).filter((t) => t.length > 0);
                        const hex16 = tokens.filter((t) => t.length === 16);
                        const hex32 = tokens.filter((t) => t.length === 32);

                        if (hex16.length >= 1 && hex32.length >= 1) {
                            let devIdx = hex16.findIndex((eui) => detectManufacturer(eui) !== '');
                            if (devIdx === -1) devIdx = 0;

                            extractedDevEui = hex16[devIdx];
                            const remaining16 = hex16.filter((_, i) => i !== devIdx);
                            extractedJoinEui = remaining16.length > 0 ? remaining16[0] : '0000000000000000';
                            extractedAppKey = hex32[0];
                            formatLabel = 'Raw Delimited';
                        }
                    }

                    if (extractedDevEui && extractedDevEui.length === 16) {
                        const mfr = detectManufacturer(extractedDevEui);
                        setDevEui(extractedDevEui);
                        if (extractedJoinEui) setJoinEui(extractedJoinEui);
                        if (extractedAppKey) setAppKey(extractedAppKey);
                        if (mfr) setManufacturer(mfr);

                        setIdentifier((prev) => prev || `${mfr ? mfr.toLowerCase() : 'node'}-${extractedDevEui.slice(-6).toLowerCase()}`);

                        setStatus({
                            variant: 'success',
                            message: `Scanned ${mfr ? `${mfr} ` : ''}Device (${formatLabel}) - DevEUI: ${extractedDevEui}`,
                            errors: []
                        });
                    } else {
                        setStatus({
                            variant: 'warning',
                            message: 'Unrecognized QR code. Manual entry required.',
                            errors: []
                        });
                    }

                    stopCamera();
                },
                () => { }
            );
        } catch (err) {
            setIsScanning(false);
            setStatus({ variant: 'danger', message: `Camera access failed: ${err.message || err}`, errors: [] });
        }
    };

    const stopCamera = async () => {
        if (qrCodeInstanceRef.current && qrCodeInstanceRef.current.isScanning) {
            try {
                await qrCodeInstanceRef.current.stop();
                setIsScanning(false);
            } catch (err) {
                console.error('Failed to stop camera scanner:', err);
            }
        }
    };

    useEffect(() => {
        return () => {
            stopCamera();
        };
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();
        stopCamera();
        setStatus({ variant: 'info', message: 'Saving device details...', errors: [] });

        const payload = {
            dev_eui: devEui,
            join_eui: joinEui,
            app_key: appKey,
            identifier: identifier,
            device_type: deviceType,
            manufacturer: manufacturer
        };

        addDeviceMutation.mutate(payload, {
            onSuccess: (data) => {
                const actionVerb = data.action === 'updated' ? 'Updated' : 'Registered';

                setStatus({
                    variant: 'success',
                    message: `Device successfully ${actionVerb.toLowerCase()}! (DevEUI: ${data.dev_eui})`,
                    errors: []
                });
                setIsSuccess(true);
                if (onProvisionSuccess) onProvisionSuccess(data.dev_eui);
            },
            onError: (err) => {
                const errorResponse = err?.response?.data;
                const errorList = errorResponse?.errors || (errorResponse?.detail ? [errorResponse.detail] : [err.message]);

                setStatus({
                    variant: 'danger',
                    message: 'Operation Failed:',
                    errors: errorList
                });
            }
        });
    };

    return (
        <>
            <Card.Title className="text-center mb-3">Provision Device</Card.Title>

            <div
                id="reader"
                className="overflow-hidden rounded mb-3 bg-light text-center"
                style={{ width: '100%', minHeight: isScanning ? '250px' : '0px' }}
            ></div>

            {!isScanning ? (
                <Button variant="outline-primary" className="w-100 mb-3" onClick={startCamera}>
                    📷 Start Camera Scanner
                </Button>
            ) : (
                <Button variant="outline-secondary" className="w-100 mb-3" onClick={stopCamera}>
                    Stop Camera
                </Button>
            )}

            <Alert variant={status.variant} className="text-break mb-3">
                <div>{status.message}</div>
                {status.errors.length > 0 && (
                    <ul className="mb-0 mt-2 ps-3 text-start small">
                        {status.errors.map((err, idx) => (
                            <li key={idx}>{err}</li>
                        ))}
                    </ul>
                )}
            </Alert>

            <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-2">
                    <Form.Label>Device Identifier (Name)</Form.Label>
                    <Form.Control
                        type="text"
                        value={identifier}
                        onChange={(e) => setIdentifier(e.target.value)}
                        placeholder="e.g. temp-sensor-01"
                        required
                    />
                    <Form.Text className="text-muted">
                        Only letters, numbers, hyphens, and underscores allowed.
                    </Form.Text>
                </Form.Group>

                <Form.Group className="mb-2">
                    <Form.Label>Device Type</Form.Label>
                    <Form.Select
                        value={deviceType}
                        onChange={(e) => setDeviceType(e.target.value)}
                        required
                    >
                        <option value="">-- Select Device Type --</option>
                        {allowedDeviceTypes.map((type) => (
                            <option key={type} value={type}>
                                {type}
                            </option>
                        ))}
                    </Form.Select>
                </Form.Group>

                <Form.Group className="mb-2">
                    <Form.Label>DevEUI (Hex)</Form.Label>
                    <Form.Control
                        type="text"
                        value={devEui}
                        onChange={(e) => setDevEui(e.target.value)}
                        placeholder="16 hex characters"
                        maxLength={16}
                        required
                    />
                </Form.Group>

                <Form.Group className="mb-2">
                    <Form.Label>JoinEUI / AppEUI (Hex)</Form.Label>
                    <Form.Control
                        type="text"
                        value={joinEui}
                        onChange={(e) => setJoinEui(e.target.value)}
                        placeholder="16 hex characters"
                        maxLength={16}
                        required
                    />
                </Form.Group>

                <Form.Group className="mb-3">
                    <Form.Label>AppKey (Hex)</Form.Label>
                    <Form.Control
                        type="text"
                        value={appKey}
                        onChange={(e) => setAppKey(e.target.value)}
                        placeholder="32 hex characters"
                        maxLength={32}
                        required
                    />
                </Form.Group>

                <Button
                    variant="primary"
                    type="submit"
                    className="w-100"
                    disabled={addDeviceMutation.isPending}
                >
                    {addDeviceMutation.isPending ? 'Saving Device...' : 'Save / Register Device'}
                </Button>
            </Form>

            {isSuccess && (
                <Button variant="success" className="w-100 mt-3" onClick={onNavigateToSetup}>
                    Configure {devEui} &rarr;
                </Button>
            )}
        </>
    );
}

function UpdateTab() {
    const [selectedOption, setSelectedOption] = useState(null);
    const [identifier, setIdentifier] = useState('');
    const [deviceType, setDeviceType] = useState('');
    const [allowedDeviceTypes, setAllowedDeviceTypes] = useState([]);
    const [status, setStatus] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const { data: devices = [], isLoading, refetch } = useDevices();

    const options = devices.map((dev) => ({
        value: dev.dev_eui,
        label: `${dev.name} (${dev.dev_eui})`,
        device: dev
    }));

    useEffect(() => {
        fetch('/api/device-types')
            .then((res) => res.json())
            .then((data) => {
                if (data.device_types) setAllowedDeviceTypes(data.device_types);
            })
            .catch((err) => console.error('Failed to load device types:', err));
    }, []);

    const handleSelectChange = (option) => {
        setSelectedOption(option);
        setStatus(null);
        if (option && option.device) {
            setIdentifier(option.device.name || '');
            // Checks top-level device_type or nested tags.device_type fallback
            const currentType = option.device.device_type || option.device.tags?.device_type || '';
            setDeviceType(currentType);
        } else {
            setIdentifier('');
            setDeviceType('');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!selectedOption) return;

        setIsSubmitting(true);
        setStatus({ variant: 'info', message: 'Updating device details...', errors: [] });

        try {
            const res = await fetch('/api/update-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dev_eui: selectedOption.value,
                    identifier,
                    device_type: deviceType
                })
            });

            const data = await res.json();

            if (!res.ok) {
                const errorList = data.errors || (data.detail ? [data.detail] : ['Failed to update device.']);
                setStatus({ variant: 'danger', message: 'Update Failed:', errors: errorList });
            } else {
                setStatus({
                    variant: 'success',
                    message: `Device (${data.dev_eui}) updated successfully!`,
                    errors: []
                });
                if (refetch) refetch();
            }
        } catch (err) {
            setStatus({
                variant: 'danger',
                message: 'Update Failed:',
                errors: [err.message || 'Network error']
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Form onSubmit={handleSubmit}>
            <Card.Title className="text-center mb-3">Edit Device Details</Card.Title>

            {status && (
                <Alert variant={status.variant} className="text-break mb-3">
                    <div>{status.message}</div>
                    {status.errors.length > 0 && (
                        <ul className="mb-0 mt-2 ps-3 text-start small">
                            {status.errors.map((err, idx) => (
                                <li key={idx}>{err}</li>
                            ))}
                        </ul>
                    )}
                </Alert>
            )}

            <Form.Group className="mb-3">
                <Form.Label>Select Registered Device</Form.Label>
                <Select
                    options={options}
                    value={selectedOption}
                    onChange={handleSelectChange}
                    isLoading={isLoading}
                    isSearchable
                    placeholder="Search by name or DevEUI..."
                />
            </Form.Group>

            {selectedOption && (
                <>
                    <Form.Group className="mb-2">
                        <Form.Label>Device Identifier (Name)</Form.Label>
                        <Form.Control
                            type="text"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            placeholder="e.g. temp-sensor-01"
                            required
                        />
                        <Form.Text className="text-muted">
                            Only letters, numbers, hyphens, and underscores allowed.
                        </Form.Text>
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>Device Type</Form.Label>
                        <Form.Select
                            value={deviceType}
                            onChange={(e) => setDeviceType(e.target.value)}
                            required
                        >
                            <option value="">-- Select Device Type --</option>
                            {allowedDeviceTypes.map((type) => (
                                <option key={type} value={type}>
                                    {type}
                                </option>
                            ))}
                        </Form.Select>
                    </Form.Group>

                    <Button
                        variant="primary"
                        type="submit"
                        className="w-100"
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? 'Updating Device...' : 'Update Device'}
                    </Button>
                </>
            )}
        </Form>
    );
}

// Base Dragino TDC/System Presets
const BASE_PRESETS = [
    { id: 'tdc_10s', label: 'Set Uplink Interval (10 Sec)', hex: '0100000A' },
    { id: 'tdc_5m', label: 'Set Uplink Interval (5 Min)', hex: '0100012C' },
    { id: 'tdc_10m', label: 'Set Uplink Interval (10 Min)', hex: '01000258' },
    { id: 'tdc_30m', label: 'Set Uplink Interval (30 Min)', hex: '01000708' },
    { id: 'tdc_1h', label: 'Set Uplink Interval (1 Hour)', hex: '01000E10' },
    {
        id: 'custom_tdc',
        label: 'Set Custom Uplink Interval...',
        fields: [
            {
                key: 'seconds',
                label: 'Uplink Interval',
                controlType: 'number',
                defaultValue: 600,
                min: 5,
                unit: 'seconds',
            },
        ],
        buildPayload: (vals) => {
            const sec = Math.max(1, parseInt(vals.seconds || 600, 10));
            return `01${sec.toString(16).padStart(6, '0').toUpperCase()}`;
        },
    },
    { id: 'sys_reset', label: 'System Reset / Rejoin', hex: '04FF' },
];

// Device-Specific Command Maps with Sub-Option Support
const DEVICE_SPECIFIC_PRESETS = {
    tc01: [
        { id: 'tc_clear_flash', label: 'Clear Internal Flash Log', hex: 'A801' },
        {
            id: 'tc_type_select',
            label: 'Set Thermocouple Sensor Type...',
            fields: [
                {
                    key: 'tcType',
                    label: 'Thermocouple Type',
                    controlType: 'select',
                    defaultValue: '01',
                    options: [
                        { label: 'Type K', value: '01' },
                        { label: 'Type J', value: '02' },
                        { label: 'Type E', value: '03' },
                        { label: 'Type T', value: '04' },
                        { label: 'Type R', value: '05' },
                        { label: 'Type S', value: '06' },
                        { label: 'Type B', value: '07' },
                        { label: 'Type N', value: '08' },
                    ],
                },
            ],
            buildPayload: (vals) => `A6${vals.tcType || '01'}`,
        },
        {
            id: 'tc_temp_alarm',
            label: 'Set High Temperature Alarm Threshold...',
            fields: [
                {
                    key: 'tempVal',
                    label: 'Threshold Temperature',
                    controlType: 'number',
                    defaultValue: 100,
                    min: -200,
                    max: 1300,
                    step: 0.1,
                    unit: '°C',
                },
            ],
            buildPayload: (vals) => {
                // TC01 stores high threshold in 0.1°C units (100°C = 1000 = 0x03E8)
                const temp = Math.round(parseFloat(vals.tempVal || 0) * 10);
                const raw16 = temp < 0 ? 0xffff + temp + 1 : temp;
                const hexVal = (raw16 & 0xffff).toString(16).padStart(4, '0').toUpperCase();
                return `0B${hexVal}`;
            },
        },
    ],
    cs01: [
        { id: 'cs_reset_cal', label: 'Reset Current Calibration Baseline', hex: 'A701' },
        {
            id: 'cs_alarm',
            label: 'Set High Current Alarm Threshold...',
            fields: [
                {
                    key: 'currentVal',
                    label: 'Current Limit',
                    controlType: 'number',
                    defaultValue: 10,
                    min: 1,
                    max: 500,
                    unit: 'Amps (A)',
                },
            ],
            buildPayload: (vals) => {
                const amps = parseInt(vals.currentVal || 10, 10);
                return `0B${amps.toString(16).padStart(4, '0').toUpperCase()}`;
            },
        },
    ],
};

function SetupTab({ initialDevEui }) {
    const [selectedOption, setSelectedOption] = useState(null);
    const [fPort, setFPort] = useState(2);
    const [payload, setPayload] = useState('');
    const [selectedPresetId, setSelectedPresetId] = useState('');
    const [presetParams, setPresetParams] = useState({});
    const [feedback, setFeedback] = useState(null);

    const { data: devices = [], isLoading } = useDevices();
    const queueDownlinkMutation = useQueueDownlink();

    const options = devices.map((dev) => ({
        value: dev.dev_eui,
        label: `${dev.name} (${dev.dev_eui})`,
        device: dev,
    }));

    useEffect(() => {
        if (initialDevEui && options.length > 0) {
            const match = options.find((o) => o.value === initialDevEui);
            if (match) setSelectedOption(match);
        }
    }, [initialDevEui, devices]);

    const deviceType = (
        selectedOption?.device?.device_type ||
        selectedOption?.device?.tags?.device_type ||
        ''
    ).toLowerCase();

    const manufacturer = selectedOption?.device?.manufacturer || '';
    const isDragino =
        manufacturer.toLowerCase().includes('dragino') ||
        selectedOption?.label?.toLowerCase().includes('dragino') ||
        Boolean(DEVICE_SPECIFIC_PRESETS[deviceType]);

    const currentPresets = [
        ...BASE_PRESETS,
        ...(DEVICE_SPECIFIC_PRESETS[deviceType] || []),
    ];

    const activePreset = currentPresets.find((p) => p.id === selectedPresetId);

    const handlePresetSelect = (e) => {
        const presetId = e.target.value;
        setSelectedPresetId(presetId);

        const preset = currentPresets.find((p) => p.id === presetId);
        if (!preset) return;

        if (preset.fields) {
            // Initialize default sub-option state
            const defaults = {};
            preset.fields.forEach((f) => {
                defaults[f.key] = f.defaultValue;
            });
            setPresetParams(defaults);
            setPayload(preset.buildPayload(defaults));
        } else if (preset.hex) {
            setPresetParams({});
            setPayload(preset.hex);
        }
    };

    const handleParamChange = (key, value) => {
        const updatedParams = { ...presetParams, [key]: value };
        setPresetParams(updatedParams);
        if (activePreset && activePreset.buildPayload) {
            setPayload(activePreset.buildPayload(updatedParams));
        }
    };

    const sendDownlink = (e) => {
        e.preventDefault();
        setFeedback(null);
        if (!selectedOption || !payload) return;

        queueDownlinkMutation.mutate(
            { dev_eui: selectedOption.value, f_port: parseInt(fPort, 10), hex_payload: payload },
            {
                onSuccess: (data) => {
                    setFeedback({ variant: 'success', message: `Downlink queued successfully! ID: ${data.id || 'OK'}` });
                },
                onError: (err) => {
                    const detail = err?.response?.data?.detail || err.message;
                    setFeedback({ variant: 'danger', message: `Failed to queue downlink: ${detail}` });
                },
            }
        );
    };

    return (
        <Form onSubmit={sendDownlink}>
            <Card.Title className="text-center mb-3">Queue Downlink Config</Card.Title>

            {feedback && (
                <Alert variant={feedback.variant} className="mb-3 text-break">
                    {feedback.message}
                </Alert>
            )}

            <Form.Group className="mb-3">
                <Form.Label>Select Registered Device</Form.Label>
                <Select
                    options={options}
                    value={selectedOption}
                    onChange={(opt) => {
                        setSelectedOption(opt);
                        setSelectedPresetId('');
                        setPayload('');
                        setPresetParams({});
                    }}
                    isLoading={isLoading}
                    isSearchable
                    placeholder="Search by name or DevEUI..."
                />
            </Form.Group>

            {selectedOption && isDragino && (
                <Card className="bg-light mb-3 border-info">
                    <Card.Body className="p-3">
                        <Card.Subtitle className="mb-2 text-info fw-bold">
                            ⚙️ Device Controls ({deviceType.toUpperCase() || 'Dragino'})
                        </Card.Subtitle>

                        <Form.Group className="mb-2">
                            <Form.Label className="small mb-1">Select Preset Command</Form.Label>
                            <Form.Select
                                size="sm"
                                value={selectedPresetId}
                                onChange={handlePresetSelect}
                            >
                                <option value="">-- Choose Preset Command --</option>
                                {currentPresets.map((p) => (
                                    <option key={p.id} value={p.id}>
                                        {p.label} {p.hex ? `(${p.hex})` : ''}
                                    </option>
                                ))}
                            </Form.Select>
                        </Form.Group>

                        {/* Render Dynamic Sub-Option Controls */}
                        {activePreset && activePreset.fields && (
                            <div className="mt-2 pt-2 border-top bg-white p-2 rounded border">
                                <span className="small fw-bold text-secondary d-block mb-2">
                                    Command Options
                                </span>
                                {activePreset.fields.map((field) => (
                                    <Form.Group key={field.key} className="mb-2">
                                        <Form.Label className="small mb-1">{field.label}</Form.Label>

                                        {field.controlType === 'select' && (
                                            <Form.Select
                                                size="sm"
                                                value={presetParams[field.key] ?? field.defaultValue}
                                                onChange={(e) => handleParamChange(field.key, e.target.value)}
                                            >
                                                {field.options.map((opt) => (
                                                    <option key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </option>
                                                ))}
                                            </Form.Select>
                                        )}

                                        {field.controlType === 'number' && (
                                            <div className="d-flex align-items-center gap-2">
                                                <Form.Control
                                                    type="number"
                                                    size="sm"
                                                    value={presetParams[field.key] ?? field.defaultValue}
                                                    min={field.min}
                                                    max={field.max}
                                                    step={field.step || 1}
                                                    onChange={(e) => handleParamChange(field.key, e.target.value)}
                                                />
                                                {field.unit && <span className="small text-muted">{field.unit}</span>}
                                            </div>
                                        )}
                                    </Form.Group>
                                ))}
                            </div>
                        )}
                    </Card.Body>
                </Card>
            )}

            <div className="row g-2 mb-3">
                <div className="col-4">
                    <Form.Group>
                        <Form.Label>FPort</Form.Label>
                        <Form.Control
                            type="number"
                            value={fPort}
                            onChange={(e) => setFPort(e.target.value)}
                            min="1"
                            max="223"
                            required
                        />
                    </Form.Group>
                </div>
                <div className="col-8">
                    <Form.Group>
                        <Form.Label>Hex Payload</Form.Label>
                        <Form.Control
                            type="text"
                            value={payload}
                            onChange={(e) => {
                                setPayload(e.target.value);
                                setSelectedPresetId('');
                            }}
                            placeholder="e.g. A601"
                            required
                        />
                    </Form.Group>
                </div>
            </div>

            <Button
                variant="primary"
                type="submit"
                className="w-100"
                disabled={!selectedOption || queueDownlinkMutation.isPending}
            >
                {queueDownlinkMutation.isPending ? 'Queuing Downlink...' : 'Send Configuration Payload'}
            </Button>
        </Form>
    );
}