// SPDX-License-Identifier: GPL-2.0-or-later
// Host adapter for the unmodified GPL-2.0 doom.wasm module. See THIRD_PARTY.txt.
let engine = null
let interval = null
let width = 0
let height = 0
let framePending = false
let ticks = 0
let pausedAt = 0
let pausedDuration = 0
const pressed = new Set()
const releaseAfterTick = new Set()
const saves = new Map()
const decoder = new TextDecoder()

function readMessage(pointer, length) {
  return engine ? decoder.decode(new Uint8Array(engine.memory.buffer, pointer, length)) : ''
}

function drawFrame(pointer) {
  // Limit the message queue to one frame if the UI cannot keep up.
  if (framePending) return
  const source = new Uint8Array(engine.memory.buffer, pointer, width * height * 4)
  const pixels = new Uint8ClampedArray(source.length)
  for (let i = 0; i < pixels.length; i += 4) {
    pixels[i] = source[i + 2]
    pixels[i + 1] = source[i + 1]
    pixels[i + 2] = source[i]
    pixels[i + 3] = 255
  }
  framePending = true
  self.postMessage({ type: 'frame', width, height, pixels: pixels.buffer }, [pixels.buffer])
}

function keyValue(key) {
  if (typeof key === 'number') return key >= 0 && key < 256 ? key : null
  const value = engine?.[`KEY_${key}`]
  return value instanceof WebAssembly.Global ? value.value : null
}

function releaseAll() {
  for (const key of pressed) engine.reportKeyUp(key)
  pressed.clear()
  releaseAfterTick.clear()
}

function reportError(error) {
  clearInterval(interval)
  interval = null
  self.postMessage({ type: 'error', message: error instanceof Error ? error.message : String(error) })
}

function tick() {
  try {
    // The upstream module accepts no CLI arguments. Start a normal new game
    // through its original menus: New Game, Knee-Deep, Hurt Me Plenty, E1M1.
    if ([4, 12, 20, 28].includes(ticks)) engine.reportKeyDown(keyValue('ENTER'))
    if ([6, 14, 22, 30].includes(ticks)) engine.reportKeyUp(keyValue('ENTER'))
    engine.tickGame()
    // A short tap may begin and end between two engine ticks. Keep it down
    // through one tick so the engine's state-based input API sees the press.
    for (const key of releaseAfterTick) {
      engine.reportKeyUp(key)
      pressed.delete(key)
    }
    releaseAfterTick.clear()
    ticks += 1
    if (ticks === 60) self.postMessage({ type: 'ready' })
  } catch (error) { reportError(error) }
}

async function start() {
  try {
    const response = await fetch(new URL('./doom-25ea5988.wasm', import.meta.url))
    if (!response.ok) throw new Error(`Doom download failed (${response.status})`)
    const { instance } = await WebAssembly.instantiate(await response.arrayBuffer(), {
      loading: {
        onGameInit: (w, h) => { width = w; height = h },
        wadSizes: () => {},
        readWads: () => {},
      },
      ui: { drawFrame },
      runtimeControl: { timeInMilliseconds: () => BigInt(Math.trunc(performance.now() - pausedDuration)) },
      console: {
        onInfoMessage: () => {},
        onErrorMessage: (pointer, length) => console.warn('Doom:', readMessage(pointer, length)),
      },
      gameSaving: {
        sizeOfSaveGame: slot => saves.get(slot)?.length ?? 0,
        readSaveGame: (slot, pointer) => {
          const bytes = saves.get(slot)
          if (!bytes) return 0
          new Uint8Array(engine.memory.buffer, pointer, bytes.length).set(bytes)
          return bytes.length
        },
        writeSaveGame: (slot, pointer, length) => {
          saves.set(slot, new Uint8Array(engine.memory.buffer, pointer, length).slice())
          return length
        },
      },
    })
    engine = instance.exports
    engine.initGame()
    interval = setInterval(tick, 1000 / 35)
  } catch (error) { reportError(error) }
}

self.onmessage = ({ data }) => {
  if (data.type === 'start' && !engine) { void start(); return }
  if (data.type === 'frameReady') { framePending = false; return }
  if (!engine) return
  if (data.type === 'key') {
    const key = keyValue(data.key)
    if (key === null || pausedAt || ticks < 60) return
    if (data.down) { releaseAfterTick.delete(key); pressed.add(key); engine.reportKeyDown(key) }
    else { releaseAfterTick.add(key) }
  } else if (data.type === 'pause' && !pausedAt) {
    releaseAll()
    clearInterval(interval)
    interval = null
    pausedAt = performance.now()
  } else if (data.type === 'resume' && pausedAt) {
    pausedDuration += performance.now() - pausedAt
    pausedAt = 0
    interval = setInterval(tick, 1000 / 35)
  }
}
