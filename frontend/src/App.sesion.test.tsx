import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { cerrarSesion, expirarSesion, iniciarSesion } from './sesion/sesion'

const OK = { token: 'tok-123', usuario: 'HR', sysdba: false }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>
let sesionDevuelta = OK

const DATOS = { host: 'db.local', puerto: '1522', servicio: 'XEPDB1', usuario: 'HR', password: 's3creta!', sysdba: false }

beforeEach(async () => {
  localStorage.clear()
  sesionDevuelta = OK
  fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
    if (url === '/sesion') {
      return opciones?.method === 'DELETE' ? respuesta(null, 204) : respuesta(sesionDevuelta)
    }
    if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES'] })
    return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
  })
  vi.stubGlobal('fetch', fetchFalso)
  await cerrarSesion()
})

afterEach(() => {
  expirarSesion()
  cleanup()
  vi.unstubAllGlobals()
})

const barra = () => within(screen.getByRole('banner'))
const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })

function iniciarDesdeElModal() {
  const valores = { Host: 'db.local', Puerto: '1522', Servicio: 'XEPDB1', Usuario: 'HR', Contraseña: 's3creta!' }
  for (const [nombre, valor] of Object.entries(valores)) {
    fireEvent.change(screen.getByLabelText(nombre), { target: { value: valor } })
  }
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
}

describe('sin sesión', () => {
  it('muestra el modal de inicio de sesión sobre la aplicación', () => {
    render(<App />)

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
  })

  it('deja la aplicación inerte detrás del modal', () => {
    const { container } = render(<App />)

    expect(container.querySelector('.app')!.hasAttribute('inert')).toBe(true)
  })

  it('la top bar no ofrece cerrar sesión ni muestra usuario', () => {
    render(<App />)

    expect(barra().queryByRole('button', { name: 'Cerrar sesión' })).toBeNull()
    expect(barra().queryByText('HR')).toBeNull()
  })

  it('no hace ninguna petición a /respaldos', () => {
    render(<App />)

    expect(fetchFalso.mock.calls.filter(([url]) => String(url).startsWith('/respaldos'))).toEqual([])
  })
})

describe('al iniciar sesión desde el modal', () => {
  it('cierra el modal y deja la aplicación accesible', async () => {
    const { container } = render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(container.querySelector('.app')!.hasAttribute('inert')).toBe(false)
    expect(boton('Creación de respaldos')).not.toBeNull()
  })

  it('guarda host, puerto, servicio y usuario, y nunca la contraseña', async () => {
    render(<App />)

    iniciarDesdeElModal()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    const guardado = localStorage.getItem('oracle.conexion')!
    expect(JSON.parse(guardado)).toEqual({ host: 'db.local', puerto: '1522', servicio: 'XEPDB1', usuario: 'HR' })
    expect(guardado).not.toContain('s3creta!')
  })

  it('la top bar muestra el usuario y «Cerrar sesión», sin etiqueta SYSDBA', async () => {
    render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(barra().queryByText('HR')).not.toBeNull())
    expect(barra().getByRole('button', { name: 'Cerrar sesión' })).not.toBeNull()
    expect(barra().queryByText('SYSDBA')).toBeNull()
  })

  it('con una sesión SYSDBA la top bar lo indica', async () => {
    sesionDevuelta = { token: 'tok-sys', usuario: 'SYS', sysdba: true }
    render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(barra().queryByText('SYS')).not.toBeNull())
    expect(barra().getByText('SYSDBA')).not.toBeNull()
  })
})

describe('con la sesión ya iniciada al abrir', () => {
  beforeEach(async () => {
    await iniciarSesion(DATOS)
  })

  it('no muestra el modal y la top bar tiene usuario y «Cerrar sesión»', () => {
    render(<App />)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(barra().getByText('HR')).not.toBeNull()
    expect(barra().getByRole('button', { name: 'Cerrar sesión' })).not.toBeNull()
  })

  it('las pantallas de respaldo usan el token de la sesión', async () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    const llamadas = fetchFalso.mock.calls.filter(([url]) => String(url).startsWith('/respaldos'))
    expect(llamadas.length).toBeGreaterThan(0)
    for (const [, opciones] of llamadas) {
      expect(opciones.headers.Authorization).toBe('Bearer tok-123')
    }
  })

  it('si la sesión expira vuelve el modal y la aplicación regresa al menú principal', async () => {
    render(<App />)
    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    act(() => expirarSesion())

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'CLIENTES' })).toBeNull()
    expect(barra().queryByText('HR')).toBeNull()
  })

  it('tras volver a iniciar sesión la aplicación empieza en el menú principal', async () => {
    render(<App />)
    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })
    act(() => expirarSesion())

    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(boton('Creación de respaldos')).not.toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'CLIENTES' })).toBeNull()
  })

  it('si la sesión se cierra vuelve el modal', async () => {
    render(<App />)

    await act(() => cerrarSesion())

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
  })
})
