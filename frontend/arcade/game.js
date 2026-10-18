// SPDX-License-Identifier: GPL-2.0-or-later
const canvas = document.querySelector('#screen')
const context = canvas.getContext('2d', { alpha: false })
const overlay = document.querySelector('#overlay')
const heading = document.querySelector('#overlay-title')
const status = document.querySelector('#status')
const startButton = document.querySelector('#start')
const pauseButton = document.querySelector('#pause')
const restartButton = document.querySelector('#restart')
const fullscreenButton = document.querySelector('#fullscreen')
const held = new Map()
let worker = null
let state = 'idle'
let watchdog = null

const keyBindings = {
  KeyW: 'UPARROW', ArrowUp: 'UPARROW', KeyS: 'DOWNARROW', ArrowDown: 'DOWNARROW',
  KeyA: 'STRAFE_L', KeyD: 'STRAFE_R', ArrowLeft: 'LEFTARROW', ArrowRight: 'RIGHTARROW',
  Space: 'FIRE', ControlLeft: 'FIRE', ControlRight: 'FIRE', KeyE: 'USE',
  ShiftLeft: 'SHIFT', ShiftRight: 'SHIFT', Tab: 'TAB', Escape: 'ESCAPE',
  Enter: 'ENTER', Backspace: 'BACKSPACE',
}

function release(source) {
  const key = held.get(source)
  if (key === undefined) return
  held.delete(source)
  if (![...held.values()].includes(key)) worker?.postMessage({ type: 'key', key, down: false })
}

function press(source, key) {
  if (state !== 'running' || held.has(source)) return
  if (![...held.values()].includes(key)) worker?.postMessage({ type: 'key', key, down: true })
  held.set(source, key)
}

function releaseAll() {
  for (const source of [...held.keys()]) release(source)
  document.querySelectorAll('[data-key].active').forEach(button => button.classList.remove('active'))
}

function stop() {
  clearTimeout(watchdog)
  releaseAll()
  worker?.terminate()
  worker = null
}

function fail(message) {
  stop()
  state = 'error'
  overlay.hidden = false
  heading.textContent = 'Der Hangar ist gerade zu.'
  status.textContent = message
  startButton.hidden = false
  startButton.disabled = false
  startButton.textContent = 'Erneut versuchen'
  pauseButton.disabled = true
  restartButton.disabled = true
}

function pause() {
  if (state !== 'running') return
  releaseAll()
  state = 'paused'
  worker.postMessage({ type: 'pause' })
  overlay.hidden = false
  heading.textContent = 'Kurze Verschnaufpause.'
  status.textContent = 'Dein Spiel wartet hier auf dich.'
  startButton.hidden = false
  startButton.disabled = false
  startButton.textContent = 'Weiterspielen'
  pauseButton.textContent = 'Weiter'
  if (!document.hidden && document.hasFocus()) startButton.focus()
}

function resume() {
  if (state !== 'paused') return
  state = 'running'
  overlay.hidden = true
  pauseButton.textContent = 'Pause'
  worker.postMessage({ type: 'resume' })
  canvas.focus({ preventScroll: true })
}

function start() {
  if (state === 'loading') return
  stop()
  if (!context || typeof WebAssembly === 'undefined' || typeof Worker === 'undefined') {
    fail('Dein Browser unterstützt die benötigte Canvas-, WebAssembly- oder Worker-Funktion nicht.')
    return
  }
  state = 'loading'
  overlay.hidden = false
  heading.textContent = 'Hangar wird geöffnet.'
  status.textContent = 'Die Shareware wird lokal geladen. Einen Moment …'
  startButton.disabled = true
  startButton.hidden = false
  startButton.textContent = 'Wird geladen …'
  pauseButton.disabled = true
  restartButton.disabled = true
  try {
    worker = new Worker(new URL('./engine-worker.js', import.meta.url), { type: 'module' })
    watchdog = setTimeout(() => fail('Das Laden dauert zu lange. Bitte versuche es noch einmal.'), 30000)
    worker.onmessage = ({ data }) => {
      if (data.type === 'frame') {
        if (canvas.width !== data.width || canvas.height !== data.height) {
          canvas.width = data.width
          canvas.height = data.height
        }
        context.putImageData(new ImageData(new Uint8ClampedArray(data.pixels), data.width, data.height), 0, 0)
        worker?.postMessage({ type: 'frameReady' })
      } else if (data.type === 'ready') {
        clearTimeout(watchdog)
        state = 'running'
        overlay.hidden = true
        pauseButton.disabled = false
        restartButton.disabled = false
        pauseButton.textContent = 'Pause'
        canvas.focus({ preventScroll: true })
        if (document.hidden || !document.hasFocus()) pause()
      } else if (data.type === 'error') {
        console.error('Doom:', data.message)
        fail('Doom konnte nicht gestartet werden. Bitte lade das Spiel erneut.')
      }
    }
    worker.onerror = event => {
      console.error('Doom worker:', event.message)
      fail('Der Browser konnte das Spiel nicht ausführen. Bitte versuche es erneut.')
    }
    worker.postMessage({ type: 'start' })
  } catch {
    fail('Das Spiel konnte nicht geladen werden. Bitte versuche es erneut.')
  }
}

startButton.addEventListener('click', () => state === 'paused' ? resume() : start())
pauseButton.addEventListener('click', () => state === 'paused' ? resume() : pause())
restartButton.addEventListener('click', start)
canvas.addEventListener('blur', pause)
window.addEventListener('blur', pause)
document.addEventListener('visibilitychange', () => { if (document.hidden) pause() })
window.addEventListener('pagehide', stop)

document.addEventListener('keydown', event => {
  if (document.activeElement !== canvas || state !== 'running' || event.metaKey || event.altKey || event.isComposing) return
  if (event.ctrlKey && !event.code.startsWith('Control')) return
  if (event.code === 'KeyP') { event.preventDefault(); if (!event.repeat) pause(); return }
  const key = keyBindings[event.code] ?? (/^(?:Digit|Numpad)[1-7]$/.test(event.code) ? event.code.slice(-1).charCodeAt(0) : null)
  if (key === null) return
  event.preventDefault()
  press(`keyboard:${event.code}`, key)
})
document.addEventListener('keyup', event => {
  const source = `keyboard:${event.code}`
  if (held.has(source)) { event.preventDefault(); release(source) }
})

for (const button of document.querySelectorAll('[data-key]')) {
  button.addEventListener('pointerdown', event => {
    if (state !== 'running') return
    event.preventDefault()
    canvas.focus({ preventScroll: true })
    button.setPointerCapture(event.pointerId)
    button.classList.add('active')
    press(`pointer:${event.pointerId}`, keyBindings[button.dataset.key])
  })
  const releasePointer = event => {
    release(`pointer:${event.pointerId}`)
    button.classList.remove('active')
  }
  button.addEventListener('pointerup', releasePointer)
  button.addEventListener('pointercancel', releasePointer)
  button.addEventListener('lostpointercapture', releasePointer)
  button.addEventListener('contextmenu', event => event.preventDefault())
}

if (!document.fullscreenEnabled) fullscreenButton.hidden = true
fullscreenButton.addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.querySelector('#arcade').requestFullscreen()
  } catch {
    fullscreenButton.title = 'Vollbild ist in diesem Browser nicht verfügbar.'
  }
})
document.addEventListener('fullscreenchange', () => {
  fullscreenButton.textContent = document.fullscreenElement ? 'Vollbild verlassen' : 'Vollbild'
})
