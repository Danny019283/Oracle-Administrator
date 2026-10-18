import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ErrorConexion } from '../respaldos/api'
import {
  alCambiarSesion,
  cabeceraAutorizacion,
  cerrarSesion,
  ErrorLogin,
  expirarSesion,
  iniciarSesion,
  recordados,
  sesionActual,
  type EventoSesion,
} from './sesion'

const DATOS = {
  host: 'db.local',
  puerto: '1522',
  servicio: 'XEPDB1',
  usuario: 'HR',
  password: 's3creta!',
  sysdba: false,
}

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

const OK = { token: 'tok-123', usuario: 'HR', sysdba: false }

const simular = (...respuestas: unknown[]) => {
  const fetchFalso = vi.fn()
  for (const r of respuestas) fetchFalso.mockResolvedValueOnce(r)
  vi.stubGlobal('fetch', fetchFalso)
  return fetchFalso
}

beforeEach(async () => {
  localStorage.clear()
  await cerrarSesion()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('iniciarSesion', () => {
  it('envía los datos a POST /sesion y devuelve token, usuario y modo', async () => {
    const fetchFalso = simular(respuesta(OK))

    const sesion = await iniciarSesion({ ...DATOS, sysdba: true })

    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe('/sesion')
    expect(opciones.method).toBe('POST')
    expect(opciones.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(opciones.body)).toEqual({ ...DATOS, sysdba: true })
    expect(sesion).toEqual(OK)
  })

  it('guarda la sesión solo en memoria y la expone', async () => {
    simular(respuesta(OK))

    await iniciarSesion(DATOS)

    expect(sesionActual()).toEqual(OK)
    expect(cabeceraAutorizacion()).toEqual({ Authorization: 'Bearer tok-123' })
    expect(JSON.stringify({ ...localStorage })).not.toContain('tok-123')
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('tok-123')
  })

  it('recuerda host, puerto, servicio y usuario, y nunca la contraseña', async () => {
    simular(respuesta(OK))

    await iniciarSesion(DATOS)

    expect(recordados()).toEqual({
      host: 'db.local',
      puerto: '1522',
      servicio: 'XEPDB1',
      usuario: 'HR',
    })
    expect(JSON.stringify({ ...localStorage })).not.toContain('s3creta!')
  })

  it('no recuerda nada si el login falla', async () => {
    simular(respuesta({ mensaje: 'Usuario o contraseña incorrectos (ORA-01017)', codigo: 'ORA-01017' }, 401))

    await expect(iniciarSesion(DATOS)).rejects.toBeInstanceOf(ErrorLogin)

    expect(recordados()).toBeNull()
    expect(sesionActual()).toBeNull()
  })

  it('si el almacenamiento del navegador falla, el login igual funciona', async () => {
    simular(respuesta(OK))
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })

    await expect(iniciarSesion(DATOS)).resolves.toEqual(OK)

    vi.restoreAllMocks()
  })

  it('credenciales rechazadas: lanza ErrorLogin con mensaje y código ORA', async () => {
    simular(respuesta({ mensaje: 'Cuenta bloqueada (ORA-28000)', codigo: 'ORA-28000' }, 401))

    const error = await iniciarSesion(DATOS).catch((e) => e)

    expect(error).toBeInstanceOf(ErrorLogin)
    expect(error.mensaje).toBe('Cuenta bloqueada (ORA-28000)')
    expect(error.codigo).toBe('ORA-28000')
    expect(error.status).toBe(401)
  })

  it('Oracle inalcanzable (502 con JSON) es ErrorLogin, no backend caído', async () => {
    simular(respuesta({ mensaje: 'No hay listener (ORA-12541)', codigo: 'ORA-12541' }, 502))

    const error = await iniciarSesion(DATOS).catch((e) => e)

    expect(error).toBeInstanceOf(ErrorLogin)
    expect(error.codigo).toBe('ORA-12541')
    expect(error.status).toBe(502)
  })

  it('datos inválidos (422): lanza ErrorLogin con la lista de errores', async () => {
    simular(respuesta({ errores: ['El campo host es obligatorio', 'El puerto debe ser un número'] }, 422))

    const error = await iniciarSesion(DATOS).catch((e) => e)

    expect(error).toBeInstanceOf(ErrorLogin)
    expect(error.errores).toEqual(['El campo host es obligatorio', 'El puerto debe ser un número'])
  })

  it('sin respuesta del backend lanza ErrorConexion ERR_CONEXION', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    const error = await iniciarSesion(DATOS).catch((e) => e)

    expect(error).toBeInstanceOf(ErrorConexion)
    expect(error.codigo).toBe('ERR_CONEXION')
  })

  it.each([502, 503, 504])('el proxy responde %i sin JSON: ErrorConexion con ese código', async (status) => {
    simular(respuestaDelProxy(status))

    const error = await iniciarSesion(DATOS).catch((e) => e)

    expect(error).toBeInstanceOf(ErrorConexion)
    expect(error.codigo).toBe(String(status))
  })
})

describe('cerrarSesion', () => {
  it('llama a DELETE /sesion con el token y descarta la sesión', async () => {
    simular(respuesta(OK))
    await iniciarSesion(DATOS)
    const fetchFalso = simular({ ok: true, status: 204, json: async () => null })

    await cerrarSesion()

    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe('/sesion')
    expect(opciones.method).toBe('DELETE')
    expect(opciones.headers).toEqual({ Authorization: 'Bearer tok-123' })
    expect(sesionActual()).toBeNull()
    expect(cabeceraAutorizacion()).toEqual({})
  })

  it('descarta la sesión local aunque la petición falle', async () => {
    simular(respuesta(OK))
    await iniciarSesion(DATOS)
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    await expect(cerrarSesion()).resolves.toBeUndefined()

    expect(sesionActual()).toBeNull()
  })

  it('sin sesión no llama a la API', async () => {
    const fetchFalso = simular()

    await cerrarSesion()

    expect(fetchFalso).not.toHaveBeenCalled()
  })

  it('conserva los datos recordados, salvo la contraseña que nunca se guardó', async () => {
    simular(respuesta(OK))
    await iniciarSesion(DATOS)
    simular({ ok: true, status: 204, json: async () => null })

    await cerrarSesion()

    expect(recordados()?.usuario).toBe('HR')
  })
})

describe('expirarSesion (401 de la API)', () => {
  it('descarta el token y deja la sesión vacía', async () => {
    simular(respuesta(OK))
    await iniciarSesion(DATOS)

    expirarSesion()

    expect(sesionActual()).toBeNull()
    expect(cabeceraAutorizacion()).toEqual({})
  })
})

describe('alCambiarSesion', () => {
  it('avisa de inicio, cierre y expiración, en ese orden', async () => {
    const eventos: EventoSesion[] = []
    const dejarDeEscuchar = alCambiarSesion((e) => eventos.push(e))

    simular(respuesta(OK))
    await iniciarSesion(DATOS)
    simular({ ok: true, status: 204, json: async () => null })
    await cerrarSesion()
    simular(respuesta(OK))
    await iniciarSesion(DATOS)
    expirarSesion()
    dejarDeEscuchar()

    expect(eventos).toEqual([
      { estado: 'activa', sesion: OK },
      { estado: 'cerrada' },
      { estado: 'activa', sesion: OK },
      { estado: 'expirada' },
    ])
  })

  it('expirar sin sesión activa no avisa a nadie', () => {
    const escucha = vi.fn()
    const dejarDeEscuchar = alCambiarSesion(escucha)

    expirarSesion()
    dejarDeEscuchar()

    expect(escucha).not.toHaveBeenCalled()
  })

  it('tras dejar de escuchar ya no se recibe nada', async () => {
    const escucha = vi.fn()
    alCambiarSesion(escucha)()

    simular(respuesta(OK))
    await iniciarSesion(DATOS)

    expect(escucha).not.toHaveBeenCalled()
  })
})

describe('recordados', () => {
  it('sin datos guardados devuelve null', () => {
    expect(recordados()).toBeNull()
  })

  it('con datos corruptos devuelve null', () => {
    localStorage.setItem('oracle.conexion', '{no es json')

    expect(recordados()).toBeNull()
  })
})
