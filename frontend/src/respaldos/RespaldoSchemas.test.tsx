import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RespaldoSchemas } from './RespaldoSchemas'

const CREDENCIALES = { usuario: 'SYSTEM', password: 's3creta!', servicio: 'XEPDB1' }
const CABECERAS = {
  'X-Oracle-User': 'SYSTEM',
  'X-Oracle-Password': 's3creta!',
  'X-Oracle-Service': 'XEPDB1',
}
const DIRECTORIOS = { directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] }
const EXITO = { dmp: 'ventas_20261017_153045.dmp', log: 'ventas_20261017_153045.log' }
const MENSAJE_CONEXION =
  'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución'

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
type Escenario = { schemas?: Respuesta; directorios?: Respuesta; respaldo?: Respuesta | Error }

let fetchFalso: ReturnType<typeof vi.fn>

const montar = ({ schemas, directorios, respaldo }: Escenario = {}) => {
  fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
    if (opciones?.method === 'POST') {
      if (respaldo instanceof Error) throw respaldo
      return respaldo ?? respuesta(EXITO)
    }
    if (url === '/respaldos/schemas') return schemas ?? respuesta({ schemas: ['HR', 'VENTAS'] })
    if (url === '/respaldos/directorios') return directorios ?? respuesta(DIRECTORIOS)
    throw new Error(`URL inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchFalso)
  render(<RespaldoSchemas credenciales={CREDENCIALES} />)
}

const casilla = (nombre: string) =>
  screen.getByRole('checkbox', { name: nombre }) as HTMLInputElement

const respaldar = async () => {
  await screen.findByRole('option', { name: /RESPALDO/ })
  fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('pantalla de respaldo de schemas', () => {
  it('lista los schemas de usuario con una casilla por schema', async () => {
    montar()

    expect(await screen.findByRole('checkbox', { name: 'HR' })).not.toBeNull()
    expect(screen.getByRole('checkbox', { name: 'VENTAS' })).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Respaldar schemas' })).not.toBeNull()
  })

  it('consulta schemas y directorios enviando las credenciales en las cabeceras', async () => {
    montar()
    await screen.findByRole('checkbox', { name: 'HR' })

    const llamadas = fetchFalso.mock.calls.map(([url, opciones]) => [url, opciones?.headers])
    expect(llamadas).toContainEqual(['/respaldos/schemas', CABECERAS])
    expect(llamadas).toContainEqual(['/respaldos/directorios', CABECERAS])
  })

  it('«Seleccionar todos» marca y desmarca todos los schemas', async () => {
    montar()
    await screen.findByRole('checkbox', { name: 'HR' })

    fireEvent.click(casilla('Seleccionar todos'))
    expect(casilla('HR').checked).toBe(true)
    expect(casilla('VENTAS').checked).toBe(true)

    fireEvent.click(casilla('Seleccionar todos'))
    expect(casilla('HR').checked).toBe(false)
    expect(casilla('VENTAS').checked).toBe(false)
  })

  it('al respaldar envía los schemas marcados, el DIRECTORY y el nombre del dumpfile', async () => {
    montar()
    await screen.findByRole('checkbox', { name: 'HR' })
    await screen.findByRole('option', { name: /RESPALDO/ })

    fireEvent.click(casilla('VENTAS'))
    fireEvent.change(screen.getByLabelText('Directorio'), { target: { value: 'RESPALDO' } })
    fireEvent.change(screen.getByLabelText('Nombre del dumpfile'), { target: { value: 'ventas' } })
    fetchFalso.mockClear()
    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe('/respaldos/schemas')
    expect(opciones.method).toBe('POST')
    expect(opciones.headers).toMatchObject(CABECERAS)
    expect(JSON.parse(opciones.body)).toEqual({
      schemas: ['VENTAS'],
      directorio: 'RESPALDO',
      nombre: 'ventas',
    })
  })
})

describe('resultado del respaldo de schemas', () => {
  it('al terminar bien informa los nombres del .dmp y del .log', async () => {
    montar()

    await respaldar()

    const estado = await screen.findByRole('status')
    expect(estado.textContent).toContain('ventas_20261017_153045.dmp')
    expect(estado.textContent).toContain('ventas_20261017_153045.log')
  })

  it('muestra cada dato faltante cuando la solicitud es inválida', async () => {
    montar({
      respaldo: respuesta(
        {
          errores: [
            'Debes seleccionar al menos un schema',
            'Debes elegir un directorio',
            'Debes ingresar un nombre de dumpfile',
          ],
        },
        422,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('Debes seleccionar al menos un schema')
    expect(alerta.textContent).toContain('Debes elegir un directorio')
    expect(alerta.textContent).toContain('Debes ingresar un nombre de dumpfile')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('si no hay schemas de usuario lo avisa con el mensaje del servidor', async () => {
    montar({ schemas: respuesta({ detail: 'No hay schemas de usuario' }, 404) })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('No hay schemas de usuario')
  })

  it('si no hay DIRECTORY lo avisa y sugiere crear uno', async () => {
    montar({
      directorios: respuesta(
        { detail: 'No hay directorios disponibles. Debes crear uno desde esta pantalla para poder respaldar' },
        404,
      ),
    })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('No hay directorios disponibles')
    expect(alerta.textContent).toContain('crear uno')
  })

  it('si expdp falla muestra el mensaje, la explicación antes del log y el log en un bloque aparte', async () => {
    const explicacion = 'Ya existe un archivo de respaldo con ese nombre en el directorio'
    const log = 'ORA-31641: no se puede crear el archivo\nORA-27038: el archivo creado ya existe'
    montar({
      respaldo: respuesta(
        { mensaje: 'El respaldo falló: expdp terminó con código 5', explicacion, log },
        500,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    const texto = alerta.textContent ?? ''
    expect(texto).toContain('expdp terminó con código 5')
    expect(texto.indexOf(explicacion)).toBeGreaterThanOrEqual(0)
    expect(texto.indexOf(explicacion)).toBeLessThan(texto.indexOf('ORA-31641'))
    expect(alerta.querySelector('pre')?.textContent).toBe(log)
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('backend que no responde en la pantalla de schemas', () => {
  it('sin respuesta alguna muestra un solo aviso con el código ERR_CONEXION', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    render(<RespaldoSchemas credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(alerta.textContent).toContain('ERR_CONEXION')
    expect(alerta.querySelectorAll('p')).toHaveLength(1)
  })

  it.each([502, 503, 504])('si el proxy responde %i muestra ese código', async (codigo) => {
    vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(codigo)))
    render(<RespaldoSchemas credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(alerta.textContent).toContain(String(codigo))
    expect(alerta.textContent).not.toContain('ERR_CONEXION')
  })

  it('si cae al respaldar muestra el aviso y no da por creado el respaldo', async () => {
    montar({ respaldo: new TypeError('Failed to fetch') })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(MENSAJE_CONEXION)
    expect(alerta.textContent).toContain('ERR_CONEXION')
    expect(screen.queryByRole('status')).toBeNull()
  })
})
