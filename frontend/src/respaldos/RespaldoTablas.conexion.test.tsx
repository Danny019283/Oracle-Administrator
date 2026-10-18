import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RespaldoTablas } from './RespaldoTablas'

const CREDENCIALES = { usuario: 'HR', password: 's3creta!', servicio: 'XEPDB1' }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

// El proxy de Vite responde 502/503/504 con un cuerpo que no es JSON.
const respuestaDelProxy = (status: number) => ({
  ok: false,
  status,
  json: async () => {
    throw new SyntaxError('Unexpected token < in JSON')
  },
})

const MENSAJE = 'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('backend que no responde', () => {
  it('sin respuesta alguna muestra el mensaje y el código ERR_CONEXION', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    render(<RespaldoTablas credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE)
    expect(alerta.textContent).toContain('ERR_CONEXION')
  })

  it.each([502, 503, 504])('si el proxy responde %i muestra ese código', async (codigo) => {
    vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(codigo)))
    render(<RespaldoTablas credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain(MENSAJE)
    expect(alerta.textContent).toContain(String(codigo))
    expect(alerta.textContent).not.toContain('ERR_CONEXION')
  })

  it('el aviso es uno solo aunque fallen la carga de tablas y la de directorios', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    render(<RespaldoTablas credenciales={CREDENCIALES} />)

    const alerta = await screen.findByRole('alert')

    expect(alerta.querySelectorAll('p')).toHaveLength(1)
  })

  it('si cae al respaldar muestra el mensaje y el código y no da por creado el respaldo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, opciones?: { method?: string }) => {
        if (opciones?.method === 'POST') return Promise.reject(new TypeError('Failed to fetch'))
        if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES'] })
        return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
      }),
    )
    render(<RespaldoTablas credenciales={CREDENCIALES} />)
    await screen.findByRole('option', { name: /RESPALDO/ })

    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(MENSAJE)
    expect(alerta.textContent).toContain('ERR_CONEXION')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('si el proxy responde 504 al respaldar muestra ese código', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, opciones?: { method?: string }) => {
        if (opciones?.method === 'POST') return respuestaDelProxy(504)
        if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES'] })
        return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
      }),
    )
    render(<RespaldoTablas credenciales={CREDENCIALES} />)
    await screen.findByRole('option', { name: /RESPALDO/ })

    fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(MENSAJE)
    expect(alerta.textContent).toContain('504')
  })
})
