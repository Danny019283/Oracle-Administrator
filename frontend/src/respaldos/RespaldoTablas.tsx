import { RespaldoObjetos, type TipoObjeto } from './RespaldoObjetos'

const TABLAS: TipoObjeto = {
  recurso: 'tablas',
  titulo: 'Respaldar tablas',
  encabezadoLista: 'Tablas',
  descripcion: 'Elige las tablas, el directorio de destino y el nombre del respaldo.',
  seleccionarTodos: 'Seleccionar todas',
}

export function RespaldoTablas({ token }: { token: string }) {
  return <RespaldoObjetos token={token} tipo={TABLAS} />
}
