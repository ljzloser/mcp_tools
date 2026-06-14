import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
    plugins: [vue()],
    base: '/web/',
    build: {
        outDir: path.resolve(__dirname, '../assets/web'),
        emptyOutDir: true,
    },
    server: {
        proxy: {
            '/health': 'http://127.0.0.1:9020',
            '/server': 'http://127.0.0.1:9020',
            '/plugins': 'http://127.0.0.1:9020',
            '/logs': 'http://127.0.0.1:9020',
        },
    },
})
