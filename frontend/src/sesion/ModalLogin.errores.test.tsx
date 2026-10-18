import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ModalLogin } from './ModalLogin'

const PASSWORD = 's3creta!'

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

const AVISO_CONEXION = 'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución'

const campo = (nombre: string) => screen.getByLabelText(nombre) as HTMLInputElement

function completarYEnviar({ sysdba = false } = {}) {
  const valores = { Host: 'db.local', Puerto: '1522', Servicio: 'XEPDB1', Usuario: 'HR', Contraseña: PASSWORD }
  for (const [nombre, valor] of Object.entries(valores)) {
    fireEvent.change(campo(nombre), { target: { value: valor } })
  }
  if (sysdba) fireEvent.click(screen.getByRole('checkbox', { name: 'Iniciar como SYSDBA' }))
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
}

const fallarCon = (cuerpo: unknown, status: number) => {
  vi.stubGlobal('fetch', vi.fn(async () => respuesta(cuerpo, status)))
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('fallos que devuelve la API', () => {
  it.each([
    ['credenciales inválidas', 401, 'Usuario o contraseña de Oracle incorrectos (ORA-01017)', 'ORA-01017'],
    ['falta de privilegio SYSDBA', 401, 'El usuario no tiene el privilegio necesario (¿SYSDBA?) (ORA-01031)', 'ORA-01031'],
    ['cuenta bloqueada', 401, 'La cuenta de Oracle está bloqueada (ORA-28000)', 'ORA-28000'],
    ['contraseña expirada', 401, 'La contraseña de Oracle ha expirado (ORA-28001)', 'ORA-28001'],
    ['Oracle inalcanzable (listener)', 502, 'No hay un listener de Oracle escuchando en ese host y puerto (ORA-12541)', 'ORA-12541'],
    ['servicio inexistente', 502, 'El servicio de Oracle indicado no existe (ORA-12514)', 'ORA-12514'],
  ])('%s: muestra el mensaje con su código ORA en una alerta', async (_caso, status, mensaje, codigo) => {
    fallarCon({ mensaje, codigo }, status)
    render(<ModalLogin />)

    completarYEnviar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(mensaje)
    expect(alerta.textContent).toContain(codigo)
  })

  it('un fallo de Oracle no se presenta como backend caído', async () => {
    fallarCon({ mensaje: 'No hay un listener (ORA-12541)', codigo: 'ORA-12541' }, 502)
    render(<ModalLogin />)

    completarYEnviar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).not.toContain('backend')
  })

  it('datos rechazados por el servidor (422) muestran cada error', async () => {
    fallarCon({ errores: ['El campo host es obligatorio', 'El puerto debe ser un número'] }, 422)
    render(<ModalLogin />)

    completarYEnviar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('El campo host es obligatorio')
    expect(alerta.textContent).toContain('El puerto debe ser un número')
  })
})

describe('backend que no responde', () => {
  it('sin respuesta alguna muestra el aviso de conexión y ERR_CONEXION', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    render(<ModalLogin />)

    completarYEnviar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(AVISO_CONEXION)
    expect(alerta.textContent).toContain('ERR_CONEXION')
  })

  it.each([502, 503, 504])('si el proxy responde %i muestra ese código', async (status) => {
    vi.stubGlobal('fetch', vi.fn(async () => respuestaDelProxy(status)))
    render(<ModalLogin />)

    completarYEnviar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(AVISO_CONEXION)
    expect(alerta.textContent).toContain(String(status))
    expect(alerta.textContent).not.toContain('ERR_CONEXION')
  })
})

describe('estado del modal tras un fallo', () => {
  beforeEach(() => {
    fallarCon({ mensaje: 'Usuario o contraseña de Oracle incorrectos (ORA-01017)', codigo: 'ORA-01017' }, 401)
  })

  it('sigue abierto', async () => {
    render(<ModalLogin />)

    completarYEnviar()
    await screen.findByRole('alert')

    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).not.toBeNull()
  })

  it('vacía la contraseña y conserva host, puerto, servicio, usuario y el check SYSDBA', async () => {
    render(<ModalLogin />)

    completarYEnviar({ sysdba: true })
    await screen.findByRole('alert')

    expect(campo('Contraseña').value).toBe('')
    expect(campo('Host').value).toBe('db.local')
    expect(campo('Puerto').value).toBe('1522')
    expect(campo('Servicio').value).toBe('XEPDB1')
    expect(campo('Usuario').value).toBe('HR')
    expect((screen.getByRole('checkbox', { name: 'Iniciar como SYSDBA' }) as HTMLInputElement).checked).toBe(true)
  })

  it('devuelve el foco a la contraseña', async () => {
    render(<ModalLogin />)

    completarYEnviar()
    await screen.findByRole('alert')

    expect(document.activeElement).toBe(campo('Contraseña'))
  })

  it('el botón vuelve a quedar habilitado', async () => {
    render(<ModalLogin />)

    completarYEnviar()
    await screen.findByRole('alert')

    const boton = screen.getByRole('button', { name: 'Iniciar sesión' }) as HTMLButtonElement
    expect(boton.disabled).toBe(false)
  })

  it('la contraseña no aparece en ninguna parte del diálogo', async () => {
    render(<ModalLogin />)

    completarYEnviar()
    await screen.findByRole('alert')

    expect(screen.getByRole('dialog').textContent).not.toContain(PASSWORD)
    expect(screen.getByRole('dialog').innerHTML).not.toContain(PASSWORD)
  })

  it('no recuerda nada en el navegador tras un fallo', async () => {
    render(<ModalLogin />)

    completarYEnviar()
    await screen.findByRole('alert')

    expect(localStorage.getItem('oracle.conexion')).toBeNull()
  })

  it('al reintentar la alerta anterior desaparece', async () => {
    render(<ModalLogin />)
    completarYEnviar()
    await screen.findByRole('alert')
    vi.stubGlobal('fetch', vi.fn(async () => respuesta({ token: 't', usuario: 'HR', sysdba: false })))

    fireEvent.change(campo('Contraseña'), { target: { value: 'otra' } })
    fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  })

  it('un nuevo fallo reemplaza el mensaje anterior en vez de acumularlo', async () => {
    render(<ModalLogin />)
    completarYEnviar()
    await screen.findByRole('alert')
    fallarCon({ mensaje: 'La cuenta de Oracle está bloqueada (ORA-28000)', codigo: 'ORA-28000' }, 401)

    fireEvent.change(campo('Contraseña'), { target: { value: 'otra' } })
    fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)

    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('ORA-28000'))
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByRole('alert').textContent).not.toContain('ORA-01017')
  })
})
