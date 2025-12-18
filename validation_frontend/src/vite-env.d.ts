/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_BENCHLING_TENANT: string
    readonly VITE_BENCHLING_CLIENT_ID: string
    readonly VITE_BENCHLING_CLIENT_SECRET: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
