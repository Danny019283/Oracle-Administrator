import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ModalLogin } from './ModalLogin'

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

let fetchFalso: ReturnType<typeof vi.fn>

const campo = (nombre: string | RegExp) => screen.getByLabelText(nombre) as HTMLInputElement
const escribir = (nombre: string | RegExp, valor: string) =>
  fireEvent.change(campo(nombre), { target: { value: valor } })
const enviar = () => fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)

function completar(cambios: Record<string, string> = {}) {
  const valores: Record<string, string> = {
    Host: 'db.local',
    Puerto: '1522',
    Servicio: 'XEPDB1',
    Usuario: 'HR',
    Contraseña: 's3creta!',
    ...cambios,
  }
  for (const [nombre, valor] of Object.entries(valores)) escribir(nombre, valor)
}

beforeEach(() => {
  localStorage.clear()
  fetchFalso = vi.fn(async () => respuesta({ token: 't', usuario: 'HR', sysdba: false }))
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('estructura del modal', () => {
  it('es un diálogo modal con el título «Iniciar sesión»', () => {
    render(<ModalLogin />)

    const dialogo = screen.getByRole('dialog', { name: 'Iniciar sesión' })
    expect(dialogo.getAttribute('aria-modal')).toBe('true')
  })

  it('tiene los cinco campos y el check «Iniciar como SYSDBA» desmarcado', () => {
    render(<ModalLogin />)

    for (const nombre of ['Host', 'Puerto', 'Servicio', 'Usuario', 'Contraseña']) {
      expect(campo(nombre)).not.toBeNull()
    }
    expect(campo('Contraseña').type).toBe('password')
    const sysdba = screen.getByRole('checkbox', { name: 'Iniciar como SYSDBA' }) as HTMLInputElement
    expect(sysdba.checked).toBe(false)
  })

  it('no tiene botón de cerrar: el único botón es el de iniciar sesión', () => {
    render(<ModalLogin />)

    const botones = screen.getAllByRole('button')
    expect(botones.map((b) => b.textContent)).toEqual(['Iniciar sesión'])
  })

  it('el botón es de tipo submit dentro del formulario, así Enter envía', () => {
    render(<ModalLogin />)

    const boton = screen.getByRole('button', { name: 'Iniciar sesión' }) as HTMLButtonElement
    const formulario = screen.getByRole('dialog').querySelector('form')!
    expect(boton.type).toBe('submit')
    expect(boton.form).toBe(formulario)
    for (const nombre of ['Host', 'Puerto', 'Servicio', 'Usuario', 'Contraseña']) {
      expect(campo(nombre).form).toBe(formulario)
    }
  })
})

describe('bloqueo', () => {
  it('Escape no lo cierra', () => {
    render(<ModalLogin />)

    const noCancelado = fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })

    expect(noCancelado).toBe(false)
    expect(screen.getByRole('dialog')).not.toBeNull()
  })

  it('un clic fuera del diálogo no lo cierra', () => {
    render(<ModalLogin />)

    fireEvent.click(screen.getByRole('dialog').parentElement!)

    expect(screen.getByRole('dialog')).not.toBeNull()
  })

  it('Tab desde el último elemento vuelve al primer campo', () => {
    render(<ModalLogin />)
    screen.getByRole('button', { name: 'Iniciar sesión' }).focus()

    const noCancelado = fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Tab' })

    expect(noCancelado).toBe(false)
    expect(document.activeElement).toBe(campo('Host'))
  })

  it('Shift+Tab desde el primer campo salta al último elemento', () => {
    render(<ModalLogin />)
    campo('Host').focus()

    const noCancelado = fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Tab', shiftKey: true })

    expect(noCancelado).toBe(false)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Iniciar sesión' }))
  })

  it('Tab en medio del formulario sigue el orden natural del navegador', () => {
    render(<ModalLogin />)
    campo('Puerto').focus()

    const noCancelado = fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Tab' })

    expect(noCancelado).toBe(true)
  })
})

describe('foco y datos recordados', () => {
  it('al abrir mueve el foco al primer campo', () => {
    render(<ModalLogin />)

    expect(document.activeElement).toBe(campo('Host'))
  })

  it('precarga host, puerto, servicio y usuario recordados, y deja vacía la contraseña', () => {
    localStorage.setItem(
      'oracle.conexion',
      JSON.stringify({ host: 'db.local', puerto: '1522', servicio: 'XEPDB1', usuario: 'HR' }),
    )

    render(<ModalLogin />)

    expect(campo('Host').value).toBe('db.local')
    expect(campo('Puerto').value).toBe('1522')
    expect(campo('Servicio').value).toBe('XEPDB1')
    expect(campo('Usuario').value).toBe('HR')
    expect(campo('Contraseña').value).toBe('')
    expect((screen.getByRole('checkbox', { name: 'Iniciar como SYSDBA' }) as HTMLInputElement).checked).toBe(false)
  })

  it('sin datos recordados los campos empiezan vacíos', () => {
    render(<ModalLogin />)

    for (const nombre of ['Host', 'Puerto', 'Servicio', 'Usuario', 'Contraseña']) {
      expect(campo(nombre).value).toBe('')
    }
  })
})

describe('validación sin llamar a la API', () => {
  it('con todos los campos vacíos marca cada uno como obligatorio y no llama a la API', () => {
    render(<ModalLogin />)

    enviar()

    expect(fetchFalso).not.toHaveBeenCalled()
    for (const nombre of ['host', 'servicio', 'usuario']) {
      expect(screen.getByText(`El campo ${nombre} es obligatorio`)).not.toBeNull()
    }
    expect(screen.getByText('El campo puerto es obligatorio')).not.toBeNull()
    expect(screen.getByText('El campo contraseña es obligatorio')).not.toBeNull()
    for (const nombre of ['Host', 'Puerto', 'Servicio', 'Usuario', 'Contraseña']) {
      expect(campo(nombre).getAttribute('aria-invalid')).toBe('true')
    }
  })

  it('cada campo inválido queda asociado a su mensaje con aria-describedby', () => {
    render(<ModalLogin />)

    enviar()

    const mensaje = screen.getByText('El campo host es obligatorio')
    expect(campo('Host').getAttribute('aria-describedby')).toContain(mensaje.id)
  })

  it('mueve el foco al primer campo inválido', () => {
    render(<ModalLogin />)
    completar({ Servicio: '' })
    campo('Contraseña').focus()

    enviar()

    expect(document.activeElement).toBe(campo('Servicio'))
  })

  it('un campo de solo espacios cuenta como vacío', () => {
    render(<ModalLogin />)
    completar({ Usuario: '   ' })

    enviar()

    expect(fetchFalso).not.toHaveBeenCalled()
    expect(screen.getByText('El campo usuario es obligatorio')).not.toBeNull()
  })

  it.each(['abc', '15 21', '1521.5', '-1'])('el puerto «%s» no es numérico', (puerto) => {
    render(<ModalLogin />)
    completar({ Puerto: puerto })

    enviar()

    expect(fetchFalso).not.toHaveBeenCalled()
    expect(screen.getByText('El puerto debe ser un número')).not.toBeNull()
  })

  it.each(['0', '65536'])('el puerto %s está fuera de rango', (puerto) => {
    render(<ModalLogin />)
    completar({ Puerto: puerto })

    enviar()

    expect(fetchFalso).not.toHaveBeenCalled()
    expect(screen.getByText('El puerto debe estar entre 1 y 65535')).not.toBeNull()
  })

  it('al corregir y reenviar desaparecen los mensajes', async () => {
    render(<ModalLogin />)
    enviar()
    expect(screen.getByText('El campo host es obligatorio')).not.toBeNull()

    completar()
    enviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    expect(screen.queryByText('El campo host es obligatorio')).toBeNull()
    expect(campo('Host').getAttribute('aria-invalid')).not.toBe('true')
  })
})

describe('envío', () => {
  it('con datos válidos llama a POST /sesion con los valores y sysdba desmarcado', async () => {
    render(<ModalLogin />)
    completar()

    enviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(1))
    const [url, opciones] = fetchFalso.mock.calls[0]
    expect(url).toBe('/sesion')
    expect(JSON.parse(opciones.body)).toEqual({
      host: 'db.local',
      puerto: '1522',
      servicio: 'XEPDB1',
      usuario: 'HR',
      password: 's3creta!',
      sysdba: false,
    })
  })

  it('con el check marcado envía sysdba true', async () => {
    render(<ModalLogin />)
    completar()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Iniciar como SYSDBA' }))

    enviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    expect(JSON.parse(fetchFalso.mock.calls[0][1].body).sysdba).toBe(true)
  })

  it('recorta los espacios de host, servicio y usuario, pero no de la contraseña', async () => {
    render(<ModalLogin />)
    completar({ Host: ' db.local ', Servicio: ' XEPDB1 ', Usuario: ' HR ', Contraseña: ' s3 ' })

    enviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    const cuerpo = JSON.parse(fetchFalso.mock.calls[0][1].body)
    expect([cuerpo.host, cuerpo.servicio, cuerpo.usuario, cuerpo.password]).toEqual([
      'db.local',
      'XEPDB1',
      'HR',
      ' s3 ',
    ])
  })

  it('mientras envía deshabilita el botón y vuelve a habilitarlo al terminar', async () => {
    let terminar: (r: unknown) => void = () => {}
    fetchFalso.mockImplementationOnce(() => new Promise((resolver) => (terminar = resolver)))
    render(<ModalLogin />)
    completar()

    enviar()

    const boton = await screen.findByRole('button', { name: 'Iniciando sesión…' })
    expect((boton as HTMLButtonElement).disabled).toBe(true)

    terminar(respuesta({ mensaje: 'x', codigo: 'ORA-01017' }, 401))
    await waitFor(() =>
      expect((screen.getByRole('button', { name: 'Iniciar sesión' }) as HTMLButtonElement).disabled).toBe(false),
    )
  })
})
