import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    const tenant = env.VITE_BENCHLING_TENANT || 'insitro'; // Default to insitro or user provided

    return {
        plugins: [react()],
        server: {
            port: 5173,
            proxy: {
                '/api/benchling': {
                    target: `https://${tenant}.benchling.com/api/v2`,
                    changeOrigin: true,
                    rewrite: (path) => path.replace(/^\/api\/benchling/, ''),
                }
            }
        },
    }
})
