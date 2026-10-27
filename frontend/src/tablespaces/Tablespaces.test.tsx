import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Tablespaces } from './Tablespaces'

const TOKEN = 'tok-123'
const CARPETA = '/opt/oracle/oradata/XE/XEPDB1/'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const USERS = {
  nombre: 'USERS',
  tipo: 'PERMANENT',
  estado: 'ONLINE',
  bigfile: false,
  tamano_mb: 100,
  usado_mb: 90,
  libre_mb: 10,
  maximo_mb: 200,
  porcentaje_uso: 90,
  archivos: 1,
}
const SYSTEM = { ...USERS, nombre: 'SYSTEM', porcentaje_uso: 40 }
const DATAFILE = {
  id: 7,
  archivo: `${CARPETA}users01.dbf`,
  tamano_mb: 100,
  autoextensible: false,
  maximo_mb: 0,
  estado: 'AVAILABLE',
}

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (opciones?.method === 'POST') {
      if (url === '/tablespaces')
        return { ok: false, status: 422, json: async () => ({ errores: ['Debes ingresar el nombre de el tablespace'] }) }
      return ok({ mensaje: 'Operación realizada' })
    }
    if (url === '/tablespaces') return ok({ tablespaces: [SYSTEM, USERS], carpeta: CARPETA })
    if (url === '/tablespaces/USERS') return ok({ ...USERS, datafiles: [DATAFILE] })
    if (url === '/tablespaces/SYSTEM') return ok({ ...SYSTEM, datafiles: [] })
    return ok({})
  })
  vi.stubGlobal('fetch', fetchFalso)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const posts = () => fetchFalso.mock.calls.filter(([, o]) => o?.method === 'POST')
const abrirUsers = async () => {
  render(<Tablespaces token={TOKEN} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Administrar USERS' }))
  await screen.findByRole('heading', { name: 'Tablespace USERS' })
  await screen.findByText(`${CARPETA}users01.dbf`)
}

describe('pantalla de administración de tablespaces', () => {
  it('lista los tablespaces con su porcentaje de uso', async () => {
    render(<Tablespaces token={TOKEN} />)

    expect(await screen.findByText('USERS')).not.toBeNull()
    expect(screen.getByText('90 %')).not.toBeNull()
    expect(screen.getByText('90 %').closest('.uso')?.classList.contains('alto')).toBe(true)
    expect(screen.getByText('40 %').closest('.uso')?.classList.contains('alto')).toBe(false)
  })

  it('al crear muestra la carpeta de los datafiles y los errores de validación', async () => {
    render(<Tablespaces token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Crear tablespace' }))
    expect(await screen.findByText(`Se crea en ${CARPETA}`, { exact: false })).not.toBeNull()
    fireEvent.change(screen.getByLabelText('Nombre del archivo'), { target: { value: 'ventas01.dbf' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Crear tablespace' }).at(-1)!)

    expect((await screen.findByRole('alert')).textContent).toContain('Debes ingresar el nombre')
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      nombre: '',
      tipo: 'PERMANENT',
      archivo: 'ventas01.dbf',
      tamano: '100M',
      autoextend: true,
      siguiente: '10M',
      maximo: 'UNLIMITED',
    })
  })

  it('sin AUTOEXTEND oculta el incremento y el máximo', async () => {
    render(<Tablespaces token={TOKEN} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Crear tablespace' }))

    expect(screen.queryByLabelText('Tamaño máximo')).not.toBeNull()
    fireEvent.click(screen.getByLabelText('Crecer automáticamente cuando se llene (AUTOEXTEND)'))

    expect(screen.queryByLabelText('Tamaño máximo')).toBeNull()
  })

  it('poner OFFLINE pide confirmación', async () => {
    await abrirUsers()

    fireEvent.click(screen.getByRole('button', { name: 'Poner OFFLINE' }))
    expect(posts()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tablespaces/USERS/estado')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ estado: 'OFFLINE', confirmar: true })
  })

  it('redimensiona el datafile elegido', async () => {
    await abrirUsers()

    fireEvent.change(screen.getByLabelText('Archivo a redimensionar'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Nuevo tamaño'), { target: { value: '200M' } })
    fireEvent.click(screen.getByRole('button', { name: 'Redimensionar' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tablespaces/USERS/archivos/7/redimensionar')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ tamano: '200M' })
    expect((await screen.findByRole('status')).textContent).toBe('Operación realizada')
  })

  it('activa AUTOEXTEND de un datafile', async () => {
    await abrirUsers()

    fireEvent.click(screen.getByRole('button', { name: 'Activar AUTOEXTEND del archivo 7' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tablespaces/USERS/archivos/7/autoextend')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ autoextend: true })
  })

  it('agrega un datafile al tablespace', async () => {
    await abrirUsers()

    fireEvent.change(screen.getByLabelText('Nombre del archivo'), { target: { value: 'users02.dbf' } })
    fireEvent.click(screen.getByRole('button', { name: 'Agregar archivo' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tablespaces/USERS/archivos')
    expect(JSON.parse(posts()[0][1].body).archivo).toBe('users02.dbf')
  })

  it('no ofrece cambiar el estado de SYSTEM', async () => {
    render(<Tablespaces token={TOKEN} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Administrar SYSTEM' }))
    await screen.findByRole('heading', { name: 'Estado' })

    expect(screen.queryByRole('button', { name: 'Poner OFFLINE' })).toBeNull()
  })

  it('consulta con el token de la sesión y sin credenciales', async () => {
    render(<Tablespaces token={TOKEN} />)

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    for (const [, opciones] of fetchFalso.mock.calls) {
      expect(opciones.headers).toEqual({ Authorization: `Bearer ${TOKEN}` })
    }
  })
})
