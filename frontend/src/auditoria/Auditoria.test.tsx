import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { Auditoria } from './Auditoria'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (opciones?.method === 'POST') return ok({ mensaje: 'Política AUD_EMP creada y habilitada' })
    if (url === '/auditoria/estado') return ok({ modo: 'Modo mixto (unificada y tradicional)', audit_trail: 'DB' })
    if (url === '/auditoria/politicas')
      return ok({
        politicas: [
          { nombre: 'AUD_EMP', acciones: ['DELETE'], objetos: ['HR.EMPLOYEES'], habilitada: false, predefinida: false },
          { nombre: 'ORA_LOGON_FAILURES', acciones: ['LOGON'], objetos: [], habilitada: true, predefinida: true },
        ],
      })
    if (url === '/auditoria/tablas') return ok({ tablas: [{ schema: 'HR', tabla: 'EMPLOYEES' }] })
    if (url.startsWith('/auditoria/registros'))
      return ok({
        registros: [
          {
            fecha: '24/10/2026 10:00:00',
            usuario: 'HR',
            accion: 'DELETE',
            schema: 'HR',
            objeto: 'EMPLOYEES',
            codigo_retorno: 0,
            politicas: 'AUD_EMP',
            sql: 'delete from employees where employee_id = 1',
          },
        ],
      })
    return ok({})
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const posts = () => fetchFalso.mock.calls.filter(([, o]) => o?.method === 'POST')

describe('pantalla de auditoría', () => {
  it('muestra el modo, las políticas propias y oculta las predefinidas', async () => {
    render(<Auditoria token={TOKEN} />)

    const politicas = await screen.findByRole('table', { name: 'Políticas de auditoría' })
    expect(within(politicas).getByText('AUD_EMP')).not.toBeNull()
    expect(within(politicas).queryByText('ORA_LOGON_FAILURES')).toBeNull()
    expect(screen.getByText('Modo mixto (unificada y tradicional)')).not.toBeNull()

    fireEvent.click(screen.getByLabelText(/predefinidas de Oracle/))
    expect(within(politicas).getByText('ORA_LOGON_FAILURES')).not.toBeNull()
  })

  it('muestra los registros de auditoría', async () => {
    render(<Auditoria token={TOKEN} />)

    const registros = await screen.findByRole('table', { name: 'Registros de auditoría' })
    expect(within(registros).getByText('Correcto')).not.toBeNull()
  })

  it('crea una política sobre una tabla con las acciones elegidas', async () => {
    render(<Auditoria token={TOKEN} />)
    await screen.findByRole('option', { name: 'HR.EMPLOYEES' })

    fireEvent.change(screen.getByLabelText('Nombre de la política'), { target: { value: 'aud_emp' } })
    fireEvent.change(screen.getByLabelText('Tabla'), { target: { value: 'HR.EMPLOYEES' } })
    fireEvent.click(screen.getByLabelText('DELETE'))
    fireEvent.click(screen.getByLabelText('UPDATE'))
    fireEvent.click(screen.getByRole('button', { name: 'Crear política' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/auditoria/politicas')
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      nombre: 'aud_emp',
      tipo: 'tabla',
      acciones: ['DELETE', 'UPDATE'],
      schema_tabla: 'HR',
      tabla: 'EMPLOYEES',
      habilitar: true,
    })
    expect((await screen.findByRole('status')).textContent).toContain('AUD_EMP')
  })

  it('eliminar una política pide confirmación', async () => {
    render(<Auditoria token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar' }))
    expect(posts()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/auditoria/politicas/AUD_EMP/eliminar')
  })
})
