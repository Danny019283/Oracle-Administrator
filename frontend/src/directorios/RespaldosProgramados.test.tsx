import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { RespaldosProgramados } from './RespaldosProgramados'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const BASE = {
  id: 1,
  nombre: 'nocturno',
  politica: 'FULL',
  frecuencia: 'DIARIO',
  hora: '23:00',
  dia: null,
  intervalo_horas: null,
  directorio: 'RESPALDOS',
  ruta_script: '/opt/oracle/respaldos/scripts_programados/nocturno.sh',
  ruta_rman: '/opt/oracle/respaldos/scripts_programados/nocturno.rman',
  entorno: 'contenedor',
  tarea: 'oracle-admin:1',
  creado: '2025-01-01T00:00:00',
  ultima_ejecucion: null,
  ultimo_resultado: null,
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

describe('sección Respaldos programados', () => {
  it('pide GET /respaldos/programados con el token y muestra el panel y los campos de la fila', async () => {
    simular(
      ok({
        programaciones: [
          { ...BASE, ultima_ejecucion: '2025-01-02T03:04:05', ultimo_resultado: 'Completo' },
        ],
      }),
    )
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText('nocturno')).not.toBeNull()
    expect(fetchFalso.mock.calls[0][0]).toBe('/respaldos/programados')
    expect(fetchFalso.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(screen.getByRole('heading', { name: 'Respaldos programados' })).not.toBeNull()
    const cabeceras = screen.getAllByRole('columnheader').map((c) => c.textContent)
    expect(cabeceras).toEqual([
      'Nombre',
      'Política',
      'Frecuencia',
      'Directorio',
      'Script',
      'Última ejecución',
      'Último resultado',
    ])
    for (const texto of [
      'Full',
      'Diario a las 23:00',
      'RESPALDOS',
      '/opt/oracle/respaldos/scripts_programados/nocturno.sh',
      new Date('2025-01-02T03:04:05').toLocaleString('es'),
      'Completo',
    ]) {
      expect(screen.getByText(texto)).not.toBeNull()
    }
  })

  it('muestra «Nunca» y «—» si nunca se ejecutó', async () => {
    simular(ok({ programaciones: [BASE] }))
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText('Nunca')).not.toBeNull()
    expect(screen.getByText('—')).not.toBeNull()
  })

  it('muestra «Con errores» y los nombres legibles de cada política', async () => {
    simular(
      ok({
        programaciones: [
          { ...BASE, id: 1, nombre: 'a', politica: 'INCREMENTAL', ultimo_resultado: 'Con errores' },
          { ...BASE, id: 2, nombre: 'b', politica: 'TRANSACCIONAL', frecuencia: 'HORAS', hora: null, intervalo_horas: 2 },
        ],
      }),
    )
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText('Incremental')).not.toBeNull()
    expect(screen.getByText('Transaccional')).not.toBeNull()
    expect(screen.getByText('Con errores')).not.toBeNull()
    expect(screen.queryByText('INCREMENTAL')).toBeNull()
  })

  it.each([
    [{ frecuencia: 'DIARIO', hora: '23:00', dia: null, intervalo_horas: null }, 'Diario a las 23:00'],
    [{ frecuencia: 'SEMANAL', hora: '23:00', dia: 0, intervalo_horas: null }, 'Semanal: domingo a las 23:00'],
    [{ frecuencia: 'SEMANAL', hora: '08:30', dia: 3, intervalo_horas: null }, 'Semanal: miércoles a las 08:30'],
    [{ frecuencia: 'MENSUAL', hora: '23:00', dia: 1, intervalo_horas: null }, 'Mensual: día 1 a las 23:00'],
    [{ frecuencia: 'HORAS', hora: null, dia: null, intervalo_horas: 2 }, 'Cada 2 horas'],
  ])('formatea la frecuencia %j como «%s»', async (cambios, texto) => {
    simular(ok({ programaciones: [{ ...BASE, ...cambios }] }))
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText(texto)).not.toBeNull()
  })

  it('con la lista vacía muestra «No hay respaldos programados» sin aviso de error', async () => {
    simular(ok({ programaciones: [] }))
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText('No hay respaldos programados')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('ante 403 muestra el aviso de sesión SYSDBA y la tabla queda vacía', async () => {
    simular({ ok: false, status: 403, json: async () => ({ detail: 'Se requiere sesión SYSDBA' }) })
    render(<RespaldosProgramados token={TOKEN} />)

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA')
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('ante un error 500 muestra el mensaje del backend', async () => {
    simular({ ok: false, status: 500, json: async () => ({ mensaje: 'No se pudo listar', explicacion: 'Oracle no responde' }) })
    render(<RespaldosProgramados token={TOKEN} />)

    const alerta = (await screen.findByRole('alert')).textContent
    expect(alerta).toContain('No se pudo listar')
    expect(alerta).toContain('Oracle no responde')
    expect(screen.queryByRole('table')).toBeNull()
  })
})
