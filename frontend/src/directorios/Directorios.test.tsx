import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Directorios } from './Directorios'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const RESPALDOS = { nombre: 'RESPALDOS', ruta: '/opt/oracle/respaldos' }
const DATA_PUMP = { nombre: 'DATA_PUMP_DIR', ruta: '/opt/oracle/admin/dpdump' }

let fetchFalso: ReturnType<typeof vi.fn>

const simular = (respuesta: unknown) => {
  fetchFalso = vi.fn(async () => respuesta)
  vi.stubGlobal('fetch', fetchFalso)
}

beforeEach(() => {
  simular(ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos'] }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('pantalla de directorios', () => {
  it('muestra el nombre y la ruta de cada directorio', async () => {
    render(<Directorios token={TOKEN} />)

    expect(await screen.findByText('RESPALDOS')).not.toBeNull()
    expect(screen.getByText('/opt/oracle/respaldos')).not.toBeNull()
    expect(screen.getByText('DATA_PUMP_DIR')).not.toBeNull()
    expect(screen.getByText('/opt/oracle/admin/dpdump')).not.toBeNull()
    expect(fetchFalso.mock.calls[0][0]).toBe('/directorios')
  })

  it('muestra el botón de crear', async () => {
    render(<Directorios token={TOKEN} />)

    await screen.findByText('RESPALDOS')
    expect(screen.getByRole('button', { name: 'Crear directorio' })).not.toBeNull()
  })

  it('con la lista vacía no muestra aviso de error y sí el botón de crear', async () => {
    simular(ok({ directorios: [], ejemplos_ruta: ['/opt/oracle/respaldos'] }))
    render(<Directorios token={TOKEN} />)

    expect(await screen.findByText('No hay directorios para mostrar')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: 'Crear directorio' })).not.toBeNull()
  })

  it('ante un error del servidor muestra el aviso', async () => {
    simular({ ok: false, status: 500, json: async () => ({ mensaje: 'No se pudo listar los directorios' }) })
    render(<Directorios token={TOKEN} />)

    expect((await screen.findByRole('alert')).textContent).toContain('No se pudo listar los directorios')
  })
})

describe('crear directorio', () => {
  const abrirFormulario = async () => {
    render(<Directorios token={TOKEN} />)
    await screen.findByText('RESPALDOS')
    fireEvent.click(screen.getByRole('button', { name: 'Crear directorio' }))
  }

  const rellenarYEnviar = async () => {
    fireEvent.change(await screen.findByLabelText('Nombre del directorio'), { target: { value: 'nuevo' } })
    fireEvent.change(screen.getByLabelText('Ruta de la carpeta'), { target: { value: '/opt/oracle/nuevo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear' }))
  }

  const USUARIOS = ok({ usuarios: [{ usuario: 'HR', estado: 'OPEN' }, { usuario: 'SCOTT', estado: 'OPEN' }] })
  let usuariosFalso: ReturnType<typeof vi.fn>

  // /seguridad/usuarios se responde aparte para que fetchFalso solo cuente las llamadas de directorios.
  const respuestas = (...siguientes: unknown[]) => {
    const cola = [...siguientes]
    fetchFalso = vi.fn(async () => cola.shift())
    usuariosFalso = vi.fn(async () => usuarios)
    vi.stubGlobal('fetch', (url: string, opciones?: unknown) =>
      url === '/seguridad/usuarios' ? usuariosFalso(url, opciones) : fetchFalso(url, opciones),
    )
  }

  let usuarios: unknown
  beforeEach(() => {
    usuarios = USUARIOS
  })

  const lista = ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos', 'C:\\respaldos'] })
  const fallo = (status: number, cuerpo: unknown) => ({ ok: false, status, json: async () => cuerpo })

  it('el formulario pide nombre y ruta y muestra los ejemplos de ruta del servidor', async () => {
    respuestas(lista)
    await abrirFormulario()

    expect(await screen.findByLabelText('Nombre del directorio')).not.toBeNull()
    expect(screen.getByLabelText('Ruta de la carpeta')).not.toBeNull()
    expect(screen.getByText(/\/opt\/oracle\/respaldos/)).not.toBeNull()
    expect(screen.getByText(/C:\\respaldos/)).not.toBeNull()
  })

  it('al confirmar envía POST /directorios con nombre y ruta', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), lista)
    await abrirFormulario()
    await rellenarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    const [url, opciones] = fetchFalso.mock.calls[1]
    expect(url).toBe('/directorios')
    expect(opciones.method).toBe('POST')
    expect(JSON.parse(opciones.body)).toEqual({ nombre: 'nuevo', ruta: '/opt/oracle/nuevo' })
  })

  it('si se crea informa «Directorio X creado» y recarga la lista', async () => {
    const NUEVO = { nombre: 'NUEVO', ruta: '/opt/oracle/nuevo' }
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), ok({ directorios: [NUEVO], ejemplos_ruta: [] }))
    await abrirFormulario()
    await rellenarYEnviar()

    expect((await screen.findByRole('status')).textContent).toContain('Directorio NUEVO creado')
    expect(await screen.findByText('/opt/oracle/nuevo')).not.toBeNull()
    expect(fetchFalso).toHaveBeenCalledTimes(3)
    expect(fetchFalso.mock.calls[2][0]).toBe('/directorios')
  })

  it('ante 422 muestra los errores y no recarga la lista', async () => {
    respuestas(lista, fallo(422, { errores: ['La ruta debe ser absoluta'] }))
    await abrirFormulario()
    await rellenarYEnviar()

    expect((await screen.findByRole('alert')).textContent).toContain('La ruta debe ser absoluta')
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })

  it('ante 500 muestra el mensaje, la explicación y el error y no recarga la lista', async () => {
    respuestas(
      lista,
      fallo(500, { mensaje: 'No se pudieron dar permisos', explicacion: 'La carpeta debe existir', error: 'chown: sin permiso' }),
    )
    await abrirFormulario()
    await rellenarYEnviar()

    const alerta = (await screen.findByRole('alert')).textContent
    expect(alerta).toContain('No se pudieron dar permisos')
    expect(alerta).toContain('La carpeta debe existir')
    expect(alerta).toContain('chown: sin permiso')
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })

  it('Schema es una lista con «Sin schema» por defecto y un elemento por usuario', async () => {
    respuestas(lista)
    await abrirFormulario()

    const campo = (await screen.findByLabelText(/Schema/)) as HTMLSelectElement
    expect(campo.tagName).toBe('SELECT')
    await screen.findByRole('option', { name: 'HR' })
    expect(Array.from(campo.options).map((o) => o.textContent)).toEqual(['Sin schema', 'HR', 'SCOTT'])
    expect(campo.value).toBe('')
    expect(usuariosFalso).toHaveBeenCalledTimes(1)
  })

  it('por defecto el POST no lleva schema', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), lista)
    await abrirFormulario()
    await screen.findByRole('option', { name: 'HR' })
    await rellenarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    expect(JSON.parse(fetchFalso.mock.calls[1][1].body)).toEqual({ nombre: 'nuevo', ruta: '/opt/oracle/nuevo' })
  })

  it('al elegir un usuario el POST lleva nombre, ruta y schema', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), lista)
    await abrirFormulario()
    await screen.findByRole('option', { name: 'HR' })
    fireEvent.change(screen.getByLabelText(/Schema/), { target: { value: 'HR' } })
    await rellenarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    expect(JSON.parse(fetchFalso.mock.calls[1][1].body)).toEqual({ nombre: 'nuevo', ruta: '/opt/oracle/nuevo', schema: 'HR' })
  })

  it('si falla la carga de usuarios muestra el aviso y se puede crear sin schema', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio NUEVO creado' }), lista)
    usuarios = fallo(500, { mensaje: 'No se pudo listar los usuarios' })
    await abrirFormulario()

    expect((await screen.findByRole('alert')).textContent).toContain('No se pudo listar los usuarios')
    await rellenarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    expect(JSON.parse(fetchFalso.mock.calls[1][1].body)).toEqual({ nombre: 'nuevo', ruta: '/opt/oracle/nuevo' })
  })

  it('ante 422 por schema inválido o inexistente muestra el aviso y no recarga la lista', async () => {
    respuestas(lista, fallo(422, { errores: ['El schema HR no existe'] }))
    await abrirFormulario()
    await screen.findByRole('option', { name: 'HR' })
    fireEvent.change(screen.getByLabelText(/Schema/), { target: { value: 'HR' } })
    await rellenarYEnviar()

    expect((await screen.findByRole('alert')).textContent).toContain('El schema HR no existe')
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })
})

describe('editar directorio', () => {
  const respuestas = (...siguientes: unknown[]) => {
    const cola = [...siguientes]
    fetchFalso = vi.fn(async () => cola.shift())
    vi.stubGlobal('fetch', fetchFalso)
  }

  const lista = ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos', 'C:\\respaldos'] })
  const fallo = (status: number, cuerpo: unknown) => ({ ok: false, status, json: async () => cuerpo })

  const abrirFormulario = async () => {
    render(<Directorios token={TOKEN} />)
    await screen.findByText('RESPALDOS')
    fireEvent.click(screen.getByRole('button', { name: 'Editar RESPALDOS' }))
  }

  const cambiarYEnviar = async () => {
    fireEvent.change(await screen.findByLabelText('Ruta de la carpeta'), { target: { value: '/opt/oracle/otra' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
  }

  it('el formulario muestra el nombre sin poder editarlo, la ruta actual y los ejemplos del servidor', async () => {
    respuestas(lista)
    await abrirFormulario()

    const nombre = (await screen.findByLabelText('Nombre del directorio')) as HTMLInputElement
    expect(nombre.value).toBe('RESPALDOS')
    expect(nombre.readOnly || nombre.disabled).toBe(true)
    expect((screen.getByLabelText('Ruta de la carpeta') as HTMLInputElement).value).toBe('/opt/oracle/respaldos')
    expect(screen.getByText(/C:\\respaldos/)).not.toBeNull()
  })

  it('el formulario de editar no muestra el campo Schema', async () => {
    respuestas(lista)
    await abrirFormulario()

    await screen.findByLabelText('Ruta de la carpeta')
    expect(screen.queryByLabelText(/Schema/)).toBeNull()
  })

  it('al confirmar envía PUT /directorios/{nombre} solo con la ruta', async () => {
    respuestas(lista, ok({ mensaje: 'Directorio RESPALDOS actualizado' }), lista)
    await abrirFormulario()
    await cambiarYEnviar()

    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(3))
    const [url, opciones] = fetchFalso.mock.calls[1]
    expect(url).toBe('/directorios/RESPALDOS')
    expect(opciones.method).toBe('PUT')
    expect(JSON.parse(opciones.body)).toEqual({ ruta: '/opt/oracle/otra' })
  })

  it('si se edita informa el cambio y recarga la lista', async () => {
    const CAMBIADO = { nombre: 'RESPALDOS', ruta: '/opt/oracle/otra' }
    respuestas(
      lista,
      ok({ mensaje: 'Directorio RESPALDOS actualizado' }),
      ok({ directorios: [CAMBIADO], ejemplos_ruta: [] }),
    )
    await abrirFormulario()
    await cambiarYEnviar()

    expect((await screen.findByRole('status')).textContent).toContain('Directorio RESPALDOS actualizado')
    expect(await screen.findByText('/opt/oracle/otra')).not.toBeNull()
    expect(fetchFalso).toHaveBeenCalledTimes(3)
    expect(fetchFalso.mock.calls[2][0]).toBe('/directorios')
  })

  it.each([
    [404, { mensaje: 'El directorio no existe' }, 'El directorio no existe'],
    [422, { errores: ['La ruta debe ser absoluta'] }, 'La ruta debe ser absoluta'],
    [500, { mensaje: 'No se pudieron dar permisos', explicacion: 'La carpeta debe existir', error: 'chown: sin permiso' }, 'chown: sin permiso'],
  ])('ante %i muestra el aviso y no recarga la lista', async (status, cuerpo, texto) => {
    respuestas(lista, fallo(status, cuerpo))
    await abrirFormulario()
    await cambiarYEnviar()

    expect((await screen.findByRole('alert')).textContent).toContain(texto)
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })
})

describe('eliminar directorio', () => {
  const respuestas = (...siguientes: unknown[]) => {
    const cola = [...siguientes]
    fetchFalso = vi.fn(async () => cola.shift())
    vi.stubGlobal('fetch', fetchFalso)
  }

  const lista = ok({ directorios: [DATA_PUMP, RESPALDOS], ejemplos_ruta: ['/opt/oracle/respaldos'] })
  const fallo = (status: number, cuerpo: unknown) => ({ ok: false, status, json: async () => cuerpo })

  const pedirEliminar = async () => {
    render(<Directorios token={TOKEN} />)
    await screen.findByText('RESPALDOS')
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar RESPALDOS' }))
  }

  it('pedir eliminar muestra la confirmación y no envía nada todavía', async () => {
    respuestas(lista)
    await pedirEliminar()

    expect(screen.getByRole('button', { name: 'Sí, confirmar' })).not.toBeNull()
    expect(fetchFalso).toHaveBeenCalledTimes(1)
  })

  it('cancelar no envía ninguna petición ni cambia la lista', async () => {
    respuestas(lista)
    await pedirEliminar()
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(screen.queryByRole('button', { name: 'Sí, confirmar' })).toBeNull()
    expect(screen.getByText('RESPALDOS')).not.toBeNull()
    expect(fetchFalso).toHaveBeenCalledTimes(1)
  })

  it('confirmar envía DELETE /directorios/{nombre}, informa y recarga la lista', async () => {
    respuestas(
      lista,
      ok({ mensaje: 'Directorio RESPALDOS eliminado' }),
      ok({ directorios: [DATA_PUMP], ejemplos_ruta: [] }),
    )
    await pedirEliminar()
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    expect((await screen.findByRole('status')).textContent).toContain('Directorio RESPALDOS eliminado')
    await waitFor(() => expect(screen.queryByText('/opt/oracle/respaldos')).toBeNull())
    expect(fetchFalso).toHaveBeenCalledTimes(3)
    const [url, opciones] = fetchFalso.mock.calls[1]
    expect(url).toBe('/directorios/RESPALDOS')
    expect(opciones.method).toBe('DELETE')
    expect(fetchFalso.mock.calls[2][0]).toBe('/directorios')
  })

  it.each([
    [404, { mensaje: 'El directorio no existe' }, 'El directorio no existe'],
    [422, { errores: ['No se puede editar ni eliminar un directorio del sistema'] }, 'No se puede editar ni eliminar'],
    [500, { mensaje: 'Oracle rechazó la operación', explicacion: 'Revisa el directorio', error: 'ORA-00955' }, 'ORA-00955'],
  ])('ante %i muestra el aviso y no recarga la lista', async (status, cuerpo, texto) => {
    respuestas(lista, fallo(status, cuerpo))
    await pedirEliminar()
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    expect((await screen.findByRole('alert')).textContent).toContain(texto)
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })
})
