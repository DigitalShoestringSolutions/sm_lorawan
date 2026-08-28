import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const HOST = typeof window !== 'undefined' ? document.location.host : 'localhost:5000';
const BASE_URL = `https://${HOST}`;

export const APIBackend = {
    api_get: async (url) => {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || err.error || `HTTP error ${res.status}`);
        }
        return res.json();
    },
    api_post: async (url, body) => {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || err.error || `HTTP error ${res.status}`);
        }
        return res.json();
    },
    api_put: async (url, body) => {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || err.error || `HTTP error ${res.status}`);
        }
        return res.json();
    },
    api_delete: async (url) => {
        const res = await fetch(url, {
            method: 'DELETE',
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || err.error || `HTTP error ${res.status}`);
        }
        return res.json();
    }
};

// ==============================================================================
// DEVICE & PROVISIONING HOOKS
// ==============================================================================

export function useDevices() {
    return useQuery({
        queryKey: ['devices'],
        queryFn: async () => APIBackend.api_get(`${BASE_URL}/api/devices`),
        select: (data) => data.devices || [],
    });
}

export function useAddDevice() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (deviceData) =>
            APIBackend.api_post(`${BASE_URL}/api/add-device`, deviceData),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['devices'] });
        },
    });
}

export function useQueueDownlink() {
    return useMutation({
        mutationFn: async ({ dev_eui, f_port = 1, hex_payload }) =>
            APIBackend.api_post(`${BASE_URL}/api/queue-downlink`, { dev_eui, f_port, hex_payload }),
    });
}