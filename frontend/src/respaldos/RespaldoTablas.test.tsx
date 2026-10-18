import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RespaldoTablas } from './RespaldoTablas'

const TOKEN = 'tok-123'
const CABECERAS = { Authorization: `Bearer ${TOKEN}` }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string) => {
    if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES', 'PEDIDOS'] })
    if (url === '/respaldos/directorios') {
      return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
    }
    throw new Error(`URL inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const pantalla = () => render(<RespaldoTablas token={TOKEN} />)
const casilla = (nombre: string) => screen.getByRole('checkbox', { name: nombre }) as HTMLInputElement

describe('pantalla de respaldo de tablas', () => {
  it('lista las tablas del usuario con una casilla por tabla', async () => {
    pantalla()

    expect(await screen.findByRole('checkbox', { name: 'CLIENTES' })).not.toBeNull()
    expect(screen.getByRole('checkbox', { name: 'PEDIDOS' })).not.toBeNull()
  })

  it('consulta tablas y directorios enviando las credenciales en las cabeceras', async () => {
    pantalla()
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    const llamadas = fetchFalso.mock.calls.map(([url, opciones]) => [url, opciones?.headers])
    expect(llamadas).toContainEqual(['/respaldos/tablas', CABECERAS])
    expect(llamadas).toContainEqual(['/respaldos/directorios', CABECERAS])
  })

  it('«Seleccionar todas» marca y desmarca todas las tablas', async () => {
    pantalla()
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    fireEvent.click(casilla('Seleccionar todas'))
    expect(casilla('CLIENTES').checked).toBe(true)
    expect(casilla('PEDIDOS').checked).toBe(true)

    fireEvent.click(casilla('Seleccionar todas'))
    expect(casilla('CLIENTES').checked).toBe(false)
    expect(casilla('PEDIDOS').checked).toBe(false)
  })

  it('permite elegir un DIRECTORY de los disponibles', async () => {
    pantalla()

    const selector = (await screen.findByLabelText('Directorio')) as HTMLSelectElement
    await screen.findByRole('option', { name: /RESPALDO/ })
    fireEvent.change(selector, { target: { value: 'RESPALDO' } })

    expect(selector.value).toBe('RESPALDO')
  })

  it('al respaldar envía las tablas marcadas, el DIRECTORY y el nombre del dumpfile', async () => {
    pantalla()
    await screen.findByRole('checkbox', { name: 'CLIENTES' })
    await screen.findByRole('option', { name: /RESPALDO/ })

    fireEvent.click(casilla('PEDIDOS'))
    fireEvent.change(screen.getByLabelText('Directorio'), { target: { value: 'RESPALDO' } })
    fireEvent.change(screen.getByLabelText('Nombre del dumpfile'), { target: { value: 'ventas' } })
    fetchFalso.mockClear()
    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe('/respaldos/tablas')
    expect(opciones.method).toBe('POST')
    expect(opciones.headers).toMatchObject(CABECERAS)
    expect(JSON.parse(opciones.body)).toEqual({
      tablas: ['PEDIDOS'],
      directorio: 'RESPALDO',
      nombre: 'ventas',
    })
  })
})
