import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
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
