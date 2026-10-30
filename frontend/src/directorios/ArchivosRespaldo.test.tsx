import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ArchivosRespaldo } from './ArchivosRespaldo'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const RECIENTE = {
  directorio: 'RESPALDOS',
  ruta: '/opt/oracle/respaldos',
  base: 'hr_20250102_030405',
  tipo: 'Data Pump',
  estado: 'Completo',
  archivos: [
    { nombre: 'hr_20250102_030405.dmp', tamano: 2 * 1024 * 1024 },
    { nombre: 'hr_20250102_030405.log', tamano: 512 },
  ],
  tamano: 2 * 1024 * 1024 + 512,
  fecha: '2025-01-02T03:04:05',
}
const ANTIGUO = {
  directorio: 'DATA_PUMP_DIR',
  ruta: '/opt/oracle/admin/dpdump',
  base: 'full_20240101_000000',
  tipo: 'RMAN',
  estado: 'Con errores',
  archivos: [{ nombre: 'full_20240101_000000_XE_1_1.dbf', tamano: 3 * 1024 ** 3 }],
  tamano: 3 * 1024 ** 3,
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

describe('sección Respaldos', () => {
  it('pide GET /directorios/respaldos con el token y muestra los campos de cada respaldo', async () => {
    simular(ok({ respaldos: [RECIENTE, ANTIGUO], avisos: [] }))
    render(<ArchivosRespaldo token={TOKEN} />)

    expect(await screen.findByText('hr_20250102_030405')).not.toBeNull()
    expect(fetchFalso.mock.calls[0][0]).toBe('/directorios/respaldos')
    expect(fetchFalso.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    for (const texto of ['Data Pump', 'Completo', 'RESPALDOS', '/opt/oracle/respaldos', '2.0 MB', 'RMAN', 'Con errores']) {
      expect(screen.getByText(texto)).not.toBeNull()
    }
    expect(screen.getByText('DATA_PUMP_DIR')).not.toBeNull()
    expect(screen.getByText('/opt/oracle/admin/dpdump')).not.toBeNull()
    expect(screen.getByText('3.0 GB')).not.toBeNull()
    expect(screen.getByText(/hr_20250102_030405\.dmp/)).not.toBeNull()
  })

  it('muestra los respaldos en el orden recibido, el más reciente primero', async () => {
    simular(ok({ respaldos: [RECIENTE, ANTIGUO], avisos: [] }))
    render(<ArchivosRespaldo token={TOKEN} />)

    await screen.findByText('hr_20250102_030405')
    const filas = screen.getAllByRole('row').slice(1)
    expect(filas[0].textContent).toContain('hr_20250102_030405')
    expect(filas[1].textContent).toContain('full_20240101_000000')
  })

  it('formatea la fecha ISO de forma legible', async () => {
    simular(ok({ respaldos: [RECIENTE], avisos: [] }))
    render(<ArchivosRespaldo token={TOKEN} />)

    await screen.findByText('hr_20250102_030405')
    expect(screen.queryByText('2025-01-02T03:04:05')).toBeNull()
    expect(screen.getByRole('table').textContent).toMatch(/2025/)
  })

  it('con la lista vacía muestra la tabla vacía sin aviso de error', async () => {
    simular(ok({ respaldos: [], avisos: [] }))
    render(<ArchivosRespaldo token={TOKEN} />)

    expect(await screen.findByText('No hay respaldos para mostrar')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('muestra cada aviso de los directorios ilegibles junto a los respaldos', async () => {
    simular(ok({ respaldos: [RECIENTE], avisos: ['No se pudo leer el directorio X', 'No se pudo leer el directorio Y'] }))
    render(<ArchivosRespaldo token={TOKEN} />)

    expect(await screen.findByText('hr_20250102_030405')).not.toBeNull()
    expect(screen.getByText('No se pudo leer el directorio X')).not.toBeNull()
    expect(screen.getByText('No se pudo leer el directorio Y')).not.toBeNull()
  })

  it('ante 403 muestra el aviso de error', async () => {
    simular({ ok: false, status: 403, json: async () => ({ detail: 'Se requiere sesión SYSDBA o rol DBA' }) })
    render(<ArchivosRespaldo token={TOKEN} />)

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA o rol DBA')
  })
})
