import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Seguridad } from './Seguridad'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const HR = { usuario: 'HR', estado: 'OPEN', tablespace: 'USERS', temporal: 'TEMP', perfil: 'DEFAULT', creado: '01/10/2026' }

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (opciones?.method === 'POST') {
      if (url === '/seguridad/usuarios')
        return { ok: false, status: 422, json: async () => ({ errores: ['Debes ingresar una contraseña'] }) }
      return ok({ mensaje: 'Usuario HR bloqueado' })
    }
    if (url === '/seguridad/usuarios') return ok({ usuarios: [HR] })
    if (url === '/seguridad/catalogos')
      return ok({ tablespaces: ['USERS'], temporales: ['TEMP'], roles: ['CONNECT', 'RESOURCE'], privilegios: ['CREATE TABLE'] })
    if (url === '/seguridad/usuarios/HR')
      return ok({ ...HR, roles: [{ nombre: 'CONNECT', admin: false }], privilegios: [], cuotas: [] })
    return ok({})
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const posts = () => fetchFalso.mock.calls.filter(([, o]) => o?.method === 'POST')

describe('pantalla de seguridad de usuarios', () => {
  it('lista los usuarios con su estado', async () => {
    render(<Seguridad token={TOKEN} />)

    expect(await screen.findByText('HR')).not.toBeNull()
    expect(screen.getByText('OPEN')).not.toBeNull()
  })

  it('abre el detalle del usuario con sus roles y permite bloquearlo', async () => {
    render(<Seguridad token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Administrar HR' }))
    expect(await screen.findByRole('heading', { name: 'Usuario HR' })).not.toBeNull()
    expect(await screen.findByRole('button', { name: 'Revocar CONNECT' })).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Bloquear' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/seguridad/usuarios/HR/bloquear')
  })

  it('eliminar un usuario pide confirmación', async () => {
    render(<Seguridad token={TOKEN} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Administrar HR' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar usuario' }))
    expect(posts()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/seguridad/usuarios/HR/eliminar')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ confirmar: true })
  })

  it('al crear un usuario muestra los errores de validación', async () => {
    render(<Seguridad token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Crear usuario' }))
    await screen.findByRole('option', { name: 'USERS' })
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'ventas' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Crear usuario' }).at(-1)!)

    expect((await screen.findByRole('alert')).textContent).toContain('Debes ingresar una contraseña')
  })
})
