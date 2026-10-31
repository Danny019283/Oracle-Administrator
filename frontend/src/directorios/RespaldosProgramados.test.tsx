import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
      'Acciones',
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

describe('pulido de la columna Frecuencia', () => {
  it.each([
    [{ frecuencia: 'DIARIO', hora: null }, 'Diario a las —'],
    [{ frecuencia: 'SEMANAL', hora: '08:30', dia: null }, 'Semanal: — a las 08:30'],
    [{ frecuencia: 'SEMANAL', hora: '08:30', dia: 9 }, 'Semanal: — a las 08:30'],
    [{ frecuencia: 'SEMANAL', hora: null, dia: 2 }, 'Semanal: martes a las —'],
    [{ frecuencia: 'MENSUAL', hora: '23:00', dia: null }, 'Mensual: día — a las 23:00'],
    [{ frecuencia: 'HORAS', hora: null, dia: null, intervalo_horas: null }, 'Cada — horas'],
    [{ frecuencia: 'HORAS', hora: null, dia: null, intervalo_horas: 1 }, 'Cada 1 hora'],
  ])('formatea %j como «%s»', async (cambios, texto) => {
    simular(ok({ programaciones: [{ ...BASE, ...cambios }] }))
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByText(texto)).not.toBeNull()
    expect(document.body.textContent).not.toMatch(/null|undefined/)
  })
})

describe('botón Ejecutar', () => {
  const FILAS = [
    { ...BASE, id: 1, nombre: 'nocturno' },
    { ...BASE, id: 2, nombre: 'semanal' },
  ]
  const LISTA = ok({ programaciones: FILAS })
  const ACTUALIZADA = ok({
    programaciones: [
      { ...FILAS[0], ultima_ejecucion: '2025-02-03T04:05:06', ultimo_resultado: 'Completo' },
      FILAS[1],
    ],
  })

  // GET devuelve las listas en orden; el POST lo resuelve la prueba (puede quedar pendiente).
  const prepararEjecucion = (alPost: () => Promise<unknown>, listas: unknown[] = [LISTA, ACTUALIZADA]) => {
    let get = 0
    fetchFalso = vi.fn(async (_url: string, opciones?: RequestInit) =>
      opciones?.method === 'POST' ? alPost() : listas[Math.min(get++, listas.length - 1)],
    )
    vi.stubGlobal('fetch', fetchFalso)
  }
  const posts = () => fetchFalso.mock.calls.filter((c) => c[1]?.method === 'POST')
  const gets = () => fetchFalso.mock.calls.filter((c) => c[1]?.method !== 'POST')

  it('añade la columna Acciones y un botón «Ejecutar <nombre>» por fila', async () => {
    simular(LISTA)
    render(<RespaldosProgramados token={TOKEN} />)

    expect(await screen.findByRole('button', { name: 'Ejecutar nocturno' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Ejecutar semanal' })).not.toBeNull()
    expect(screen.getAllByRole('columnheader').map((c) => c.textContent)).toContain('Acciones')
  })

  it('envía POST /respaldos/programados/<id>/ejecutar con el token y sin pedir confirmación', async () => {
    prepararEjecucion(async () => ok({ mensaje: 'Respaldo ejecutado', resultado: 'Completo', log: 'ok' }))
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar semanal' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/respaldos/programados/2/ejecutar')
    expect(posts()[0][1].headers.Authorization).toBe(`Bearer ${TOKEN}`)
    expect(screen.queryByRole('group')).toBeNull()
  })

  it('mientras corre muestra «Ejecutando…» y deshabilita todos los botones Ejecutar', async () => {
    let liberar: (v: unknown) => void = () => {}
    prepararEjecucion(() => new Promise((r) => (liberar = r)))
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect(await screen.findByText('Ejecutando…')).not.toBeNull()
    const botones = screen.getAllByRole('button', { name: /^Ejecutar / })
    expect(botones).toHaveLength(2)
    for (const b of botones) expect((b as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(botones[1])
    expect(posts()).toHaveLength(1)

    liberar(ok({ mensaje: 'Respaldo ejecutado', resultado: 'Completo', log: 'fin' }))
    await waitFor(() => expect(screen.queryByText('Ejecutando…')).toBeNull())
    for (const b of screen.getAllByRole('button', { name: /^Ejecutar / })) {
      expect((b as HTMLButtonElement).disabled).toBe(false)
    }
  })

  it('en éxito muestra «Respaldo ejecutado» con el log y recarga la lista', async () => {
    prepararEjecucion(async () =>
      ok({ mensaje: 'Respaldo ejecutado', resultado: 'Completo', log: 'Recovery Manager completado' }),
    )
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect((await screen.findByRole('status')).textContent).toContain('Respaldo ejecutado')
    expect(screen.getByText('Recovery Manager completado')).not.toBeNull()
    expect(await screen.findByText('Completo')).not.toBeNull()
    expect(screen.getByText(new Date('2025-02-03T04:05:06').toLocaleString('es'))).not.toBeNull()
    expect(gets()).toHaveLength(2)
    expect(gets()[1][0]).toBe('/respaldos/programados')
  })

  it('ante 404 muestra el detalle y recarga la lista', async () => {
    prepararEjecucion(async () => ({ ok: false, status: 404, json: async () => ({ detail: 'La programación 1 no existe' }) }))
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect((await screen.findByRole('alert')).textContent).toContain('La programación 1 no existe')
    await waitFor(() => expect(gets()).toHaveLength(2))
  })

  it('ante 409 muestra el mensaje con la sugerencia «Reinstalar tareas»', async () => {
    const texto = 'El script de la programación ya no existe en disco; usa «Reinstalar tareas»'
    prepararEjecucion(async () => ({ ok: false, status: 409, json: async () => ({ mensaje: texto, detail: texto }) }))
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect((await screen.findByRole('alert')).textContent).toContain('«Reinstalar tareas»')
    expect(screen.queryByText('Ejecutando…')).toBeNull()
  })

  it('ante 500 de RMAN muestra mensaje, explicación y log, y recarga la lista', async () => {
    prepararEjecucion(
      async () => ({
        ok: false,
        status: 500,
        json: async () => ({
          mensaje: 'No se pudo ejecutar el respaldo programado',
          explicacion: 'RMAN terminó con errores',
          log: 'RMAN-03009: failure of backup command',
        }),
      }),
      [LISTA, ok({ programaciones: [{ ...FILAS[0], ultimo_resultado: 'Con errores' }, FILAS[1]] })],
    )
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    const alerta = (await screen.findByRole('alert')).textContent
    expect(alerta).toContain('No se pudo ejecutar el respaldo programado')
    expect(alerta).toContain('RMAN terminó con errores')
    expect(alerta).toContain('RMAN-03009: failure of backup command')
    expect(await screen.findByText('Con errores')).not.toBeNull()
    expect(gets()).toHaveLength(2)
  })

  it('ante 403 muestra el aviso de sesión SYSDBA', async () => {
    prepararEjecucion(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Se requiere sesión SYSDBA' }) }))
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect((await screen.findByRole('alert')).textContent).toContain('Se requiere sesión SYSDBA')
  })

  it('con el backend caído muestra el aviso de conexión', async () => {
    let get = 0
    fetchFalso = vi.fn(async (_url: string, opciones?: RequestInit) => {
      if (opciones?.method === 'POST') throw new TypeError('Failed to fetch')
      get++
      return LISTA
    })
    vi.stubGlobal('fetch', fetchFalso)
    render(<RespaldosProgramados token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Ejecutar nocturno' }))

    expect((await screen.findByRole('alert')).textContent).toContain('No se pudo conectar con el servidor')
    expect(get).toBeGreaterThan(0)
    expect(screen.queryByText('Ejecutando…')).toBeNull()
  })
})

