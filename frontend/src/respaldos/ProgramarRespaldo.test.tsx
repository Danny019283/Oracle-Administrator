import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { PROGRAMACION_INICIAL, ProgramarRespaldo, type Programacion } from './ProgramarRespaldo'

afterEach(cleanup)

const montar = (cambios: Partial<Programacion> = {}) => {
  const onChange = vi.fn()
  render(<ProgramarRespaldo valor={{ ...PROGRAMACION_INICIAL, ...cambios }} onChange={onChange} />)
  return onChange
}

const opciones = (etiqueta: string) =>
  Array.from((screen.getByLabelText(etiqueta) as HTMLSelectElement).options).map((o) => [o.text, o.value])

describe('ProgramarRespaldo', () => {
  it('ofrece las tres políticas con Full por defecto', () => {
    montar()

    expect(opciones('Política')).toEqual([
      ['Full (nivel 0)', 'FULL'],
      ['Incremental (nivel 1)', 'INCREMENTAL'],
      ['Transaccional (archivelogs)', 'TRANSACCIONAL'],
    ])
    expect((screen.getByLabelText('Política') as HTMLSelectElement).value).toBe('FULL')
  })

  it('con Full la frecuencia es Diario, Semanal o Mensual, sin «Cada N horas»', () => {
    montar()

    expect(opciones('Frecuencia')).toEqual([
      ['Diario', 'DIARIO'],
      ['Semanal', 'SEMANAL'],
      ['Mensual', 'MENSUAL'],
    ])
    expect((screen.getByLabelText('Frecuencia') as HTMLSelectElement).value).toBe('DIARIO')
  })

  it('con Transaccional ofrece también «Cada N horas»', () => {
    montar({ politica: 'TRANSACCIONAL' })

    expect(opciones('Frecuencia')).toContainEqual(['Cada N horas', 'HORAS'])
  })

  it('diario muestra solo la hora, 23:00 por defecto', () => {
    montar()

    const hora = screen.getByLabelText('Hora') as HTMLInputElement
    expect(hora.type).toBe('time')
    expect(hora.value).toBe('23:00')
    expect(screen.queryByLabelText('Día de la semana')).toBeNull()
    expect(screen.queryByLabelText('Día del mes')).toBeNull()
    expect(screen.queryByLabelText('Cada cuántas horas')).toBeNull()
  })

  it('semanal muestra la hora y el día de la semana (Domingo=0 … Sábado=6)', () => {
    montar({ frecuencia: 'SEMANAL' })

    expect(screen.getByLabelText('Hora')).toBeTruthy()
    const dias = opciones('Día de la semana')
    expect(dias[0]).toEqual(['Domingo', '0'])
    expect(dias[6]).toEqual(['Sábado', '6'])
    expect(dias).toHaveLength(7)
    expect((screen.getByLabelText('Día de la semana') as HTMLSelectElement).value).toBe('0')
    expect(screen.queryByLabelText('Día del mes')).toBeNull()
  })

  it('mensual muestra la hora y el día del mes de 1 a 28', () => {
    montar({ frecuencia: 'MENSUAL' })

    expect(screen.getByLabelText('Hora')).toBeTruthy()
    const dia = screen.getByLabelText('Día del mes') as HTMLInputElement
    expect(dia.type).toBe('number')
    expect([dia.min, dia.max, dia.value]).toEqual(['1', '28', '1'])
    expect(screen.queryByLabelText('Día de la semana')).toBeNull()
  })

  it('«Cada N horas» oculta la hora y muestra el intervalo de 1 a 23, 2 por defecto', () => {
    montar({ politica: 'TRANSACCIONAL', frecuencia: 'HORAS' })

    expect(screen.queryByLabelText('Hora')).toBeNull()
    const n = screen.getByLabelText('Cada cuántas horas') as HTMLInputElement
    expect([n.min, n.max, n.value]).toEqual(['1', '23', '2'])
    expect(screen.queryByLabelText('Día de la semana')).toBeNull()
    expect(screen.queryByLabelText('Día del mes')).toBeNull()
  })

  it('no menciona dumpfile', () => {
    montar()

    expect(document.body.textContent?.toLowerCase()).not.toContain('dumpfile')
  })

  it('notifica cada cambio con el valor completo', () => {
    const onChange = montar({ frecuencia: 'SEMANAL' })

    fireEvent.change(screen.getByLabelText('Política'), { target: { value: 'INCREMENTAL' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, frecuencia: 'SEMANAL', politica: 'INCREMENTAL' })

    fireEvent.change(screen.getByLabelText('Frecuencia'), { target: { value: 'MENSUAL' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, frecuencia: 'MENSUAL' })

    fireEvent.change(screen.getByLabelText('Hora'), { target: { value: '03:30' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, frecuencia: 'SEMANAL', hora: '03:30' })

    fireEvent.change(screen.getByLabelText('Día de la semana'), { target: { value: '6' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, frecuencia: 'SEMANAL', diaSemana: 6 })
  })

  it('notifica el día del mes y el intervalo como números', () => {
    let onChange = montar({ frecuencia: 'MENSUAL' })
    fireEvent.change(screen.getByLabelText('Día del mes'), { target: { value: '15' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, frecuencia: 'MENSUAL', diaMes: 15 })
    cleanup()

    onChange = montar({ politica: 'TRANSACCIONAL', frecuencia: 'HORAS' })
    fireEvent.change(screen.getByLabelText('Cada cuántas horas'), { target: { value: '6' } })
    expect(onChange).toHaveBeenLastCalledWith({
      ...PROGRAMACION_INICIAL,
      politica: 'TRANSACCIONAL',
      frecuencia: 'HORAS',
      cadaHoras: 6,
    })
  })

  it('al salir de Transaccional estando en «Cada N horas» la frecuencia vuelve a Diario', () => {
    const onChange = montar({ politica: 'TRANSACCIONAL', frecuencia: 'HORAS' })

    fireEvent.change(screen.getByLabelText('Política'), { target: { value: 'FULL' } })

    expect(onChange).toHaveBeenLastCalledWith({
      ...PROGRAMACION_INICIAL,
      politica: 'FULL',
      frecuencia: 'DIARIO',
    })
  })

  it('al salir de Transaccional con otra frecuencia la conserva', () => {
    const onChange = montar({ politica: 'TRANSACCIONAL', frecuencia: 'SEMANAL' })

    fireEvent.change(screen.getByLabelText('Política'), { target: { value: 'FULL' } })

    expect(onChange).toHaveBeenLastCalledWith({ ...PROGRAMACION_INICIAL, politica: 'FULL', frecuencia: 'SEMANAL' })
  })
})
