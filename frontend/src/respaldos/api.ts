import { expirarSesion } from '../sesion/sesion'

export const cabeceras = (token: string) => ({ Authorization: `Bearer ${token}` })

export class ErrorConexion extends Error {
  codigo: string

  constructor(codigo: string) {
    super(codigo)
    this.codigo = codigo
  }
}

const CODIGOS_DEL_PROXY = [502, 503, 504]

export const avisoDeConexion = ({ codigo }: ErrorConexion) =>
  `No se pudo conectar con el servidor. Verifica que el backend esté en ejecución (código ${codigo})`

// Distingue un backend caído (sin respuesta o 502/503/504 del proxy) de una respuesta normal.
export async function pedir(url: string, opciones?: RequestInit) {
  let r: Response
  try {
    r = await fetch(url, opciones)
  } catch {
    throw new ErrorConexion('ERR_CONEXION')
  }
  if (CODIGOS_DEL_PROXY.includes(r.status)) throw new ErrorConexion(String(r.status))
  if (r.status === 401) expirarSesion()
  return { ok: r.ok, status: r.status, cuerpo: await r.json() }
}
