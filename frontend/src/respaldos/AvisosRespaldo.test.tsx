import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { AvisoError, AvisoExito, BarraRespaldando } from './AvisosRespaldo'

afterEach(cleanup)

describe('avisos del respaldo', () => {
  it('el aviso de error es una alerta con cada mensaje y el log', () => {
    render(<AvisoError mensajes={['El respaldo falló', 'Explicación']} log="ORA-27038: ya existe" />)

    const alerta = screen.getByRole('alert')
    expect(alerta.textContent).toContain('El respaldo falló')
    expect(alerta.textContent).toContain('Explicación')
    expect(alerta.querySelector('pre')?.textContent).toBe('ORA-27038: ya existe')
  })

  it('el aviso de error no se muestra sin mensajes', () => {
    render(<AvisoError mensajes={[]} />)

    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('el aviso de error no muestra el log cuando no lo hay', () => {
    const { container } = render(<AvisoError mensajes={['Falta el nombre']} />)

    expect(container.querySelector('pre')).toBeNull()
  })

  it('el aviso de éxito es un estado con su contenido', () => {
    render(<AvisoExito>Respaldo creado: x.dmp</AvisoExito>)

    expect(screen.getByRole('status').textContent).toBe('Respaldo creado: x.dmp')
  })

  it('la barra anuncia que se está respaldando', () => {
    render(<BarraRespaldando />)

    expect(screen.getByText('Respaldando...')).toBeTruthy()
  })
})
