import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => cleanup())

class EventSourceMock {
  static CLOSED = 2
  addEventListener() {}
  close() {}
}
Object.defineProperty(globalThis, 'EventSource', { value: EventSourceMock, writable: true })

