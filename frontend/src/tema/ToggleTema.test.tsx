import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ToggleTema } from './ToggleTema'

const sistemaOscuro = (oscuro: boolean) =>
  vi.stubGlobal(
    'matchMedia',
    vi.fn((consulta: string) => ({
      matches: oscuro && consulta.includes('dark'),
      media: consulta,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )

const boton = () => screen.getByRole('button', { name: 'Tema oscuro' })
const tema = () => document.documentElement.dataset.theme

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('selector de tema claro y oscuro', () => {
  it('parte del tema claro del sistema', () => {
    sistemaOscuro(false)

    render(<ToggleTema />)

    expect(tema()).toBe('light')
    expect(boton().getAttribute('aria-pressed')).toBe('false')
  })

  it('parte del tema oscuro del sistema', () => {
    sistemaOscuro(true)

    render(<ToggleTema />)

    expect(tema()).toBe('dark')
    expect(boton().getAttribute('aria-pressed')).toBe('true')
  })

  it('alterna entre claro y oscuro y guarda la elección', () => {
    sistemaOscuro(false)
    render(<ToggleTema />)

    fireEvent.click(boton())
    expect(tema()).toBe('dark')
    expect(boton().getAttribute('aria-pressed')).toBe('true')
    expect(localStorage.getItem('tema')).toBe('dark')

    fireEvent.click(boton())
    expect(tema()).toBe('light')
    expect(boton().getAttribute('aria-pressed')).toBe('false')
    expect(localStorage.getItem('tema')).toBe('light')
  })

  it('la elección guardada gana sobre el tema del sistema', () => {
    sistemaOscuro(true)
    localStorage.setItem('tema', 'light')

    render(<ToggleTema />)

    expect(tema()).toBe('light')
    expect(boton().getAttribute('aria-pressed')).toBe('false')
  })

  it('sigue funcionando si el navegador no permite guardar', () => {
    sistemaOscuro(false)
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    render(<ToggleTema />)

    fireEvent.click(boton())

    expect(tema()).toBe('dark')
  })
})
