import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RespaldoTablas } from './RespaldoTablas'

const TOKEN = 'tok-123'

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

const EXPLICACION = 'Ya existe un archivo de respaldo con ese nombre en el directorio'
const LOG = 'ORA-31641: no se puede crear el archivo\nORA-27038: el archivo creado ya existe'

const montarConFallo = (cuerpo: Record<string, string>) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, opciones?: { method?: string }) => {
      if (opciones?.method === 'POST') return respuesta(cuerpo, 500)
      if (url === '/respaldos/tablas') return respuesta({ tablas: ['CLIENTES'] })
      return respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] })
    }),
  )
  render(<RespaldoTablas token={TOKEN} />)
}

const respaldar = async () => {
  await screen.findByRole('option', { name: /RESPALDO/ })
  fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
  return screen.findByRole('alert')
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('explicación del fallo de expdp', () => {
  it('muestra el mensaje, la explicación en lenguaje natural y el error de Oracle del log', async () => {
    montarConFallo({
      mensaje: 'El respaldo falló: expdp terminó con código 5',
      explicacion: EXPLICACION,
      log: LOG,
    })

    const alerta = await respaldar()

    expect(alerta.textContent).toContain('El respaldo falló: expdp terminó con código 5')
    expect(alerta.textContent).toContain(EXPLICACION)
    expect(alerta.textContent).toContain('ORA-27038')
  })

  it('muestra la explicación antes que el log completo', async () => {
    montarConFallo({
      mensaje: 'El respaldo falló: expdp terminó con código 5',
      explicacion: EXPLICACION,
      log: LOG,
    })

    const alerta = await respaldar()

    const texto = alerta.textContent ?? ''
    expect(texto.indexOf(EXPLICACION)).toBeGreaterThanOrEqual(0)
    expect(texto.indexOf(EXPLICACION)).toBeLessThan(texto.indexOf('ORA-31641'))
  })

  it('el log sigue disponible en un bloque aparte', async () => {
    montarConFallo({
      mensaje: 'El respaldo falló: expdp terminó con código 5',
      explicacion: EXPLICACION,
      log: LOG,
    })

    const alerta = await respaldar()

    const bloque = alerta.querySelector('pre')
    expect(bloque?.textContent).toBe(LOG)
  })
})
