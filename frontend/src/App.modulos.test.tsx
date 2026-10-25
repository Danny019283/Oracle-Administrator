import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })
const titulo = (nombre: string) => screen.queryByRole('heading', { name: nombre, level: 1 })

describe('módulos de performance, auditoría y seguridad', () => {
  it.each([
    ['Performance de la base de datos', 'Performance de la base de datos'],
    ['Auditoría de la BD', 'Auditoría de la BD'],
    ['Seguridad de usuarios', 'Seguridad de usuarios'],
  ])('«%s» abre su pantalla y «Volver» regresa al menú', (modulo, encabezado) => {
    render(<App />)

    fireEvent.click(boton(modulo)!)

    expect(titulo(encabezado)).not.toBeNull()
    expect(boton('Creación de respaldos')).toBeNull()

    fireEvent.click(boton('Volver')!)

    expect(boton('Creación de respaldos')).not.toBeNull()
  })
})
