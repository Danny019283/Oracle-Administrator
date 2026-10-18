import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RespaldoTablas } from './RespaldoTablas'

const CREDENCIALES = { usuario: 'HR', password: 's3creta!', servicio: 'XEPDB1' }

const respuesta = (cuerpo: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => cuerpo,
})

type Escenario = {
  tablas?: ReturnType<typeof respuesta>
  directorios?: ReturnType<typeof respuesta>
  respaldo?: ReturnType<typeof respuesta>
}

const montar = ({ tablas, directorios, respaldo }: Escenario = {}) => {
  const porDefecto = {
    tablas: respuesta({ tablas: ['CLIENTES'] }),
    directorios: respuesta({ directorios: [{ nombre: 'RESPALDO', ruta: '/opt/oracle/Respaldos' }] }),
    respaldo: respuesta({ dmp: 'ventas_20261017_153045.dmp', log: 'ventas_20261017_153045.log' }),
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, opciones?: { method?: string }) => {
      if (opciones?.method === 'POST') return respaldo ?? porDefecto.respaldo
      if (url === '/respaldos/tablas') return tablas ?? porDefecto.tablas
      return directorios ?? porDefecto.directorios
    }),
  )
  render(<RespaldoTablas credenciales={CREDENCIALES} />)
}

const respaldar = async () => {
  await screen.findByRole('option', { name: /RESPALDO/ })
  fireEvent.click(screen.getByRole('button', { name: 'Respaldar' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('resultado del respaldo de tablas', () => {
  it('al terminar bien informa los nombres del .dmp y del .log', async () => {
    montar()

    await respaldar()

    const estado = await screen.findByRole('status')
    expect(estado.textContent).toContain('ventas_20261017_153045.dmp')
    expect(estado.textContent).toContain('ventas_20261017_153045.log')
  })

  it('muestra cada dato faltante cuando la solicitud es inválida', async () => {
    montar({
      respaldo: respuesta(
        {
          errores: [
            'Debes seleccionar al menos una tabla',
            'Debes elegir un directorio',
            'Debes ingresar un nombre de dumpfile',
          ],
        },
        422,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('Debes seleccionar al menos una tabla')
    expect(alerta.textContent).toContain('Debes elegir un directorio')
    expect(alerta.textContent).toContain('Debes ingresar un nombre de dumpfile')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('si no hay tablas lo avisa con el mensaje del servidor', async () => {
    montar({ tablas: respuesta({ detail: 'No hay tablas en el schema' }, 404) })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('No hay tablas en el schema')
  })

  it('si no hay DIRECTORY lo avisa y sugiere crear uno', async () => {
    montar({
      directorios: respuesta(
        { detail: 'No hay directorios disponibles. Debes crear uno desde esta pantalla para poder respaldar' },
        404,
      ),
    })

    const alerta = await screen.findByRole('alert')

    expect(alerta.textContent).toContain('No hay directorios disponibles')
    expect(alerta.textContent).toContain('crear uno')
  })

  it('si expdp falla muestra el error y el contenido del log', async () => {
    montar({
      respaldo: respuesta(
        {
          mensaje: 'El respaldo falló: expdp terminó con código 5',
          log: 'ORA-27038: el archivo creado ya existe',
        },
        500,
      ),
    })

    await respaldar()

    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('expdp terminó con código 5')
    expect(alerta.textContent).toContain('ORA-27038')
    expect(screen.queryByRole('status')).toBeNull()
  })
})
