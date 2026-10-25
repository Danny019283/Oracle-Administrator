import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Performance } from './Performance'

const CREDENCIALES = { usuario: 'SYSTEM', password: 's3creta!', servicio: 'XEPDB1' }

const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const RESUMEN = {
  instancia: {
    nombre: 'XE',
    host: 'srv',
    version: '21.3.0.0.0',
    estado: 'OPEN',
    inicio: '20/10/2026 08:00:00',
    base_datos: 'XE',
    modo_log: 'ARCHIVELOG',
    modo_apertura: 'READ WRITE',
  },
  memoria: { sga: [{ nombre: 'Fixed Size', mb: 9.4 }], sga_total_mb: 9.4, pga: [] },
  indicadores: { buffer_cache_hit: 99.1, library_cache_hit: 97.5, sesiones_total: 3, sesiones_activas: 1 },
}

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (url === '/performance/resumen') return ok(RESUMEN)
    if (url === '/performance/sesiones')
      return ok({
        sesiones: [
          {
            sid: 25,
            serial: 101,
            usuario: 'HR',
            estado: 'ACTIVE',
            usuario_so: 'emijo',
            maquina: 'PC',
            programa: 'sqlplus.exe',
            conexion: '24/10/2026 10:00:00',
            sql_id: null,
          },
        ],
      })
    if (url.startsWith('/performance/consultas')) return ok({ consultas: [] })
    if (url === '/performance/esperas') return ok({ esperas: [] })
    if (url === '/performance/sesiones/terminar' && opciones?.method === 'POST')
      return ok({ mensaje: 'Sesión 25,101 terminada' })
    return ok({})
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('pantalla de performance', () => {
  it('muestra el estado de la instancia y los indicadores', async () => {
    render(<Performance credenciales={CREDENCIALES} />)

    expect(await screen.findByText('99.1 %')).not.toBeNull()
    expect(screen.getByText('ARCHIVELOG')).not.toBeNull()
    expect(screen.getByRole('table', { name: 'SGA' })).not.toBeNull()
  })

  it('envía las credenciales en las cabeceras', async () => {
    render(<Performance credenciales={CREDENCIALES} />)
    await screen.findByText('99.1 %')

    const [, opciones] = fetchFalso.mock.calls[0]
    expect(opciones.headers['X-Oracle-User']).toBe('SYSTEM')
  })

  it('terminar una sesión pide confirmación antes de llamar al backend', async () => {
    render(<Performance credenciales={CREDENCIALES} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Terminar' }))
    const llamadasTerminar = () =>
      fetchFalso.mock.calls.filter(([url]) => url === '/performance/sesiones/terminar')
    expect(llamadasTerminar()).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(llamadasTerminar()).toHaveLength(1))
    expect(JSON.parse(llamadasTerminar()[0][1].body)).toEqual({ sid: 25, serial: 101, confirmar: true })
    expect((await screen.findByRole('status')).textContent).toContain('Sesión 25,101 terminada')
  })

  it('si Oracle rechaza muestra la explicación y el código', async () => {
    fetchFalso.mockImplementation(async () => ({
      ok: false,
      status: 500,
      json: async () => ({
        mensaje: 'Oracle rechazó la operación',
        explicacion: 'El usuario conectado no tiene privilegios suficientes',
        error: 'ORA-01031: privilegios insuficientes',
      }),
    }))

    render(<Performance credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('privilegios suficientes')
    expect(alerta.textContent).toContain('ORA-01031')
  })

  it('avisa cuando el backend no responde', async () => {
    fetchFalso.mockImplementation(async () => {
      throw new TypeError('Failed to fetch')
    })

    render(<Performance credenciales={CREDENCIALES} />)

    expect((await screen.findByRole('alert')).textContent).toContain('backend esté en ejecución')
  })
})
