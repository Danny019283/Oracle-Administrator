import type { Credenciales } from './api'
import { RespaldoObjetos, type TipoObjeto } from './RespaldoObjetos'

const SCHEMAS: TipoObjeto = {
  recurso: 'schemas',
  titulo: 'Respaldar schemas',
  encabezadoLista: 'Schemas',
  descripcion: 'Elige los schemas, el directorio de destino y el nombre del respaldo.',
  seleccionarTodos: 'Seleccionar todos',
}

export function RespaldoSchemas({ credenciales }: { credenciales: Credenciales }) {
  return <RespaldoObjetos credenciales={credenciales} tipo={SCHEMAS} />
}
