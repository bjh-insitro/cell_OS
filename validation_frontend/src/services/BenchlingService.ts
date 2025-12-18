export interface BenchlingEntity {
    id: string;
    name: string;
    registryId: string;
    schema: string;
    webURL: string;
    fields: Record<string, string>;
}

// Mock data store (fallback)
const MOCK_ENTITIES: Record<string, BenchlingEntity> = {
    // ... (keep existing mock data) ...
    "ben_a549_vendor": {
        id: "ben_a549_vendor",
        name: "A549 (ATCC CCL-185)",
        registryId: "CL001",
        schema: "Cell Line",
        webURL: "https://benchling.com/insitro/registry/entities/ben_a549_vendor",
        fields: {
            "Vendor": "ATCC",
            "Catalog #": "CCL-185",
            "Passage": "4",
            "Date Received": "2023-10-15"
        }
    },
    "ben_a549_mcb": {
        id: "ben_a549_mcb",
        name: "A549 MCB Lot 001",
        registryId: "CL001-MCB001",
        schema: "Cell Line Batch",
        webURL: "https://benchling.com/insitro/registry/entities/ben_a549_mcb",
        fields: {
            "Parent": "CL001",
            "Vial Count": "20",
            "Viability": "98%",
            "Mycoplasma": "Negative"
        }
    },
    "ben_a549_wcb": {
        id: "ben_a549_wcb",
        name: "A549 WCB Lot 001",
        registryId: "CL001-WCB001",
        schema: "Cell Line Batch",
        webURL: "https://benchling.com/insitro/registry/entities/ben_a549_wcb",
        fields: {
            "Parent": "CL001-MCB001",
            "Vial Count": "100",
            "Viability": "97%",
            "Passage": "8"
        }
    },
    "ben_cas9_mcb": {
        id: "ben_cas9_mcb",
        name: "A549-Cas9 MCB Lot 001",
        registryId: "CL002-MCB001",
        schema: "Cell Line Batch",
        webURL: "https://benchling.com/insitro/registry/entities/ben_cas9_mcb",
        fields: {
            "Parent": "CL001-WCB001",
            "Modification": "Lenti-Cas9-Blast",
            "Selection": "Blasticidin",
            "Cas9 Activity": "High"
        }
    },
    "ben_cas9_wcb": {
        id: "ben_cas9_wcb",
        name: "A549-Cas9 WCB Lot 001",
        registryId: "CL002-WCB001",
        schema: "Cell Line Batch",
        webURL: "https://benchling.com/insitro/registry/entities/ben_cas9_wcb",
        fields: {
            "Parent": "CL002-MCB001",
            "Vial Count": "120",
            "Viability": "96%"
        }
    }
};

export const BenchlingService = {
    getEntity: async (entityId: string): Promise<BenchlingEntity | null> => {
        const clientId = import.meta.env.VITE_BENCHLING_CLIENT_ID;
        const clientSecret = import.meta.env.VITE_BENCHLING_CLIENT_SECRET;

        // If no credentials, use mock data
        if (!clientId || !clientSecret) {
            console.warn("No Benchling credentials found, using mock data.");
            await new Promise(resolve => setTimeout(resolve, 500));
            return MOCK_ENTITIES[entityId] || null;
        }

        try {
            // 1. Get Access Token
            // We use the proxy for this too
            const tokenResponse = await fetch('/api/benchling/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    grant_type: 'client_credentials',
                    client_id: clientId.trim(),
                    client_secret: clientSecret.trim(),
                })
            });

            if (!tokenResponse.ok) {
                console.error("Failed to authenticate with Benchling:", tokenResponse.statusText);
                return MOCK_ENTITIES[entityId] || null;
            }

            const tokenData = await tokenResponse.json();
            const accessToken = tokenData.access_token;

            // 2. Fetch Entity
            const response = await fetch(`/api/benchling/custom-entities/${entityId}`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Accept': 'application/json',
                }
            });

            if (!response.ok) {
                // If direct fetch by ID fails, try to search by registry ID
                console.warn(`Direct fetch for entity ID '${entityId}' failed (${response.status}). Attempting registry ID lookup.`);
                const entityByRegistry = await BenchlingService.searchEntity(entityId);
                if (entityByRegistry) {
                    return entityByRegistry;
                }
                console.error("Benchling API Error:", response.statusText);
                return MOCK_ENTITIES[entityId] || null;
            }

            const data = await response.json();

            return {
                id: data.id,
                name: data.name,
                registryId: data.registryId || data.id,
                schema: data.schema?.name || "Unknown",
                webURL: data.webURL,
                fields: {}
            };

        } catch (error) {
            console.error("Failed to fetch from Benchling:", error);
            // If an error occurs during the direct fetch, also try registry lookup as a fallback
            console.warn(`Error during direct fetch for entity ID '${entityId}'. Attempting registry ID lookup.`);
            const entityByRegistry = await BenchlingService.searchEntity(entityId);
            if (entityByRegistry) {
                return entityByRegistry;
            }
            return MOCK_ENTITIES[entityId] || null;
        }
    },

    getContainerCount: async (entityId: string): Promise<number | null> => {
        const clientId = import.meta.env.VITE_BENCHLING_CLIENT_ID;
        const clientSecret = import.meta.env.VITE_BENCHLING_CLIENT_SECRET;

        if (!clientId || !clientSecret) return null;

        try {
            // 1. Get Token (reuse logic or refactor later - duplicating for speed now)
            const tokenResponse = await fetch('/api/benchling/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    grant_type: 'client_credentials',
                    client_id: clientId.trim(),
                    client_secret: clientSecret.trim(),
                })
            });
            const tokenData = await tokenResponse.json();
            const accessToken = tokenData.access_token;

            // 2. Search for containers with this entity
            // We need the API ID (ent_...) for this filter. 
            // If entityId passed here is a Registry ID (CLI...), this might fail.
            // We'll assume the caller passes the API ID, which we get from getEntity.

            const params = new URLSearchParams({
                content_entity_id: entityId,
                archived: 'false',
                pageSize: '1' // We only care about the total count
            });

            const response = await fetch(`/api/benchling/containers?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Accept': 'application/json',
                }
            });

            if (!response.ok) return null;

            // Benchling paginated responses usually don't give a total count header easily 
            // unless we iterate, but let's check if there's a workaround or if we just fetch a page.
            // Actually, for a simple "how many tubes", we might need to fetch all or check if 'total' is in response.
            // V2 API often doesn't return total count for performance. 
            // Strategy: Fetch with a larger limit (e.g. 100) and count. If 100+, say "100+".

            // Re-fetch with larger limit
            const countParams = new URLSearchParams({
                content_entity_id: entityId,
                archived: 'false',
                pageSize: '100'
            });
            const countResponse = await fetch(`/api/benchling/containers?${countParams.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Accept': 'application/json',
                }
            });
            const data = await countResponse.json();
            return data.containers ? data.containers.length : 0;

        } catch (error) {
            console.error("Failed to fetch container count:", error);
            return null;
        }
    },

    // Helper to resolve Registry ID (CLI...) to API ID (ent...)
    searchEntity: async (registryId: string): Promise<BenchlingEntity | null> => {
        const clientId = import.meta.env.VITE_BENCHLING_CLIENT_ID;
        const clientSecret = import.meta.env.VITE_BENCHLING_CLIENT_SECRET;



        if (!clientId || !clientSecret) {
            throw new Error("Missing Benchling Credentials");
        }

        try {
            const tokenResponse = await fetch('/api/benchling/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    grant_type: 'client_credentials',
                    client_id: clientId.trim(),
                    client_secret: clientSecret.trim(),
                })
            });

            if (!tokenResponse.ok) {
                const err = await tokenResponse.text();
                throw new Error(`Auth Failed: ${tokenResponse.status} ${err}`);
            }

            const tokenData = await tokenResponse.json();
            const accessToken = tokenData.access_token;

            const response = await fetch(`/api/benchling/custom-entities?registry_id=${registryId}`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Accept': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`Search Failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();

            if (data.customEntities && data.customEntities.length > 0) {
                const entity = data.customEntities[0];
                return {
                    id: entity.id,
                    name: entity.name,
                    registryId: entity.registryId,
                    schema: entity.schema?.name || "Unknown",
                    webURL: entity.webURL,
                    fields: {}
                };
            }
            return null;
        } catch (e: any) {
            console.error("Benchling Service Error:", e);
            throw e;
        }
    }
};
