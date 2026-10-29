import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { llamar } from './api'
import { alCambiarSesion, expirarSesion, iniciarSesion, type EventoSesion } from '../sesion/sesion'

const TOKEN = 'tok-123'

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

// El proxy de Vite responde 502/503/504 con un cuerpo que no es JSON.
const respuestaDelProxy = (status: number) => ({
  ok: false,
  status,
  json: async () => {
    throw new SyntaxError('Unexpected token < in JSON')
  },
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('llamar a la API de administración', () => {
  it('una consulta envía solo el token de la sesión', async () => {
    const fetchFalso = vi.fn(async () => respuesta({ politicas: [] }))
    vi.stubGlobal('fetch', fetchFalso)

    const r = await llamar(TOKEN, '/auditoria/politicas')

    expect(r).toEqual({ ok: true, datos: { politicas: [] } })
    expect(fetchFalso).toHaveBeenCalledWith('/auditoria/politicas', {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
  })

  it('una operación envía el cuerpo en JSON con el token', async () => {
    const fetchFalso = vi.fn(async () => respuesta({ mensaje: 'listo' }))
    vi.stubGlobal('fetch', fetchFalso)

    await llamar(TOKEN, '/seguridad/usuarios', { usuario: 'HR' })

    const [url, opciones] = fetchFalso.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/seguridad/usuarios')
    expect(opciones.method).toBe('POST')
    expect(opciones.headers).toEqual({
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
    })
    expect(JSON.parse(opciones.body as string)).toEqual({ usuario: 'HR' })
  })

  it('PUT envía el cuerpo en JSON con el token y el método PUT', async () => {
    const fetchFalso = vi.fn(async () => respuesta({ mensaje: 'listo' }))
    vi.stubGlobal('fetch', fetchFalso)

    const r = await llamar(TOKEN, '/directorios/RESPALDOS', { ruta: '/opt/oracle' }, 'PUT')

    expect(r).toEqual({ ok: true, datos: { mensaje: 'listo' } })
    const [url, opciones] = fetchFalso.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/directorios/RESPALDOS')
    expect(opciones.method).toBe('PUT')
    expect(opciones.headers).toEqual({
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
    })
    expect(JSON.parse(opciones.body as string)).toEqual({ ruta: '/opt/oracle' })
  })

  it('DELETE envía solo el token y el método DELETE, sin cuerpo', async () => {
    const fetchFalso = vi.fn(async () => respuesta({ mensaje: 'listo' }))
    vi.stubGlobal('fetch', fetchFalso)

    const r = await llamar(TOKEN, '/directorios/RESPALDOS', undefined, 'DELETE')

    expect(r).toEqual({ ok: true, datos: { mensaje: 'listo' } })
    expect(fetchFalso).toHaveBeenCalledWith('/directorios/RESPALDOS', {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
  })

  it('PUT y DELETE usan el mismo manejo de errores', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta({ errores: ['ruta inválida'] }, 422)))
    expect(await llamar(TOKEN, '/directorios/X', { ruta: 'x' }, 'PUT')).toEqual({
      ok: false,
      aviso: { tipo: 'error', textos: ['ruta inválida'] },
    })

    vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(502)))
    const r = await llamar(TOKEN, '/directorios/X', undefined, 'DELETE')
    expect(r.ok).toBe(false)
  })

  it('no envía ninguna cabecera X-Oracle-*', async () => {
    const fetchFalso = vi.fn(async () => respuesta({}))
    vi.stubGlobal('fetch', fetchFalso)

    await llamar(TOKEN, '/performance/resumen')
    await llamar(TOKEN, '/performance/sesiones/terminar', { sid: 1 })

    for (const [, opciones] of fetchFalso.mock.calls as unknown as [string, RequestInit][]) {
      expect(Object.keys(opciones.headers as object).some((c) => c.startsWith('X-Oracle'))).toBe(
        false,
      )
    }
  })

  describe('errores de la API', () => {
    it('un 422 muestra la lista de errores', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta({ errores: ['Falta el nombre'] }, 422)))

      const r = await llamar(TOKEN, '/auditoria/politicas', {})

      expect(r).toEqual({ ok: false, aviso: { tipo: 'error', textos: ['Falta el nombre'] } })
    })

    it('un 404 muestra el detalle', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta({ detail: 'Usuario no administrable' }, 404)))

      const r = await llamar(TOKEN, '/seguridad/usuarios/SYS')

      expect(r).toEqual({ ok: false, aviso: { tipo: 'error', textos: ['Usuario no administrable'] } })
    })

    it('un 500 muestra el mensaje, la explicación y el error de Oracle', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          respuesta(
            {
              mensaje: 'Oracle rechazó la operación',
              explicacion: 'Privilegios insuficientes',
              error: 'ORA-01031: privilegios insuficientes',
            },
            500,
          ),
        ),
      )

      const r = await llamar(TOKEN, '/auditoria/politicas', {})

      expect(r).toEqual({
        ok: false,
        aviso: {
          tipo: 'error',
          textos: ['Oracle rechazó la operación', 'Privilegios insuficientes'],
          detalle: 'ORA-01031: privilegios insuficientes',
        },
      })
    })
  })

  describe('backend que no responde', () => {
    it('sin respuesta muestra el aviso de conexión con ERR_CONEXION', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

      const r = await llamar(TOKEN, '/performance/resumen')

      expect(r.ok).toBe(false)
      expect(!r.ok && r.aviso.textos[0]).toContain('ERR_CONEXION')
    })

    it.each([502, 503, 504])('si el proxy responde %i muestra ese código', async (codigo) => {
      vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(codigo)))

      const r = await llamar(TOKEN, '/performance/resumen')

      expect(!r.ok && r.aviso.textos[0]).toContain(String(codigo))
    })
  })

  describe('sesión expirada (401)', () => {
    let eventos: EventoSesion[]
    let dejarDeEscuchar: () => void

    beforeEach(async () => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta({ token: TOKEN, usuario: 'SYS', sysdba: true })))
      await iniciarSesion({
        host: 'h',
        puerto: '1521',
        servicio: 'S',
        usuario: 'SYS',
        password: 'x',
        sysdba: true,
      })
      eventos = []
      dejarDeEscuchar = alCambiarSesion((e) => eventos.push(e))
    })

    afterEach(() => {
      dejarDeEscuchar()
      expirarSesion()
    })

    it('un 401 expira la sesión', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta({ detail: 'Sesión no válida o expirada' }, 401)))

      const r = await llamar(TOKEN, '/auditoria/estado')

      expect(r.ok).toBe(false)
      expect(eventos).toEqual([{ estado: 'expirada' }])
    })

    it('otros errores no expiran la sesión', async () => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta({ errores: ['x'] }, 422)))

      await llamar(TOKEN, '/auditoria/estado')

      expect(eventos).toEqual([])
    })
  })
})
