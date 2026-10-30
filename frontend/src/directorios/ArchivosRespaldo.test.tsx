import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

describe('eliminar un respaldo', () => {
  const URL_BORRAR = '/directorios/RESPALDOS/respaldos/hr_20250102_030405'
  const listados = () => fetchFalso.mock.calls.filter(([, o]) => o.method === undefined)
  const borrados = () => fetchFalso.mock.calls.filter(([, o]) => o.method === 'DELETE')

  // La primera lista trae ambos respaldos; las recargas, solo el antiguo.
  const simularBorrado = (respuestaDelete: unknown) => {
    let lecturas = 0
    fetchFalso = vi.fn(async (_url: string, opciones: { method?: string }) => {
      if (opciones.method === 'DELETE') return respuestaDelete
      lecturas++
      return ok({ respaldos: lecturas === 1 ? [RECIENTE, ANTIGUO] : [ANTIGUO], avisos: [] })
    })
    vi.stubGlobal('fetch', fetchFalso)
  }

  const pedirEliminar = async () => {
    render(<ArchivosRespaldo token={TOKEN} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar hr_20250102_030405' }))
  }
  const confirmar = () => fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

  it('pide confirmación nombrando el respaldo y avisando de que se borran sus archivos y su log', async () => {
    simularBorrado(ok({ mensaje: 'Respaldo hr_20250102_030405 eliminado', advertencia: null }))
    await pedirEliminar()

    const pregunta = screen.getByRole('group').getAttribute('aria-label') ?? ''
    expect(pregunta).toContain('hr_20250102_030405')
    expect(pregunta).toMatch(/archivos/)
    expect(pregunta).toMatch(/log/)
    expect(borrados()).toHaveLength(0)
  })

  it('al confirmar envía DELETE con el directorio y la base codificados, muestra el éxito y recarga la lista', async () => {
    simularBorrado(ok({ mensaje: 'Respaldo hr_20250102_030405 eliminado', advertencia: null }))
    await pedirEliminar()
    confirmar()

    expect(await screen.findByText('Respaldo hr_20250102_030405 eliminado')).not.toBeNull()
    expect(borrados()).toHaveLength(1)
    expect(borrados()[0][0]).toBe(URL_BORRAR)
    expect(borrados()[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(listados()).toHaveLength(2)
    expect(screen.queryByText('hr_20250102_030405')).toBeNull()
    expect(screen.getByText('full_20240101_000000')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('codifica con encodeURIComponent el directorio y la base', async () => {
    const raro = { ...RECIENTE, directorio: 'DIR/ESP ECIAL', base: 'a b_20250102_030405' }
    fetchFalso = vi.fn(async () => ok({ respaldos: [raro], avisos: [] }))
    vi.stubGlobal('fetch', fetchFalso)
    render(<ArchivosRespaldo token={TOKEN} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar a b_20250102_030405' }))
    confirmar()

    await waitFor(() => expect(borrados()).toHaveLength(1))
    expect(borrados()[0][0]).toBe('/directorios/DIR%2FESP%20ECIAL/respaldos/a%20b_20250102_030405')
  })

  it('al cancelar no envía ninguna petición ni cambia la lista', async () => {
    simularBorrado(ok({ mensaje: 'Respaldo hr_20250102_030405 eliminado', advertencia: null }))
    await pedirEliminar()
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(borrados()).toHaveLength(0)
    expect(fetchFalso).toHaveBeenCalledTimes(1)
    expect(screen.getByText('hr_20250102_030405')).not.toBeNull()
    expect(screen.getByText('full_20240101_000000')).not.toBeNull()
  })

  it('muestra la advertencia de RMAN con su explicación y su log junto al éxito', async () => {
    simularBorrado(
      ok({
        mensaje: 'Respaldo hr_20250102_030405 eliminado',
        advertencia: { explicacion: 'No se pudo limpiar el catálogo de RMAN', log: 'RMAN-06004: fallo' },
      }),
    )
    await pedirEliminar()
    confirmar()

    expect(await screen.findByText('Respaldo hr_20250102_030405 eliminado')).not.toBeNull()
    expect(screen.getByText('No se pudo limpiar el catálogo de RMAN')).not.toBeNull()
    expect(screen.getByText('RMAN-06004: fallo')).not.toBeNull()
    expect(listados()).toHaveLength(2)
  })

  it.each([
    [404, { detail: 'Respaldo no encontrado' }, 'Respaldo no encontrado', undefined],
    [422, { errores: ['Nombre de respaldo no válido'] }, 'Nombre de respaldo no válido', undefined],
    [
      500,
      { mensaje: 'No se pudo eliminar el respaldo', explicacion: 'El archivo está en uso', error: 'rm: sin permiso' },
      'No se pudo eliminar el respaldo',
      'rm: sin permiso',
    ],
  ])('ante %i muestra el aviso devuelto y recarga la lista', async (status, cuerpo, texto, detalle) => {
    simularBorrado({ ok: false, status, json: async () => cuerpo })
    await pedirEliminar()
    confirmar()

    expect((await screen.findByRole('alert')).textContent).toContain(texto)
    if (detalle) expect(screen.getByText(detalle)).not.toBeNull()
    if (status === 500) expect(screen.getByText('El archivo está en uso')).not.toBeNull()
    await waitFor(() => expect(listados()).toHaveLength(2))
    expect(screen.queryByText('hr_20250102_030405')).toBeNull()
    expect(screen.queryByText(/eliminado/)).toBeNull()
  })
})
