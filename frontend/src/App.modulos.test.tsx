import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { cerrarSesion, expirarSesion, iniciarSesion } from './sesion/sesion'

const TOKEN = 'tok-123'
const DATOS = { host: 'h', puerto: '1521', servicio: 'XEPDB1', usuario: 'HR', password: 'x', sysdba: false }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(async () => {
  fetchFalso = vi.fn(async (url: string) => {
    if (url === '/sesion') return respuesta({ token: TOKEN, usuario: 'HR', sysdba: false })
    return respuesta({ detail: 'Sin datos de prueba' }, 404)
  })
  vi.stubGlobal('fetch', fetchFalso)
  await iniciarSesion(DATOS)
})

afterEach(() => {
  expirarSesion()
  cleanup()
  vi.unstubAllGlobals()
})

const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })
const titulo = (nombre: string) => screen.queryByRole('heading', { name: nombre, level: 1 })

const MODULOS = [
  ['Performance de la base de datos', 'Performance de la base de datos', '/performance/resumen'],
  ['Auditoría de la BD', 'Auditoría de la BD', '/auditoria/estado'],
  ['Seguridad de usuarios', 'Seguridad de usuarios', '/seguridad/usuarios'],
]

const llamadasA = (url: string) => fetchFalso.mock.calls.filter(([u]) => u === url)

describe('módulos de performance, auditoría y seguridad', () => {
  it.each(MODULOS)('«%s» abre su pantalla y «Volver» regresa al menú', (modulo, encabezado) => {
    render(<App />)

    fireEvent.click(boton(modulo)!)

    expect(titulo(encabezado)).not.toBeNull()
    expect(boton('Creación de respaldos')).toBeNull()

    fireEvent.click(boton('Volver')!)

    expect(boton('Creación de respaldos')).not.toBeNull()
  })

  it.each(MODULOS)('«%s» consulta con el token de la sesión y sin credenciales', async (modulo, _e, ruta) => {
    render(<App />)

    fireEvent.click(boton(modulo)!)

    await waitFor(() => expect(llamadasA(ruta).length).toBeGreaterThan(0))
    for (const [, opciones] of llamadasA(ruta)) {
      expect(opciones.headers).toEqual({ Authorization: `Bearer ${TOKEN}` })
    }
  })

  it('las pantallas pertenecen a la sesión: al iniciar otra vuelve el menú principal', async () => {
    render(<App />)
    fireEvent.click(boton('Auditoría de la BD')!)
    expect(titulo('Auditoría de la BD')).not.toBeNull()

    await act(async () => {
      await cerrarSesion()
    })
    fetchFalso.mockImplementation(async (url: string) =>
      url === '/sesion'
        ? respuesta({ token: 'tok-456', usuario: 'HR', sysdba: false })
        : respuesta({ detail: 'Sin datos de prueba' }, 404),
    )
    await act(async () => {
      await iniciarSesion(DATOS)
    })

    expect(titulo('Auditoría de la BD')).toBeNull()
    expect(boton('Creación de respaldos')).not.toBeNull()
  })

  it('sin sesión no se abre ningún módulo ni se consulta la API', async () => {
    await act(async () => {
      await cerrarSesion()
    })
    fetchFalso.mockClear()
    render(<App />)

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(titulo('Auditoría de la BD')).toBeNull()
    expect(llamadasA('/auditoria/estado')).toHaveLength(0)
  })
})
