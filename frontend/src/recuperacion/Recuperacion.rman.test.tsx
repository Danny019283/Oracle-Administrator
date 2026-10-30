import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Recuperacion } from './Recuperacion'
import * as sesion from '../sesion/sesion'

const TOKEN = 'tok-123'
const RMAN = {
  directorio: 'RESPALDOS',
  ruta: '/opt/oracle/respaldos',
  base: 'full_20250102_030405',
  tipo: 'RMAN',
  estado: 'Completo',
  archivos: [{ nombre: 'full_20250102_030405_ORCL_1_1.dbf', tamano: 2048 }],
  tamano: 2048,
  fecha: '2025-01-02T03:04:05',
}
const URL_RECUPERAR = '/directorios/RESPALDOS/respaldos/full_20250102_030405/recuperar'
const CONFIRMACION_ARCHIVELOG =
  'Activar ARCHIVELOG reinicia la base de datos y corta todas las sesiones, incluida la tuya. ¿Continuar?'

const respuesta = (status: number, cuerpo: unknown) => ({ ok: status < 400, status, json: async () => cuerpo })

let fetchFalso: ReturnType<typeof vi.fn>

const simular = (post: unknown, respaldo = RMAN, archivelog: unknown = respuesta(200, {})) => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (url === '/respaldos/full/archivelog') return archivelog
    return opciones?.method === 'POST' ? post : respuesta(200, { respaldos: [respaldo], avisos: [] })
  })
  vi.stubGlobal('fetch', fetchFalso)
}

const posts = () => fetchFalso.mock.calls.filter(([url, o]) => o?.method === 'POST' && url === URL_RECUPERAR)

const abrirFormulario = async () => {
  render(<Recuperacion token={TOKEN} />)
  fireEvent.click(await screen.findByRole('button', { name: /^Recuperar/ }))
}

const escribir = (etiqueta: string, valor: string) =>
  fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } })

const elegirTabla = () => {
  escribir('Modo', 'tabla')
  escribir('Tabla', 'HR.EMPLEADOS')
  escribir('UNTIL TIME', '2025-01-02 04:00:00')
  escribir('Nombre nuevo', 'EMPLEADOS_RECUPERADA')
}

const confirmar = () => {
  fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))
  fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('Recuperar un respaldo RMAN', () => {
  it('muestra el formulario con «Base completa» y «Tabla», sin los campos de Data Pump', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()

    const modo = screen.getByLabelText('Modo') as HTMLSelectElement
    expect(Array.from(modo.options).map((o) => o.text)).toEqual(['Base completa', 'Tabla'])
    expect(modo.value).toBe('full')
    expect(screen.getByLabelText('UNTIL TIME (opcional)')).not.toBeNull()
    expect(screen.queryByLabelText('Objetos')).toBeNull()
    expect(screen.queryByLabelText('Tabla')).toBeNull()
  })

  it('en modo Tabla pide OWNER.TABLA, UNTIL TIME y nombre nuevo como obligatorios', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()
    escribir('Modo', 'tabla')

    for (const etiqueta of ['Tabla', 'UNTIL TIME', 'Nombre nuevo']) {
      expect((screen.getByLabelText(etiqueta) as HTMLInputElement).required).toBe(true)
    }
    expect(screen.queryByLabelText('UNTIL TIME (opcional)')).toBeNull()
  })

  it('con estado distinto de Completo advierte el estado', async () => {
    simular(respuesta(200, {}), { ...RMAN, estado: 'Incompleto' })
    await abrirFormulario()

    expect(screen.getByText(/Incompleto/, { selector: 'p.aviso' })).not.toBeNull()
  })

  it('la pregunta de la base completa avisa de que apaga la base y cierra la sesión', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))

    expect(screen.getByRole('group').textContent).toMatch(/apaga la base.*cierra la sesión/)
    expect(posts()).toHaveLength(0)
  })

  it('al cancelar no se envía nada', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(posts()).toHaveLength(0)
    expect(fetchFalso).toHaveBeenCalledTimes(1)
  })

  it('base completa sin UNTIL TIME envía solo modo full', async () => {
    simular(respuesta(200, { mensaje: 'Recuperado', log: 'RMAN ok', advertencia: null }))
    await abrirFormulario()
    confirmar()

    await screen.findByRole('status')
    expect(posts()).toHaveLength(1)
    const [, opciones] = posts()[0]
    expect(opciones.headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(JSON.parse(opciones.body)).toEqual({ modo: 'full' })
  })

  it('base completa con UNTIL TIME lo envía como hasta', async () => {
    simular(respuesta(200, { mensaje: 'Recuperado', log: 'RMAN ok', advertencia: null }))
    await abrirFormulario()
    escribir('UNTIL TIME (opcional)', '2025-01-02 04:00:00')
    confirmar()

    await screen.findByRole('status')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ modo: 'full', hasta: '2025-01-02 04:00:00' })
  })

  it('tabla envía tabla, hasta y nuevo_nombre y muestra el log sin pedir cerrar la sesión', async () => {
    simular(respuesta(200, { mensaje: 'Recuperado', log: 'RECOVER TABLE terminó', advertencia: null }))
    await abrirFormulario()
    elegirTabla()
    fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))
    expect(screen.getByRole('group').textContent).not.toMatch(/apaga la base/)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    expect((await screen.findByRole('status')).textContent).toContain('Recuperado')
    expect(screen.getByText('RECOVER TABLE terminó')).not.toBeNull()
    expect(screen.queryByText(/Inicia sesión de nuevo/)).toBeNull()
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      modo: 'tabla',
      tabla: 'HR.EMPLEADOS',
      hasta: '2025-01-02 04:00:00',
      nuevo_nombre: 'EMPLEADOS_RECUPERADA',
    })
  })

  it('muestra «Recuperando...» mientras corre', async () => {
    let terminar: (r: unknown) => void = () => {}
    const pendiente = new Promise((resolver) => {
      terminar = resolver
    })
    simular(pendiente)
    await abrirFormulario()
    confirmar()

    expect(await screen.findByText('Recuperando...')).not.toBeNull()
    terminar(respuesta(200, { mensaje: 'Recuperado', log: 'ok', advertencia: null }))
    await waitFor(() => expect(screen.queryByText('Recuperando...')).toBeNull())
  })

  it('tras un full con sesion_cerrada muestra el log y el aviso de iniciar sesión sin borrar la sesión local', async () => {
    const expirar = vi.spyOn(sesion, 'expirarSesion')
    simular(respuesta(200, { mensaje: 'Recuperado', log: 'RMAN terminó', advertencia: null, sesion_cerrada: true }))
    await abrirFormulario()
    confirmar()

    const exito = await screen.findByRole('status')
    expect(exito.textContent).toContain('Recuperado')
    expect(exito.textContent).toContain('La sesión se cerró. Inicia sesión de nuevo')
    expect(screen.getByText('RMAN terminó')).not.toBeNull()
    expect(expirar).not.toHaveBeenCalled()
  })

  it('la siguiente petición con la sesión cerrada recibe 401 y abre el login', async () => {
    const expirar = vi.spyOn(sesion, 'expirarSesion').mockImplementation(() => {})
    simular(respuesta(200, { mensaje: 'Recuperado', log: 'ok', advertencia: null, sesion_cerrada: true }))
    await abrirFormulario()
    confirmar()
    await screen.findByRole('status')

    simular(respuesta(401, { detail: 'Sesión no válida' }))
    confirmar()

    await waitFor(() => expect(expirar).toHaveBeenCalledTimes(1))
  })

  it('403 muestra «Se requiere sesión SYSDBA»', async () => {
    simular(respuesta(403, { detail: 'Se requiere sesión SYSDBA' }))
    await abrirFormulario()
    confirmar()

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA')
  })

  it('422 muestra los errores de validación', async () => {
    simular(respuesta(422, { errores: ['La fecha UNTIL TIME no puede ser futura'] }))
    await abrirFormulario()
    escribir('UNTIL TIME (opcional)', '2999-01-01 00:00:00')
    confirmar()

    expect((await screen.findByRole('alert')).textContent).toContain('La fecha UNTIL TIME no puede ser futura')
  })

  it('500 muestra el mensaje, la explicación y el log sin ocultar el código', async () => {
    simular(
      respuesta(500, {
        mensaje: 'No se pudo recuperar el respaldo',
        explicacion: 'RMAN-06054: falta un archive log',
        log: 'RMAN-06054: media recovery requesting unknown archived log',
      }),
    )
    await abrirFormulario()
    confirmar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('No se pudo recuperar el respaldo')
    expect(alerta.textContent).toContain('RMAN-06054: falta un archive log')
    expect(alerta.textContent).toContain('RMAN-06054: media recovery requesting unknown archived log')
  })

  it('409 sin ARCHIVELOG muestra el aviso y el botón «Activar ARCHIVELOG»', async () => {
    simular(
      respuesta(409, {
        mensaje: 'La base de datos no está en ARCHIVELOG: actívalo para poder respaldar',
        explicacion: 'RMAN-06149: la base no está en ARCHIVELOG',
      }),
    )
    await abrirFormulario()
    expect(screen.queryByRole('button', { name: 'Activar ARCHIVELOG' })).toBeNull()
    confirmar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('La base de datos no está en ARCHIVELOG')
    expect(alerta.textContent).toContain('RMAN-06149')
    expect(screen.getByRole('button', { name: 'Activar ARCHIVELOG' })).not.toBeNull()
  })

  it('«Activar ARCHIVELOG» pide confirmar con el texto de RespaldoFull y llama a POST /respaldos/full/archivelog', async () => {
    simular(
      respuesta(409, { mensaje: 'La base de datos no está en ARCHIVELOG', explicacion: 'RMAN-06149' }),
      RMAN,
      respuesta(200, { mensaje: 'ARCHIVELOG activado. Inicia sesión de nuevo', log: 'log de archivelog' }),
    )
    await abrirFormulario()
    confirmar()
    fireEvent.click(await screen.findByRole('button', { name: 'Activar ARCHIVELOG' }))

    expect(screen.getByRole('group', { name: CONFIRMACION_ARCHIVELOG })).not.toBeNull()
    const llamadas = () => fetchFalso.mock.calls.filter(([url]) => url === '/respaldos/full/archivelog')
    expect(llamadas()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(screen.getByText('log de archivelog')).not.toBeNull())
    expect(llamadas()).toHaveLength(1)
    expect(llamadas()[0][1].method).toBe('POST')
    expect(llamadas()[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(screen.getByRole('status').textContent).toContain('ARCHIVELOG activado. Inicia sesión de nuevo')
    expect(screen.queryByRole('button', { name: 'Activar ARCHIVELOG' })).toBeNull()
  })

  it('un error al activar ARCHIVELOG muestra su explicación y el log', async () => {
    simular(
      respuesta(409, { mensaje: 'La base de datos no está en ARCHIVELOG', explicacion: 'RMAN-06149' }),
      RMAN,
      respuesta(500, { mensaje: 'No se pudo activar ARCHIVELOG', explicacion: 'ORA-00205: error al abrir el control file', log: 'ORA-00205' }),
    )
    await abrirFormulario()
    confirmar()
    fireEvent.click(await screen.findByRole('button', { name: 'Activar ARCHIVELOG' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('ORA-00205: error al abrir el control file'))
    expect(screen.getByRole('alert').textContent).toContain('No se pudo activar ARCHIVELOG')
  })
})
