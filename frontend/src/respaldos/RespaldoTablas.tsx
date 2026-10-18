import type { Credenciales } from './api'
import { RespaldoObjetos, type TipoObjeto } from './RespaldoObjetos'

const TABLAS: TipoObjeto = {
  recurso: 'tablas',
  titulo: 'Respaldar tablas',
  encabezadoLista: 'Tablas',
  descripcion: 'Elige las tablas, el directorio de destino y el nombre del respaldo.',
  seleccionarTodos: 'Seleccionar todas',
}

export function RespaldoTablas({ credenciales }: { credenciales: Credenciales }) {
  return <RespaldoObjetos credenciales={credenciales} tipo={TABLAS} />
}
