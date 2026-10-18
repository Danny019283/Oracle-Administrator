import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from './App'
import { expirarSesion, iniciarSesion } from './sesion/sesion'

const respuesta = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const DATOS = { host: 'h', puerto: '1521', servicio: 'XEPDB1', usuario: 'HR', password: 'x', sysdba: false }

beforeEach(async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url === '/sesion') return respuesta({ token: 'tok-123', usuario: 'HR', sysdba: false })
      return url === '/respaldos/tablas'
        ? respuesta({ tablas: ['CLIENTES'] })
        : respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
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
const titulo = (nombre: string) => screen.queryByRole('heading', { name: nombre })

const irASubmenu = () => fireEvent.click(boton('Creación de respaldos')!)
const irATablas = () => {
  irASubmenu()
  fireEvent.click(boton('Tablas')!)
}

describe('navegación de una pantalla a la vez', () => {
  it('al elegir «Creación de respaldos» el submenú reemplaza al menú principal', () => {
    render(<App />)

    irASubmenu()

    expect(boton('Tablas')).not.toBeNull()
    expect(boton('Schemas')).not.toBeNull()
    expect(boton('Full')).not.toBeNull()
    expect(boton('Tunning de consultas')).toBeNull()
    expect(boton('Creación de respaldos')).toBeNull()
  })

  it('desde el submenú «Volver» regresa al menú principal', () => {
    render(<App />)
    irASubmenu()

    fireEvent.click(boton('Volver')!)

    expect(boton('Creación de respaldos')).not.toBeNull()
    expect(boton('Tablas')).toBeNull()
    expect(boton('Volver')).toBeNull()
  })

  it('al elegir «Tablas» la pantalla de respaldo reemplaza al submenú', () => {
    render(<App />)

    irATablas()

    expect(titulo('Respaldar tablas')).not.toBeNull()
    expect(boton('Tablas')).toBeNull()
    expect(boton('Schemas')).toBeNull()
    expect(boton('Tunning de consultas')).toBeNull()
  })

  it('desde la pantalla de tablas «Volver» regresa al submenú', () => {
    render(<App />)
    irATablas()

    fireEvent.click(boton('Volver')!)

    expect(titulo('Respaldar tablas')).toBeNull()
    expect(boton('Tablas')).not.toBeNull()
    expect(boton('Schemas')).not.toBeNull()
  })

  it('al elegir «Schemas» la pantalla de respaldo de schemas reemplaza al submenú', () => {
    render(<App />)

    irASubmenu()
    fireEvent.click(boton('Schemas')!)

    expect(titulo('Respaldar schemas')).not.toBeNull()
    expect(boton('Tablas')).toBeNull()
    expect(boton('Schemas')).toBeNull()
    expect(boton('Tunning de consultas')).toBeNull()
  })

  it('desde la pantalla de schemas «Volver» regresa al submenú', () => {
    render(<App />)
    irASubmenu()
    fireEvent.click(boton('Schemas')!)

    fireEvent.click(boton('Volver')!)

    expect(titulo('Respaldar schemas')).toBeNull()
    expect(boton('Tablas')).not.toBeNull()
    expect(boton('Schemas')).not.toBeNull()
  })

  it('el menú principal no muestra ningún botón «Volver»', () => {
    render(<App />)

    expect(boton('Volver')).toBeNull()
  })
})
