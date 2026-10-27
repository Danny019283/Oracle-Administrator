import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { cerrarSesion, expirarSesion, iniciarSesion } from './sesion/sesion'

const OK = { token: 'tok-123', usuario: 'HR', sysdba: false }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>
let sesionDevuelta = OK

const DATOS = { host: 'db.local', puerto: '1522', servicio: 'XEPDB1', usuario: 'HR', password: 's3creta!', sysdba: false }

beforeEach(async () => {
  localStorage.clear()
  sesionDevuelta = OK
  fetchFalso = vi.fn(async (url: string, opciones?: { method?: string }) => {
    if (url === '/sesion') {
      return opciones?.method === 'DELETE' ? respuesta(null, 204) : respuesta(sesionDevuelta)
    }
    if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES'] })
    return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
  })
  vi.stubGlobal('fetch', fetchFalso)
  await cerrarSesion()
})

afterEach(() => {
  expirarSesion()
  cleanup()
  vi.unstubAllGlobals()
})

const barra = () => within(screen.getByRole('banner'))
const boton = (nombre: string) => screen.queryByRole('button', { name: nombre })

function iniciarDesdeElModal() {
  const valores = { Host: 'db.local', Puerto: '1522', Servicio: 'XEPDB1', Usuario: 'HR', Contraseña: 's3creta!' }
  for (const [nombre, valor] of Object.entries(valores)) {
    fireEvent.change(screen.getByLabelText(nombre), { target: { value: valor } })
  }
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
}

describe('sin sesión', () => {
  it('muestra el modal de inicio de sesión sobre la aplicación', () => {
    render(<App />)

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
  })

  it('deja la aplicación inerte detrás del modal', () => {
    const { container } = render(<App />)

    expect(container.querySelector('.app')!.hasAttribute('inert')).toBe(true)
  })

  it('la top bar no ofrece cerrar sesión ni muestra usuario', () => {
    render(<App />)

    expect(barra().queryByRole('button', { name: 'Cerrar sesión' })).toBeNull()
    expect(barra().queryByText('HR')).toBeNull()
  })

  it('no hace ninguna petición a /respaldos', () => {
    render(<App />)

    expect(fetchFalso.mock.calls.filter(([url]) => String(url).startsWith('/respaldos'))).toEqual([])
  })
})

describe('al iniciar sesión desde el modal', () => {
  it('cierra el modal y deja la aplicación accesible', async () => {
    const { container } = render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(container.querySelector('.app')!.hasAttribute('inert')).toBe(false)
    expect(boton('Creación de respaldos')).not.toBeNull()
  })

  it('guarda host, puerto, servicio y usuario, y nunca la contraseña', async () => {
    render(<App />)

    iniciarDesdeElModal()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    const guardado = localStorage.getItem('oracle.conexion')!
    expect(JSON.parse(guardado)).toEqual({ host: 'db.local', puerto: '1522', servicio: 'XEPDB1', usuario: 'HR' })
    expect(guardado).not.toContain('s3creta!')
  })

  it('la top bar muestra el usuario y «Cerrar sesión», sin etiqueta SYSDBA', async () => {
    render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(barra().queryByText('HR')).not.toBeNull())
    expect(barra().getByRole('button', { name: 'Cerrar sesión' })).not.toBeNull()
    expect(barra().queryByText('SYSDBA')).toBeNull()
  })

  it('con una sesión SYSDBA la top bar lo indica', async () => {
    sesionDevuelta = { token: 'tok-sys', usuario: 'SYS', sysdba: true }
    render(<App />)

    iniciarDesdeElModal()

    await waitFor(() => expect(barra().queryByText('SYS')).not.toBeNull())
    expect(barra().getByText('SYSDBA')).not.toBeNull()
  })
})

describe('con la sesión ya iniciada al abrir', () => {
  beforeEach(async () => {
    await iniciarSesion(DATOS)
  })

  it('no muestra el modal y la top bar tiene usuario y «Cerrar sesión»', () => {
    render(<App />)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(barra().getByText('HR')).not.toBeNull()
    expect(barra().getByRole('button', { name: 'Cerrar sesión' })).not.toBeNull()
  })

  it('las pantallas de respaldo usan el token de la sesión', async () => {
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    const llamadas = fetchFalso.mock.calls.filter(([url]) => String(url).startsWith('/respaldos'))
    expect(llamadas.length).toBeGreaterThan(0)
    for (const [, opciones] of llamadas) {
      expect(opciones.headers.Authorization).toBe('Bearer tok-123')
    }
  })

  it('si la sesión expira vuelve el modal y la aplicación regresa al menú principal', async () => {
    render(<App />)
    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    act(() => expirarSesion())

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'CLIENTES' })).toBeNull()
    expect(barra().queryByText('HR')).toBeNull()
  })

  it('tras volver a iniciar sesión la aplicación empieza en el menú principal', async () => {
    render(<App />)
    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })
    act(() => expirarSesion())

    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(boton('Creación de respaldos')).not.toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'CLIENTES' })).toBeNull()
  })

  it('si la sesión se cierra vuelve el modal', async () => {
    render(<App />)

    await act(() => cerrarSesion())

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
  })
})

describe('cerrar sesión desde la top bar', () => {
  beforeEach(async () => {
    await iniciarSesion(DATOS)
  })

  it('llama a DELETE /sesion con el token y vuelve al modal', async () => {
    render(<App />)

    fireEvent.click(barra().getByRole('button', { name: 'Cerrar sesión' }))

    await screen.findByRole('dialog', { name: 'Iniciar sesión' })
    const borrado = fetchFalso.mock.calls.find(([url, o]) => url === '/sesion' && o?.method === 'DELETE')
    expect(borrado).toBeDefined()
    expect(borrado![1].headers).toEqual({ Authorization: 'Bearer tok-123' })
  })

  it('la top bar deja de mostrar usuario y «Cerrar sesión»', async () => {
    render(<App />)

    fireEvent.click(barra().getByRole('button', { name: 'Cerrar sesión' }))

    await screen.findByRole('dialog')
    expect(barra().queryByText('HR')).toBeNull()
    expect(barra().queryByRole('button', { name: 'Cerrar sesión' })).toBeNull()
  })

  it('el modal vuelve con la contraseña vacía y los datos de conexión recordados', async () => {
    render(<App />)

    fireEvent.click(barra().getByRole('button', { name: 'Cerrar sesión' }))

    await screen.findByRole('dialog')
    expect((screen.getByLabelText('Contraseña') as HTMLInputElement).value).toBe('')
    expect((screen.getByLabelText('Host') as HTMLInputElement).value).toBe('db.local')
    expect((screen.getByLabelText('Usuario') as HTMLInputElement).value).toBe('HR')
  })

  it('cerrar la sesión por voluntad propia no muestra «Sesión expirada»', async () => {
    render(<App />)

    fireEvent.click(barra().getByRole('button', { name: 'Cerrar sesión' }))

    await screen.findByRole('dialog')
    expect(screen.queryByText(/Sesión expirada/)).toBeNull()
  })

  it('tras cerrar, la app empieza en el menú principal al volver a entrar', async () => {
    render(<App />)
    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)
    await screen.findByRole('checkbox', { name: 'CLIENTES' })

    fireEvent.click(barra().getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByRole('dialog')
    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(boton('Creación de respaldos')).not.toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'CLIENTES' })).toBeNull()
  })
})

describe('sesión expirada', () => {
  beforeEach(async () => {
    await iniciarSesion(DATOS)
  })

  it('un 401 en una pantalla de respaldo vuelve al modal con el aviso «Sesión expirada»', async () => {
    fetchFalso.mockImplementation(async (url: string) =>
      String(url).startsWith('/respaldos') ? respuesta({ detail: 'Sesión no válida o expirada' }, 401) : respuesta(OK),
    )
    render(<App />)

    fireEvent.click(boton('Creación de respaldos')!)
    fireEvent.click(boton('Tablas')!)

    await screen.findByRole('dialog', { name: 'Iniciar sesión' })
    expect(screen.getByRole('status').textContent).toContain('Sesión expirada')
  })

  it.each([
    ['Performance de la base de datos', '/performance'],
    ['Auditoría de la BD', '/auditoria'],
    ['Seguridad de usuarios', '/seguridad'],
  ])('un 401 en «%s» vuelve al modal con «Sesión expirada» y sin el error de la pantalla', async (modulo, prefijo) => {
    fetchFalso.mockImplementation(async (url: string) =>
      String(url).startsWith(prefijo) ? respuesta({ detail: 'Sesión no válida o expirada' }, 401) : respuesta(OK),
    )
    render(<App />)

    fireEvent.click(boton(modulo)!)

    await screen.findByRole('dialog', { name: 'Iniciar sesión' })
    expect(screen.getByRole('status').textContent).toContain('Sesión expirada')
    expect(screen.queryByRole('heading', { name: modulo, level: 1 })).toBeNull()
    expect(screen.queryByText('Sesión no válida o expirada')).toBeNull()
  })

  it('al expirar por inactividad el modal muestra el aviso y conserva los datos recordados', () => {
    render(<App />)

    act(() => expirarSesion())

    expect(screen.getByRole('status').textContent).toContain('Sesión expirada')
    expect((screen.getByLabelText('Host') as HTMLInputElement).value).toBe('db.local')
    expect((screen.getByLabelText('Contraseña') as HTMLInputElement).value).toBe('')
  })

  it('al iniciar sesión de nuevo el aviso desaparece', async () => {
    render(<App />)
    act(() => expirarSesion())

    iniciarDesdeElModal()

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.queryByText(/Sesión expirada/)).toBeNull()
  })

  it('una expiración posterior a un cierre voluntario vuelve a mostrar el aviso', async () => {
    render(<App />)
    await act(() => cerrarSesion())
    iniciarDesdeElModal()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    act(() => expirarSesion())

    expect(screen.getByRole('status').textContent).toContain('Sesión expirada')
  })

  it('un fallo de login con el aviso visible muestra además el error del servidor', async () => {
    render(<App />)
    act(() => expirarSesion())
    fetchFalso.mockImplementation(async () =>
      respuesta({ mensaje: 'Usuario o contraseña de Oracle incorrectos (ORA-01017)', codigo: 'ORA-01017' }, 401),
    )

    iniciarDesdeElModal()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('ORA-01017')
    expect(screen.getByRole('status').textContent).toContain('Sesión expirada')
  })

  it('sin sesión previa el modal inicial no muestra el aviso', async () => {
    await cerrarSesion()
    render(<App />)

    expect(screen.queryByText(/Sesión expirada/)).toBeNull()
  })
})
