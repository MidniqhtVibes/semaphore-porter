import { cpSync, createReadStream, readdirSync } from 'node:fs'
import { extname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vitest/config'
import react from '@vitejs/plugin-react'

const arcadeFlag = process.env.PORTAL_BUILD_IDDQD ?? '0'
if (!['0', '1'].includes(arcadeFlag)) throw new Error('PORTAL_BUILD_IDDQD must be 0 or 1')
const arcadeEnabled = arcadeFlag === '1'
const arcadeDirectory = fileURLToPath(new URL('./arcade/', import.meta.url))

function optionalArcade(): Plugin {
  const files = new Set(readdirSync(arcadeDirectory))
  const mime: Record<string, string> = {
    '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css',
    '.wasm': 'application/wasm', '.zip': 'application/zip', '.txt': 'text/plain; charset=utf-8',
  }
  return {
    name: 'optional-arcade',
    writeBundle(options) {
      if (arcadeEnabled && options.dir) cpSync(arcadeDirectory, resolve(options.dir, 'arcade'), { recursive: true })
    },
    configureServer(server) {
      server.middlewares.use('/arcade', (request, response, next) => {
        const name = new URL(request.url ?? '/', 'http://localhost').pathname.slice(1)
        if (!arcadeEnabled || !files.has(name)) { response.statusCode = 404; response.end(); return }
        response.setHeader('Content-Type', mime[extname(name)] ?? 'application/octet-stream')
        const stream = createReadStream(resolve(arcadeDirectory, name))
        stream.on('error', next)
        stream.pipe(response)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), optionalArcade()],
  define: { __PORTAL_ARCADE__: JSON.stringify(arcadeEnabled) },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
