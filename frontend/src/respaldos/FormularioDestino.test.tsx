import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { FormularioDestino } from './FormularioDestino'

const DIRECTORIOS = [
  { nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' },
  { nombre: 'OTRO', ruta: '/tmp/otro' },
]

const montar = (props: Partial<Parameters<typeof FormularioDestino>[0]> = {}) => {
  const alElegirDirectorio = vi.fn()
  const alCambiarNombre = vi.fn()
  render(
    <FormularioDestino
      directorios={DIRECTORIOS}
      directorio=""
      alElegirDirectorio={alElegirDirectorio}
      nombre=""
      alCambiarNombre={alCambiarNombre}
      etiquetaNombre="Nombre del dumpfile"
      ayudaNombre="Se agrega la fecha."
      {...props}
    />,
  )
  return { alElegirDirectorio, alCambiarNombre }
}

afterEach(cleanup)

describe('formulario de destino', () => {
  it('lista los directorios con su ruta tras la opción vacía', () => {
    montar()

    expect(screen.getByRole('heading', { name: 'Destino' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Selecciona un directorio' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'RESPALDO (/opt/oracle/Respaldos)' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'OTRO (/tmp/otro)' })).toBeTruthy()
  })

  it('avisa al elegir un directorio', () => {
    const { alElegirDirectorio } = montar()

    fireEvent.change(screen.getByRole('combobox', { name: 'Directorio' }), {
      target: { value: 'OTRO' },
    })

    expect(alElegirDirectorio).toHaveBeenCalledWith('OTRO')
  })

  it('muestra el nombre con su etiqueta y avisa al escribir', () => {
    const { alCambiarNombre } = montar({ nombre: 'ventas', etiquetaNombre: 'Nombre del respaldo' })

    const campo = screen.getByRole('textbox', { name: 'Nombre del respaldo' }) as HTMLInputElement
    expect(campo.value).toBe('ventas')
    fireEvent.change(campo, { target: { value: 'semanal' } })

    expect(alCambiarNombre).toHaveBeenCalledWith('semanal')
  })

  it('asocia la ayuda al campo del nombre', () => {
    montar()

    const campo = screen.getByRole('textbox', { name: 'Nombre del dumpfile' })
    expect(campo.getAttribute('aria-describedby')).toBe(
      screen.getByText('Se agrega la fecha.').getAttribute('id'),
    )
  })
})
