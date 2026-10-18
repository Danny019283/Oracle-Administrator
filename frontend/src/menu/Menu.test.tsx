import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from '../App'
import { expirarSesion, iniciarSesion } from '../sesion/sesion'

const respuesta = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const DATOS = { host: 'h', puerto: '1521', servicio: 'XEPDB1', usuario: 'HR', password: 'x', sysdba: false }

beforeEach(async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url === '/sesion') return respuesta({ token: 'tok-123', usuario: 'HR', sysdba: false })
      if (url === '/respaldos/directorios') return respuesta({ directorios: [] })
      return respuesta({ tablas: [], schemas: [] })
    }),
  )
  await iniciarSesion(DATOS)
})

afterEach(() => {
  expirarSesion()
  cleanup()
  vi.unstubAllGlobals()
})

const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })

describe('menú principal', () => {
  it('muestra los módulos de administración, incluida la creación de respaldos', () => {
    render(<App />)

    for (const modulo of [
      'Administración de tablespaces',
      'Tunning de consultas',
      'Performance de la base de datos',
      'Auditoría de la BD',
      'Seguridad de usuarios',
      'Creación de respaldos',
      'Recuperación de respaldos',
      'Administración de archivos de respaldos y directorios',
    ]) {
      expect(boton(modulo), modulo).not.toBeNull()
    }
  })

  it('no muestra el submenú de respaldos hasta elegir «Creación de respaldos»', () => {
    render(<App />)

    expect(boton('Tablas')).toBeNull()
  })

  it('al elegir «Creación de respaldos» ofrece Tablas, Schemas y Full', () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)

    expect(boton('Tablas')).not.toBeNull()
    expect(boton('Schemas')).not.toBeNull()
    expect(boton('Full')).not.toBeNull()
  })

  it('al elegir «Tablas» lleva a la pantalla de respaldo de tablas', () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)

    expect(screen.queryByRole('heading', { name: 'Respaldar tablas' })).not.toBeNull()
  })

  it('«Schemas» está disponible y lleva a la pantalla de respaldo de schemas', () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)
    expect(boton('Schemas')!.getAttribute('aria-disabled')).toBeNull()
    fireEvent.click(boton('Schemas')!)

    expect(screen.queryByRole('heading', { name: 'Respaldar schemas' })).not.toBeNull()
  })

  it('«Full» sigue sin estar disponible', () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)

    expect(boton('Full')!.getAttribute('aria-disabled')).toBe('true')
  })
})
