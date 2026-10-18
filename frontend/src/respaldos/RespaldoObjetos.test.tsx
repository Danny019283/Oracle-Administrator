import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RespaldoObjetos, type TipoObjeto } from './RespaldoObjetos'
import { alCambiarSesion, expirarSesion, iniciarSesion, type EventoSesion } from '../sesion/sesion'

const TOKEN = 'tok-123'
const TABLAS: TipoObjeto = {
  recurso: 'tablas',
  titulo: 'Respaldar tablas',
  encabezadoLista: 'Tablas',
  descripcion: 'Elige las tablas, el directorio de destino y el nombre del respaldo.',
  seleccionarTodos: 'Seleccionar todas',
}
const SCHEMAS: TipoObjeto = {
  recurso: 'schemas',
  titulo: 'Respaldar schemas',
  encabezadoLista: 'Schemas',
  descripcion: 'Elige los schemas, el directorio de destino y el nombre del respaldo.',
  seleccionarTodos: 'Seleccionar todos',
}

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
    if (opciones?.method === 'POST') {
      return respuesta({ dmp: 'ventas_20261017_153045.dmp', log: 'ventas_20261017_153045.log' })
    }
    if (url === '/respaldos/directorios') {
      return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
    }
    return respuesta({ [url.split('/').pop()!]: ['UNO', 'DOS'] })
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('autenticación con el token de la sesión', () => {
  it('envía Authorization Bearer en las consultas y en el respaldo, y ninguna cabecera X-Oracle', async () => {
    render(<RespaldoObjetos token={TOKEN} tipo={TABLAS} />)
    await screen.findByRole('checkbox', { name: 'UNO' })
    await screen.findByRole('option', { name: /RESPALDO/ })
    fireEvent.click(screen.getByRole('checkbox', { name: 'UNO' }))
    fireEvent.change(screen.getByLabelText('Directorio'), { target: { value: 'RESPALDO' } })
    fireEvent.change(screen.getByLabelText('Nombre del dumpfile'), { target: { value: 'ventas' } })
    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
    await screen.findByRole('status')

    expect(fetchFalso.mock.calls).toHaveLength(3)
    for (const [, opciones] of fetchFalso.mock.calls) {
      expect(opciones.headers.Authorization).toBe('Bearer tok-123')
      expect(Object.keys(opciones.headers).some((c) => c.startsWith('X-Oracle'))).toBe(false)
    }
  })

  it('el respaldo conserva Content-Type junto con Authorization', async () => {
    render(<RespaldoObjetos token={TOKEN} tipo={TABLAS} />)
    await screen.findByRole('checkbox', { name: 'UNO' })
    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
    await waitFor(() => expect(fetchFalso.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(true))

    const [, opciones] = fetchFalso.mock.calls.find(([, o]) => o?.method === 'POST')!
    expect(opciones.headers).toEqual({
      Authorization: 'Bearer tok-123',
      'Content-Type': 'application/json',
    })
  })
})

describe('sesión expirada (401)', () => {
  let eventos: EventoSesion[]
  let dejarDeEscuchar: () => void

  beforeEach(async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta({ token: TOKEN, usuario: 'HR', sysdba: false })))
    await iniciarSesion({
      host: 'h',
      puerto: '1521',
      servicio: 'S',
      usuario: 'HR',
      password: 'x',
      sysdba: false,
    })
    eventos = []
    dejarDeEscuchar = alCambiarSesion((e) => eventos.push(e))
  })

  afterEach(() => {
    dejarDeEscuchar()
    expirarSesion()
  })

  it('un 401 al cargar las listas expira la sesión', async () => {
    fetchFalso = vi.fn(async () => respuesta({ detail: 'Sesión no válida o expirada' }, 401))
    vi.stubGlobal('fetch', fetchFalso)

    render(<RespaldoObjetos token={TOKEN} tipo={TABLAS} />)

    await waitFor(() => expect(eventos).toEqual([{ estado: 'expirada' }]))
  })

  it('un 401 al respaldar expira la sesión', async () => {
    fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
      if (opciones?.method === 'POST') return respuesta({ detail: 'Sesión no válida o expirada' }, 401)
      if (url === '/respaldos/directorios') return respuesta({ directorios: [] }, 404)
      return respuesta({ tablas: ['UNO'] })
    })
    vi.stubGlobal('fetch', fetchFalso)
    render(<RespaldoObjetos token={TOKEN} tipo={TABLAS} />)
    await screen.findByRole('checkbox', { name: 'UNO' })

    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    await waitFor(() => expect(eventos).toEqual([{ estado: 'expirada' }]))
  })

  it('otros errores del servidor no expiran la sesión', async () => {
    fetchFalso = vi.fn(async () => respuesta({ detail: 'No hay tablas en el schema' }, 404))
    vi.stubGlobal('fetch', fetchFalso)

    render(<RespaldoObjetos token={TOKEN} tipo={TABLAS} />)
    await screen.findByRole('alert')

    expect(eventos).toEqual([])
  })
})

describe.each([
  [TABLAS, 'tablas'],
  [SCHEMAS, 'schemas'],
])('pantalla común de respaldo (%#)', (tipo, recurso) => {
  it('muestra el título, la descripción y el encabezado del tipo', async () => {
    render(<RespaldoObjetos token={TOKEN} tipo={tipo} />)
    await screen.findByRole('checkbox', { name: 'UNO' })

    expect(screen.getByRole('heading', { name: tipo.titulo })).not.toBeNull()
    expect(screen.getByRole('heading', { name: tipo.encabezadoLista })).not.toBeNull()
    expect(screen.getByText(tipo.descripcion)).not.toBeNull()
    expect(screen.getByRole('checkbox', { name: tipo.seleccionarTodos })).not.toBeNull()
  })

  it('lista los objetos de /respaldos/<recurso>', async () => {
    render(<RespaldoObjetos token={TOKEN} tipo={tipo} />)

    expect(await screen.findByRole('checkbox', { name: 'DOS' })).not.toBeNull()
    expect(fetchFalso.mock.calls.map(([url]) => url)).toContain(`/respaldos/${recurso}`)
  })

  it('envía la selección en el campo con el nombre del recurso', async () => {
    render(<RespaldoObjetos token={TOKEN} tipo={tipo} />)
    await screen.findByRole('checkbox', { name: 'UNO' })
    await screen.findByRole('option', { name: /RESPALDO/ })

    fireEvent.click(screen.getByRole('checkbox', { name: 'DOS' }))
    fireEvent.change(screen.getByLabelText('Directorio'), { target: { value: 'RESPALDO' } })
    fireEvent.change(screen.getByLabelText('Nombre del dumpfile'), { target: { value: 'ventas' } })
    fetchFalso.mockClear()
    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe(`/respaldos/${recurso}`)
    expect(JSON.parse(opciones.body)).toEqual({
      [recurso]: ['DOS'],
      directorio: 'RESPALDO',
      nombre: 'ventas',
    })
  })
})
