import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Directorios } from './Directorios'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const RESPALDOS = { nombre: 'RESPALDOS', ruta: '/opt/oracle/respaldos' }
const DATA_PUMP = { nombre: 'DATA_PUMP_DIR', ruta: '/opt/oracle/admin/dpdump' }

let fetchFalso: ReturnType<typeof vi.fn>

const simular = (respuesta: unknown) => {
  fetchFalso = vi.fn(async () => respuesta)
  vi.stubGlobal('fetch', fetchFalso)
}

beforeEach(() => {
  simular(ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos'] }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('pantalla de directorios', () => {
  it('muestra el nombre y la ruta de cada directorio', async () => {
    render(<Directorios token={TOKEN} />)

    expect(await screen.findByText('RESPALDOS')).not.toBeNull()
    expect(screen.getByText('/opt/oracle/respaldos')).not.toBeNull()
    expect(screen.getByText('DATA_PUMP_DIR')).not.toBeNull()
    expect(screen.getByText('/opt/oracle/admin/dpdump')).not.toBeNull()
    expect(fetchFalso.mock.calls[0][0]).toBe('/directorios')
  })

  it('muestra el botón de crear', async () => {
    render(<Directorios token={TOKEN} />)

    await screen.findByText('RESPALDOS')
    expect(screen.getByRole('button', { name: 'Crear directorio' })).not.toBeNull()
  })

  it('con la lista vacía no muestra aviso de error y sí el botón de crear', async () => {
    simular(ok({ directorios: [], ejemplos_ruta: ['/opt/oracle/respaldos'] }))
    render(<Directorios token={TOKEN} />)

    expect(await screen.findByText('No hay directorios para mostrar')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: 'Crear directorio' })).not.toBeNull()
  })

  it('ante un error del servidor muestra el aviso', async () => {
    simular({ ok: false, status: 500, json: async () => ({ mensaje: 'No se pudo listar los directorios' }) })
    render(<Directorios token={TOKEN} />)

    expect((await screen.findByRole('alert')).textContent).toContain('No se pudo listar los directorios')
  })
})

describe('crear directorio', () => {
  const abrirFormulario = async () => {
    render(<Directorios token={TOKEN} />)
    await screen.findByText('RESPALDOS')
    fireEvent.click(screen.getByRole('button', { name: 'Crear directorio' }))
  }

  const rellenarYEnviar = async () => {
    fireEvent.change(await screen.findByLabelText('Nombre del directorio'), { target: { value: 'nuevo' } })
    fireEvent.change(screen.getByLabelText('Ruta de la carpeta'), { target: { value: '/opt/oracle/nuevo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear' }))
  }

  const respuestas = (...siguientes: unknown[]) => {
    const cola = [...siguientes]
    fetchFalso = vi.fn(async () => cola.shift())
    vi.stubGlobal('fetch', fetchFalso)
  }

  const lista = ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos', 'C:\\respaldos'] })
  const fallo = (status: number, cuerpo: unknown) => ({ ok: false, status, json: async () => cuerpo })

  it('el formulario pide nombre y ruta y muestra los ejemplos de ruta del servidor', async () => {
    respuestas(lista)
    await abrirFormulario()

    expect(await screen.findByLabelText('Nombre del directorio')).not.toBeNull()
    expect(screen.getByLabelText('Ruta de la carpeta')).not.toBeNull()
    expect(screen.getByText(/\/opt\/oracle\/respaldos/)).not.toBeNull()
    expect(screen.getByText(/C:\\respaldos/)).not.toBeNull()
  })

  it('al confirmar envía POST /directorios con nombre y ruta', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), lista)
    await abrirFormulario()
    await rellenarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    const [url, opciones] = fetchFalso.mock.calls[1]
    expect(url).toBe('/directorios')
    expect(opciones.method).toBe('POST')
    expect(JSON.parse(opciones.body)).toEqual({ nombre: 'nuevo', ruta: '/opt/oracle/nuevo' })
  })

  it('si se crea informa «Directorio X creado» y recarga la lista', async () => {
    const NUEVO = { nombre: 'NUEVO', ruta: '/opt/oracle/nuevo' }
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), ok({ directorios: [NUEVO], ejemplos_ruta: [] }))
    await abrirFormulario()
    await rellenarYEnviar()

    expect((await screen.findByRole('status')).textContent).toContain('Directorio NUEVO creado')
    expect(await screen.findByText('/opt/oracle/nuevo')).not.toBeNull()
    expect(fetchFalso).toHaveBeenCalledTimes(3)
    expect(fetchFalso.mock.calls[2][0]).toBe('/directorios')
  })

  it('ante 422 muestra los errores y no recarga la lista', async () => {
    respuestas(lista, fallo(422, { errores: ['La ruta debe ser absoluta'] }))
    await abrirFormulario()
    await rellenarYEnviar()

    expect((await screen.findByRole('alert')).textContent).toContain('La ruta debe ser absoluta')
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })

  it('ante 500 muestra el mensaje, la explicación y el error y no recarga la lista', async () => {
    respuestas(
      lista,
      fallo(500, { mensaje: 'No se pudieron dar permisos', explicacion: 'La carpeta debe existir', error: 'chown: sin permiso' }),
    )
    await abrirFormulario()
    await rellenarYEnviar()

    const alerta = (await screen.findByRole('alert')).textContent
    expect(alerta).toContain('No se pudieron dar permisos')
    expect(alerta).toContain('La carpeta debe existir')
    expect(alerta).toContain('chown: sin permiso')
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })
})
