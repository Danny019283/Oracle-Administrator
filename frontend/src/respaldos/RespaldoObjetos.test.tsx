import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RespaldoObjetos, type TipoObjeto } from './RespaldoObjetos'

const CREDENCIALES = { usuario: 'HR', password: 's3creta!', servicio: 'XEPDB1' }
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

describe.each([
  [TABLAS, 'tablas'],
  [SCHEMAS, 'schemas'],
])('pantalla común de respaldo (%#)', (tipo, recurso) => {
  it('muestra el título, la descripción y el encabezado del tipo', async () => {
    render(<RespaldoObjetos credenciales={CREDENCIALES} tipo={tipo} />)
    await screen.findByRole('checkbox', { name: 'UNO' })

    expect(screen.getByRole('heading', { name: tipo.titulo })).not.toBeNull()
    expect(screen.getByRole('heading', { name: tipo.encabezadoLista })).not.toBeNull()
    expect(screen.getByText(tipo.descripcion)).not.toBeNull()
    expect(screen.getByRole('checkbox', { name: tipo.seleccionarTodos })).not.toBeNull()
  })

  it('lista los objetos de /respaldos/<recurso>', async () => {
    render(<RespaldoObjetos credenciales={CREDENCIALES} tipo={tipo} />)

    expect(await screen.findByRole('checkbox', { name: 'DOS' })).not.toBeNull()
    expect(fetchFalso.mock.calls.map(([url]) => url)).toContain(`/respaldos/${recurso}`)
  })

  it('envía la selección en el campo con el nombre del recurso', async () => {
    render(<RespaldoObjetos credenciales={CREDENCIALES} tipo={tipo} />)
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
