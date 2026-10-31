import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { EstadoBase } from './EstadoBase'

const respuesta = (cuerpo: unknown, status = 200) => ({ ok: status < 400, status, json: async () => cuerpo })

let estado: string
let fetchFalso: ReturnType<typeof vi.fn>
let resolverPost: (r: ReturnType<typeof respuesta>) => void
let respuestaPost: ReturnType<typeof respuesta> | null

beforeEach(() => {
  estado = 'ABIERTA'
  respuestaPost = respuesta({ mensaje: 'La acción APAGAR se ejecutó correctamente', log: 'Database closed.' })
  fetchFalso = vi.fn(async (_url: string, opciones?: { method?: string }) => {
    if (opciones?.method === 'POST') {
      return respuestaPost ?? new Promise((resolver) => (resolverPost = resolver))
    }
    return respuesta({ estado })
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })
const posts = () => fetchFalso.mock.calls.filter(([, o]) => o?.method === 'POST')

const ACCIONES = ['NOMOUNT', 'MOUNT', 'APAGAR', 'ENCENDER']
const VALIDAS: Record<string, string[]> = {
  APAGADA: ['NOMOUNT', 'MOUNT', 'ENCENDER'],
  NOMOUNT: ['MOUNT', 'APAGAR', 'ENCENDER'],
  MOUNT: ['APAGAR', 'ENCENDER'],
  ABIERTA: ['APAGAR'],
}

describe('control de estado de la base', () => {
  it.each(Object.entries(VALIDAS))('en %s muestra el estado y solo las acciones válidas', async (estadoActual, validas) => {
    estado = estadoActual
    render(<EstadoBase />)

    await screen.findByText(estadoActual)

    expect(fetchFalso).toHaveBeenCalledWith('/base/estado')
    for (const accion of ACCIONES) expect(boton(accion) !== null).toBe(validas.includes(accion))
  })

  it('consulta el estado sin enviar credenciales de sesión', async () => {
    render(<EstadoBase />)
    await screen.findByText('ABIERTA')

    expect(fetchFalso.mock.calls[0]).toEqual(['/base/estado'])
  })

  it('al cancelar la confirmación no envía nada', async () => {
    render(<EstadoBase />)
    fireEvent.click(await screen.findByRole('button', { name: 'APAGAR' }))

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(posts()).toEqual([])
    expect(boton('APAGAR')).not.toBeNull()
  })

  it('APAGAR avisa de que corta la app y cierra las sesiones antes de enviar', async () => {
    render(<EstadoBase />)
    fireEvent.click(await screen.findByRole('button', { name: 'APAGAR' }))

    const grupo = screen.getByRole('group')
    expect(grupo.textContent).toMatch(/corta la app/)
    expect(grupo.textContent).toMatch(/sesiones/)
    expect(posts()).toEqual([])
  })

  it('al confirmar envía la acción, muestra «Cambiando estado...» y luego el resultado con el log', async () => {
    respuestaPost = null
    render(<EstadoBase />)
    fireEvent.click(await screen.findByRole('button', { name: 'APAGAR' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await screen.findByText('Cambiando estado...')
    const [url, opciones] = posts()[0]
    expect(url).toBe('/base/estado')
    expect(JSON.parse(opciones.body)).toEqual({ accion: 'APAGAR' })

    estado = 'APAGADA'
    resolverPost(respuesta({ mensaje: 'La acción APAGAR se ejecutó correctamente', log: 'Database closed.' }))

    await screen.findByText('La acción APAGAR se ejecutó correctamente')
    expect(screen.getByText('Database closed.')).not.toBeNull()
    expect(screen.queryByText('Cambiando estado...')).toBeNull()
    await screen.findByText('APAGADA')
  })

  it('muestra el error 500 con su explicación y su log', async () => {
    respuestaPost = respuesta(
      { mensaje: 'No se pudo cambiar el estado de la base', explicacion: 'El usuario no tiene el privilegio necesario', log: 'ORA-01031: insufficient privileges' },
      500,
    )
    render(<EstadoBase />)
    fireEvent.click(await screen.findByRole('button', { name: 'APAGAR' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('No se pudo cambiar el estado de la base')
    expect(alerta.textContent).toContain('El usuario no tiene el privilegio necesario')
    expect(alerta.textContent).toContain('ORA-01031: insufficient privileges')
  })

  it('muestra el aviso del 409 cuando la acción ya no es válida', async () => {
    respuestaPost = respuesta({ detail: 'La acción APAGAR no es válida con la base en estado APAGADA' }, 409)
    render(<EstadoBase />)
    fireEvent.click(await screen.findByRole('button', { name: 'APAGAR' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain('La acción APAGAR no es válida con la base en estado APAGADA'),
    )
  })

  it('si no puede consultar el estado muestra el error y no ofrece acciones', async () => {
    fetchFalso.mockImplementation(async () =>
      respuesta({ mensaje: 'No se pudo consultar el estado de la base', log: 'ORA-01031: insufficient privileges' }, 500),
    )
    render(<EstadoBase />)

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('No se pudo consultar el estado de la base')
    for (const accion of ACCIONES) expect(boton(accion)).toBeNull()
  })
})
