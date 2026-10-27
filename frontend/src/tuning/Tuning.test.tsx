import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Tuning } from './Tuning'

const TOKEN = 'tok-123'
const ok = (cuerpo: unknown) => ({ ok: true, status: 200, json: async () => cuerpo })

const PLAN = {
  texto: ['Plan hash value: 1', '| 0 | SELECT STATEMENT |'],
  operaciones: [
    { id: 0, nivel: 0, operacion: 'SELECT STATEMENT', opciones: null, propietario: null, objeto: null, costo: 3, filas: 107, bytes: 7000, acceso: null, filtro: null },
    { id: 1, nivel: 1, operacion: 'TABLE ACCESS', opciones: 'FULL', propietario: 'HR', objeto: 'EMPLOYEES', costo: 3, filas: 107, bytes: 7000, acceso: null, filtro: '"SALARY">1000' },
  ],
  observaciones: ['Se lee completa la tabla EMPLOYEES (TABLE ACCESS FULL).'],
}

const TABLAS = [
  { tabla: 'EMPLOYEES', filas: 107, bloques: 5, largo_promedio: 69, analizada: '20/10/2026 08:00:00', obsoletas: false },
  { tabla: 'JOBS', filas: null, bloques: null, largo_promedio: null, analizada: null, obsoletas: false },
]

const INDICES = [
  { propietario: 'HR', nombre: 'EMP_EMP_ID_PK', unico: true, tipo: 'NORMAL', estado: 'VALID', tablespace: 'USERS', analizado: null, columnas: 'EMPLOYEE_ID', restriccion: 'EMP_EMP_ID_PK' },
  { propietario: 'HR', nombre: 'EMP_NAME_IX', unico: false, tipo: 'NORMAL', estado: 'VALID', tablespace: 'USERS', analizado: null, columnas: 'LAST_NAME', restriccion: null },
]

let fetchFalso: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchFalso = vi.fn(async (url: string, opciones?: RequestInit) => {
    if (opciones?.method === 'POST') {
      if (url === '/tuning/plan') return ok(PLAN)
      return ok({ mensaje: 'Operación realizada' })
    }
    if (url === '/tuning/catalogos') return ok({ schemas: ['HR'], tablespaces: ['USERS'] })
    if (url === '/tuning/tablas?schema=HR') return ok({ tablas: TABLAS })
    if (url === '/tuning/indices?schema=HR&tabla=EMPLOYEES')
      return ok({
        indices: INDICES,
        columnas: [
          { nombre: 'EMPLOYEE_ID', tipo: 'NUMBER' },
          { nombre: 'LAST_NAME', tipo: 'VARCHAR2' },
          { nombre: 'FIRST_NAME', tipo: 'VARCHAR2' },
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
const elegirSchema = async () => {
  await screen.findByRole('option', { name: 'HR' })
  fireEvent.change(screen.getByLabelText('Schema'), { target: { value: 'HR' } })
}

describe('pantalla de tunning de consultas', () => {
  it('muestra el plan de ejecución con sus operaciones y observaciones', async () => {
    render(<Tuning token={TOKEN} />)

    await elegirSchema()
    fireEvent.change(screen.getByLabelText('Sentencia SQL'), {
      target: { value: 'SELECT * FROM employees WHERE salary > 1000' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Ver plan de ejecución' }))

    expect(await screen.findByText('TABLE ACCESS FULL')).not.toBeNull()
    expect(screen.getByText('HR.EMPLOYEES')).not.toBeNull()
    expect(screen.getByText('Filtro: "SALARY">1000')).not.toBeNull()
    expect(screen.getByText(/Se lee completa la tabla EMPLOYEES/)).not.toBeNull()
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      sql: 'SELECT * FROM employees WHERE salary > 1000',
      schema: 'HR',
    })
  })

  it('lista las estadísticas y marca las tablas nunca analizadas', async () => {
    render(<Tuning token={TOKEN} />)
    fireEvent.click(screen.getByRole('button', { name: 'Estadísticas' }))

    await elegirSchema()

    expect(await screen.findByText('EMPLOYEES')).not.toBeNull()
    expect(screen.getByText('Nunca')).not.toBeNull()
  })

  it('actualiza las estadísticas de una tabla', async () => {
    render(<Tuning token={TOKEN} />)
    fireEvent.click(screen.getByRole('button', { name: 'Estadísticas' }))
    await elegirSchema()

    fireEvent.click(await screen.findByRole('button', { name: 'Actualizar estadísticas de JOBS' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tuning/estadisticas')
    expect(JSON.parse(posts()[0][1].body)).toEqual({ schema: 'HR', tabla: 'JOBS' })
    expect((await screen.findByRole('status')).textContent).toBe('Operación realizada')
  })

  it('crea un índice compuesto respetando el orden en que se marcan las columnas', async () => {
    render(<Tuning token={TOKEN} />)
    fireEvent.click(screen.getByRole('button', { name: 'Índices' }))
    await elegirSchema()
    await screen.findByRole('option', { name: 'EMPLOYEES' })
    fireEvent.change(screen.getByLabelText('Tabla'), { target: { value: 'EMPLOYEES' } })

    fireEvent.change(await screen.findByLabelText('Nombre del índice'), { target: { value: 'emp_nombre_ix' } })
    fireEvent.click(await screen.findByLabelText(/FIRST_NAME/))
    fireEvent.click(screen.getByLabelText(/^LAST_NAME/))
    expect(screen.getByText('Orden del índice: FIRST_NAME, LAST_NAME')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Crear índice' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      schema: 'HR',
      tabla: 'EMPLOYEES',
      nombre: 'emp_nombre_ix',
      columnas: ['FIRST_NAME', 'LAST_NAME'],
      unico: false,
      tablespace: '',
    })
  })

  it('eliminar un índice pide confirmación y no se ofrece para el de la llave primaria', async () => {
    render(<Tuning token={TOKEN} />)
    fireEvent.click(screen.getByRole('button', { name: 'Índices' }))
    await elegirSchema()
    await screen.findByRole('option', { name: 'EMPLOYEES' })
    fireEvent.change(screen.getByLabelText('Tabla'), { target: { value: 'EMPLOYEES' } })

    expect(await screen.findByText('Respalda EMP_EMP_ID_PK')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Eliminar EMP_EMP_ID_PK' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Eliminar EMP_NAME_IX' }))
    expect(posts()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Sí, confirmar' }))

    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][0]).toBe('/tuning/indices/eliminar')
    expect(JSON.parse(posts()[0][1].body)).toEqual({
      schema: 'HR',
      tabla: 'EMPLOYEES',
      nombre: 'EMP_NAME_IX',
      confirmar: true,
    })
  })

  it('consulta con el token de la sesión y sin credenciales', async () => {
    render(<Tuning token={TOKEN} />)

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled())
    for (const [, opciones] of fetchFalso.mock.calls) {
      expect(opciones.headers).toEqual({ Authorization: `Bearer ${TOKEN}` })
    }
  })
})
