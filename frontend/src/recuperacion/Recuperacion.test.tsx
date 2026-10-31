import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { Recuperacion } from './Recuperacion'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const RECIENTE = {
  directorio: 'RESPALDOS',
  ruta: '/opt/oracle/respaldos',
  base: 'hr_20250102_030405',
  tipo: 'Data Pump',
  estado: 'Completo',
  archivos: [{ nombre: 'hr_20250102_030405.dmp', tamano: 2048 }],
  tamano: 2048,
  fecha: '2025-01-02T03:04:05',
}
const ANTIGUO = {
  directorio: 'DATA_PUMP_DIR',
  ruta: '/opt/oracle/admin/dpdump',
  base: 'full_20240101_000000',
  tipo: 'RMAN',
  estado: 'Con errores',
  archivos: [{ nombre: 'full_20240101_000000_XE_1_1.dbf', tamano: 4096 }],
  tamano: 4096,
  fecha: '2024-01-01T00:00:00',
}

let fetchFalso: ReturnType<typeof vi.fn>

const simular = (respuesta: unknown) => {
  fetchFalso = vi.fn(async () => respuesta)
  vi.stubGlobal('fetch', fetchFalso)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('vista Recuperación', () => {
  it('pide GET /directorios/respaldos con el token y lista respaldo, tipo, estado, directorio y fecha', async () => {
    simular(ok({ respaldos: [RECIENTE, ANTIGUO], avisos: [] }))
    render(<Recuperacion token={TOKEN} />)

    expect(await screen.findByText('hr_20250102_030405')).not.toBeNull()
    expect(fetchFalso.mock.calls[0][0]).toBe('/directorios/respaldos')
    expect(fetchFalso.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    for (const texto of ['Data Pump', 'Completo', 'RESPALDOS', 'full_20240101_000000', 'RMAN', 'Con errores', 'DATA_PUMP_DIR']) {
      expect(screen.getByText(texto)).not.toBeNull()
    }
    expect(screen.getByText(new Date(RECIENTE.fecha).toLocaleString('es'))).not.toBeNull()
  })

  it('ofrece un botón «Recuperar» por cada respaldo', async () => {
    simular(ok({ respaldos: [RECIENTE, ANTIGUO], avisos: [] }))
    render(<Recuperacion token={TOKEN} />)

    await screen.findByText('hr_20250102_030405')
    expect(screen.getAllByRole('button', { name: /^Recuperar/ })).toHaveLength(2)
  })

  it('sin respaldos muestra el mensaje de vacío', async () => {
    simular(ok({ respaldos: [], avisos: [] }))
    render(<Recuperacion token={TOKEN} />)

    expect(await screen.findByText('No hay respaldos para mostrar')).not.toBeNull()
  })

  it('ante 403 muestra el aviso de error', async () => {
    simular({ ok: false, status: 403, json: async () => ({ detail: 'Se requiere sesión SYSDBA o rol DBA' }) })
    render(<Recuperacion token={TOKEN} />)

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA o rol DBA')
  })
})
