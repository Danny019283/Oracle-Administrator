import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Recuperacion } from './Recuperacion'

const TOKEN = 'tok-123'
const DUMP = {
  directorio: 'RESPALDOS',
  ruta: '/opt/oracle/respaldos',
  base: 'hr_20250102_030405',
  tipo: 'Data Pump',
  estado: 'Completo',
  archivos: [{ nombre: 'hr_20250102_030405.dmp', tamano: 2048 }],
  tamano: 2048,
  fecha: '2025-01-02T03:04:05',
}
const URL_RECUPERAR = '/directorios/RESPALDOS/respaldos/hr_20250102_030405/recuperar'

const respuesta = (status: number, cuerpo: unknown) => ({ ok: status < 400, status, json: async () => cuerpo })

let fetchFalso: ReturnType<typeof vi.fn>

const simular = (post: unknown, respaldo = DUMP) => {
  fetchFalso = vi.fn(async (_url: string, opciones?: RequestInit) =>
    opciones?.method === 'POST' ? post : respuesta(200, { respaldos: [respaldo], avisos: [] }),
  )
  vi.stubGlobal('fetch', fetchFalso)
}

const posts = () => fetchFalso.mock.calls.filter(([, o]) => o?.method === 'POST')

const abrirFormulario = async () => {
  render(<Recuperacion token={TOKEN} />)
  fireEvent.click(await screen.findByRole('button', { name: /^Recuperar/ }))
}

const escribirObjetos = (texto: string) =>
  fireEvent.change(screen.getByLabelText('Objetos'), { target: { value: texto } })

const confirmar = () => {
  fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))
  fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Recuperar un respaldo Data Pump', () => {
  it('no muestra el formulario hasta pulsar «Recuperar»', async () => {
    simular(respuesta(200, {}))
    render(<Recuperacion token={TOKEN} />)
    await screen.findByText(DUMP.base)

    expect(screen.queryByLabelText('Objetos')).toBeNull()
  })

  it('muestra el formulario con modo Tablas, objetos y «Omitir» por defecto', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()

    const modo = screen.getByLabelText('Modo') as HTMLSelectElement
    expect(Array.from(modo.options).map((o) => o.text)).toEqual(['Tablas', 'Schemas'])
    expect(modo.value).toBe('tablas')
    expect(screen.getByLabelText('Objetos')).not.toBeNull()
    const existentes = screen.getByLabelText('Tablas existentes') as HTMLSelectElement
    expect(Array.from(existentes.options).map((o) => o.text)).toEqual([
      'Omitir',
      'Agregar',
      'Vaciar y cargar',
      'Reemplazar',
    ])
    expect(existentes.selectedOptions[0].text).toBe('Omitir')
  })

  it('con estado distinto de Completo advierte el estado; con Completo no', async () => {
    simular(respuesta(200, {}), { ...DUMP, estado: 'Con errores' })
    await abrirFormulario()
    expect(screen.getByText(/Con errores/, { selector: 'p.aviso' })).not.toBeNull()
    cleanup()

    simular(respuesta(200, {}))
    await abrirFormulario()
    expect(document.querySelector('p.aviso')).toBeNull()
  })

  it('la pregunta de confirmación avisa de que Vaciar y Reemplazar sobrescriben datos', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()
    escribirObjetos('HR.EMPLEADOS')
    fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))

    expect(screen.getByRole('group').textContent).toMatch(/Vaciar y Reemplazar sobrescriben/)
    expect(posts()).toHaveLength(0)
  })

  it('al cancelar no se envía nada', async () => {
    simular(respuesta(200, {}))
    await abrirFormulario()
    escribirObjetos('HR.EMPLEADOS')
    fireEvent.click(screen.getByRole('button', { name: 'Ejecutar recuperación' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(posts()).toHaveLength(0)
    expect(fetchFalso).toHaveBeenCalledTimes(1)
    expect(screen.getByText(DUMP.base)).not.toBeNull()
  })

  it('al confirmar envía POST con modo datapump, tablas, objetos y la acción elegida y muestra el log', async () => {
    simular(respuesta(200, { mensaje: 'Recuperación completada', log: 'Import terminó sin errores', advertencia: null }))
    await abrirFormulario()
    escribirObjetos('HR.EMPLEADOS\nHR.DEPARTAMENTOS, HR.PAISES')
    fireEvent.change(screen.getByLabelText('Tablas existentes'), { target: { value: 'TRUNCATE' } })
    confirmar()

    expect((await screen.findByRole('status')).textContent).toContain('Recuperación completada')
    expect(screen.getByText('Import terminó sin errores')).not.toBeNull()
    expect(posts()).toHaveLength(1)
    const [url, opciones] = posts()[0]
    expect(url).toBe(URL_RECUPERAR)
    expect(opciones.headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(JSON.parse(opciones.body)).toEqual({
      modo: 'datapump',
      objeto_modo: 'tablas',
      objetos: ['HR.EMPLEADOS', 'HR.DEPARTAMENTOS', 'HR.PAISES'],
      existentes: 'TRUNCATE',
    })
  })

  it('en modo Schemas envía objeto_modo schemas y SKIP por defecto', async () => {
    simular(respuesta(200, { mensaje: 'Recuperación completada', log: 'ok', advertencia: null }))
    await abrirFormulario()
    fireEvent.change(screen.getByLabelText('Modo'), { target: { value: 'schemas' } })
    escribirObjetos('HR')
    confirmar()

    await screen.findByRole('status')
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      modo: 'datapump',
      objeto_modo: 'schemas',
      objetos: ['HR'],
      existentes: 'SKIP',
    })
  })

  it('muestra «Recuperando...» mientras corre', async () => {
    let terminar: (r: unknown) => void = () => {}
    const pendiente = new Promise((resolver) => {
      terminar = resolver
    })
    fetchFalso = vi.fn(async (_url: string, opciones?: RequestInit) =>
      opciones?.method === 'POST' ? pendiente : respuesta(200, { respaldos: [DUMP], avisos: [] }),
    )
    vi.stubGlobal('fetch', fetchFalso)
    await abrirFormulario()
    escribirObjetos('HR.EMPLEADOS')
    confirmar()

    expect(await screen.findByText('Recuperando...')).not.toBeNull()
    terminar(respuesta(200, { mensaje: 'Recuperación completada', log: 'ok', advertencia: null }))
    await waitFor(() => expect(screen.queryByText('Recuperando...')).toBeNull())
  })

  it('muestra la advertencia de estado que devuelve la respuesta', async () => {
    simular(respuesta(200, { mensaje: 'Recuperación completada', log: 'ok', advertencia: 'El respaldo tiene estado «Con errores»' }))
    await abrirFormulario()
    escribirObjetos('HR')
    confirmar()

    expect(await screen.findByText(/El respaldo tiene estado «Con errores»/)).not.toBeNull()
  })

  it('422 muestra los errores de validación', async () => {
    simular(respuesta(422, { errores: ['Indica al menos un objeto'] }))
    await abrirFormulario()
    confirmar()

    expect((await screen.findByRole('alert')).textContent).toContain('Indica al menos un objeto')
  })

  it('404 muestra el detalle', async () => {
    simular(respuesta(404, { detail: 'El respaldo no existe' }))
    await abrirFormulario()
    escribirObjetos('HR')
    confirmar()

    expect((await screen.findByRole('alert')).textContent).toContain('El respaldo no existe')
  })

  it('500 muestra el mensaje, la explicación y el log sin ocultar el código', async () => {
    simular(
      respuesta(500, {
        mensaje: 'No se pudo recuperar el respaldo',
        explicacion: 'ORA-39151: la tabla ya existe y se omitió',
        log: 'ORA-39151: Table "HR"."EMPLEADOS" exists',
      }),
    )
    await abrirFormulario()
    escribirObjetos('HR.EMPLEADOS')
    confirmar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('No se pudo recuperar el respaldo')
    expect(alerta.textContent).toContain('ORA-39151: la tabla ya existe y se omitió')
    expect(alerta.textContent).toContain('ORA-39151: Table "HR"."EMPLEADOS" exists')
  })
})
