import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RespaldoFull } from './RespaldoFull'
import { alCambiarSesion, expirarSesion, iniciarSesion, type EventoSesion } from '../sesion/sesion'

const TOKEN = 'tok-123'
const CABECERAS = { Authorization: `Bearer ${TOKEN}` }
const DIRECTORIOS = { directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] }
const EXITO = { log: 'piezas creadas: semanal_XE_1', advertencia: null }
const MENSAJE_CONEXION =
  'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución'
const CONFIRMACION =
  'Activar ARCHIVELOG reinicia la base de datos y corta todas las sesiones, incluida la tuya. ¿Continuar?'

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

type Respuesta = ReturnType<typeof respuesta>
type Escenario = {
  estado?: Respuesta
  directorios?: Respuesta
  respaldo?: Respuesta | Error
  archivelog?: Respuesta
}

let fetchFalso: ReturnType<typeof vi.fn>

const montar = ({ estado, directorios, respaldo, archivelog }: Escenario = {}) => {
  fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
    if (url === '/respaldos/full/archivelog') {
      return archivelog ?? respuesta({ mensaje: 'ARCHIVELOG activado. Inicia sesión de nuevo', log: '' })
    }
    if (opciones?.method === 'POST') {
      if (respaldo instanceof Error) throw respaldo
      return respaldo ?? respuesta(EXITO)
    }
    if (url === '/respaldos/full/estado') return estado ?? respuesta({ archivelog: true })
    if (url === '/respaldos/directorios') return directorios ?? respuesta(DIRECTORIOS)
    throw new Error(`URL inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchFalso)
  render(<RespaldoFull token={TOKEN} />)
}

const llamadasPost = (url: string) =>
  fetchFalso.mock.calls.filter(([u, o]) => u === url && o?.method === 'POST')

const respaldar = async (nombre = 'semanal') => {
  await screen.findByRole('option', { name: /RESPALDO/ })
  fireEvent.change(screen.getByLabelText('Directorio'), { target: { value: 'RESPALDO' } })
  fireEvent.change(screen.getByLabelText('Nombre del respaldo'), { target: { value: nombre } })
  fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('pantalla de respaldo Full', () => {
  it('muestra el título, consulta el modo de log y lista los directorios con el token', async () => {
    montar()

    expect(screen.getByRole('heading', { name: 'Respaldar base completa (Full)' })).toBeTruthy()
    await screen.findByRole('option', { name: /RESPALDO/ })
    expect(fetchFalso).toHaveBeenCalledWith('/respaldos/full/estado', { headers: CABECERAS })
    expect(fetchFalso).toHaveBeenCalledWith('/respaldos/directorios', { headers: CABECERAS })
  })

  it('en ARCHIVELOG lo indica y no ofrece activarlo', async () => {
    montar()

    await screen.findByText('La base de datos está en modo ARCHIVELOG')
    expect(screen.queryByRole('button', { name: 'Activar ARCHIVELOG' })).toBeNull()
  })

  it('en NOARCHIVELOG avisa y ofrece «Activar ARCHIVELOG»', async () => {
    montar({ estado: respuesta({ archivelog: false }) })

    await screen.findByText('La base de datos está en NOARCHIVELOG: actívalo para poder respaldar')
    expect(screen.getByRole('button', { name: 'Activar ARCHIVELOG' })).toBeTruthy()
  })

  it('sin directorios muestra el mensaje y no deja respaldar', async () => {
    montar({
      directorios: respuesta({ detail: 'No hay directorios disponibles. Debes crear uno' }, 404),
    })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('No hay directorios disponibles')
    expect(fetchFalso).not.toHaveBeenCalledWith(
      '/respaldos/full',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('al respaldar envía el DIRECTORY y el nombre elegidos', async () => {
    montar()

    await respaldar('semanal')

    await waitFor(() => expect(llamadasPost('/respaldos/full')).toHaveLength(1))
    const [, opciones] = llamadasPost('/respaldos/full')[0]
    expect(opciones.headers).toMatchObject(CABECERAS)
    expect(JSON.parse(opciones.body)).toEqual({ directorio: 'RESPALDO', nombre: 'semanal' })
  })

  it('mientras respalda muestra el progreso y deshabilita el botón', async () => {
    let terminar: (r: Respuesta) => void = () => {}
    fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
      if (opciones?.method === 'POST') return new Promise<Respuesta>((r) => (terminar = r))
      if (url === '/respaldos/full/estado') return respuesta({ archivelog: true })
      return respuesta(DIRECTORIOS)
    })
    vi.stubGlobal('fetch', fetchFalso)
    render(<RespaldoFull token={TOKEN} />)

    await respaldar()

    await screen.findByText('Respaldando...')
    expect((screen.getByRole('button', { name: 'Respaldar' }) as HTMLButtonElement).disabled).toBe(true)
    terminar(respuesta(EXITO))
    await waitFor(() => expect(screen.queryByText('Respaldando...')).toBeNull())
  })

  it('al terminar informa el éxito con el log de RMAN y sin advertencia', async () => {
    montar()

    await respaldar()

    const estado = await screen.findByRole('status')
    expect(estado.textContent).toContain('Respaldo full creado')
    expect(estado.textContent).toContain('piezas creadas: semanal_XE_1')
    expect(screen.queryByRole('note')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('si la limpieza falló informa el éxito y aparte la advertencia con su explicación y log', async () => {
    montar({
      respaldo: respuesta({
        log: 'piezas creadas: semanal_XE_1',
        advertencia: {
          explicacion: 'Faltan archivelogs necesarios para el respaldo; ejecuta un CROSSCHECK',
          log: 'RMAN-06059: falta un archivelog',
        },
      }),
    })

    await respaldar()

    expect((await screen.findByRole('status')).textContent).toContain('Respaldo full creado')
    const advertencia = screen.getByRole('note')
    expect(advertencia.textContent).toContain('la limpieza de respaldos obsoletos falló')
    expect(advertencia.textContent).toContain('Faltan archivelogs necesarios')
    expect(advertencia.querySelector('pre')?.textContent).toBe('RMAN-06059: falta un archivelog')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('si faltan datos (422) indica cada uno y no da por creado el respaldo', async () => {
    montar({
      respaldo: respuesta(
        { errores: ['Debes elegir un directorio', 'Debes ingresar un nombre de dumpfile'] },
        422,
      ),
    })

    await respaldar('')

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('Debes elegir un directorio')
    expect(alerta.textContent).toContain('Debes ingresar un nombre de dumpfile')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('sin ARCHIVELOG al solicitar (409) muestra el mensaje con su explicación', async () => {
    montar({
      respaldo: respuesta(
        {
          mensaje: 'La base de datos no está en ARCHIVELOG: actívalo para poder respaldar',
          explicacion: 'La base no está en ARCHIVELOG: actívalo para respaldar en caliente',
        },
        409,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('no está en ARCHIVELOG: actívalo para poder respaldar')
    expect(alerta.textContent).toContain('actívalo para respaldar en caliente')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('si RMAN falla (500) muestra el mensaje, la explicación y el log', async () => {
    montar({
      respaldo: respuesta(
        {
          mensaje: 'El respaldo falló: rman terminó con código 1',
          explicacion: 'Faltan archivelogs necesarios para el respaldo; ejecuta un CROSSCHECK',
          log: 'RMAN-06059: falta un archivelog',
        },
        500,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('rman terminó con código 1')
    expect(alerta.textContent).toContain('Faltan archivelogs necesarios')
    expect(alerta.querySelector('pre')?.textContent).toBe('RMAN-06059: falta un archivelog')
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('activar ARCHIVELOG', () => {
  const abrirConfirmacion = async () => {
    montar({ estado: respuesta({ archivelog: false }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Activar ARCHIVELOG' }))
  }

  it('pide confirmación explícita y no activa nada hasta confirmar', async () => {
    await abrirConfirmacion()

    expect(screen.getByText(CONFIRMACION)).toBeTruthy()
    expect(llamadasPost('/respaldos/full/archivelog')).toHaveLength(0)
  })

  it('cancelar descarta la confirmación sin activar nada', async () => {
    await abrirConfirmacion()

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(screen.queryByText(CONFIRMACION)).toBeNull()
    expect(screen.getByRole('button', { name: 'Activar ARCHIVELOG' })).toBeTruthy()
    expect(llamadasPost('/respaldos/full/archivelog')).toHaveLength(0)
  })

  it('al confirmar lo activa y pide iniciar sesión de nuevo', async () => {
    await abrirConfirmacion()

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    const estado = await screen.findByRole('status')
    expect(estado.textContent).toContain('ARCHIVELOG activado. Inicia sesión de nuevo')
    expect(llamadasPost('/respaldos/full/archivelog')).toHaveLength(1)
    expect(llamadasPost('/respaldos/full/archivelog')[0][1].headers).toMatchObject(CABECERAS)
    expect(screen.queryByRole('button', { name: 'Activar ARCHIVELOG' })).toBeNull()
  })

  it('si falla muestra «No se pudo activar ARCHIVELOG» con la explicación y el log', async () => {
    montar({
      estado: respuesta({ archivelog: false }),
      archivelog: respuesta(
        {
          mensaje: 'No se pudo activar ARCHIVELOG',
          explicacion: 'Se superó el límite de la zona de recuperación (FRA)',
          log: 'ORA-19809: límite de la FRA superado',
        },
        500,
      ),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Activar ARCHIVELOG' }))

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('No se pudo activar ARCHIVELOG')
    expect(alerta.textContent).toContain('Se superó el límite de la zona de recuperación')
    expect(alerta.querySelector('pre')?.textContent).toBe('ORA-19809: límite de la FRA superado')
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('sesión sin SYSDBA', () => {
  it('muestra el aviso, no deja respaldar y no ofrece activar ARCHIVELOG', async () => {
    montar({ estado: respuesta({ detail: 'Se requiere sesión SYSDBA' }, 403) })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('Se requiere sesión SYSDBA')
    expect((screen.getByRole('button', { name: 'Respaldar' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByRole('button', { name: 'Activar ARCHIVELOG' })).toBeNull()
    expect(screen.queryByText('La base de datos está en modo ARCHIVELOG')).toBeNull()
  })

  it('un 403 al respaldar también muestra el aviso', async () => {
    montar({ respaldo: respuesta({ detail: 'Se requiere sesión SYSDBA' }, 403) })

    await respaldar()

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA')
  })
})

describe('backend que no responde', () => {
  it('sin respuesta muestra el mensaje con ERR_CONEXION en un solo aviso', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    render(<RespaldoFull token={TOKEN} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(alerta.textContent).toContain('ERR_CONEXION')
    expect(alerta.querySelectorAll('p')).toHaveLength(1)
  })

  it('si el proxy responde 502 muestra ese código', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(502)))
    render(<RespaldoFull token={TOKEN} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(alerta.textContent).toContain('502')
  })

  it('si cae al respaldar muestra el aviso y no da por creado el respaldo', async () => {
    montar({ respaldo: new TypeError('Failed to fetch') })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(screen.queryByRole('status')).toBeNull()
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

  it('un 401 al cargar el estado expira la sesión', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta({ detail: 'Sesión no válida o expirada' }, 401)))

    render(<RespaldoFull token={TOKEN} />)

    await waitFor(() => expect(eventos).toContainEqual({ estado: 'expirada' }))
  })

  it('un 401 al respaldar expira la sesión', async () => {
    montar({ respaldo: respuesta({ detail: 'Sesión no válida o expirada' }, 401) })

    await respaldar()

    await waitFor(() => expect(eventos).toContainEqual({ estado: 'expirada' }))
  })
})
