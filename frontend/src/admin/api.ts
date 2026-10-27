import { expirarSesion } from '../sesion/sesion'

export type Aviso = { tipo: 'ok' | 'error'; textos: string[]; detalle?: string }

const cabeceras = (token: string) => ({ Authorization: `Bearer ${token}` })

const CODIGOS_DEL_PROXY = [502, 503, 504]

const avisoDeConexion = (codigo: string): Aviso => ({
  tipo: 'error',
  textos: [
    `No se pudo conectar con el servidor. Verifica que el backend esté en ejecución (código ${codigo})`,
  ],
})

// Convierte la respuesta de error del backend en un aviso para la pantalla:
// 422 trae la lista de errores, 404 un detalle y 500 la explicación de Oracle.
function avisoDeError(status: number, cuerpo: Record<string, unknown>): Aviso {
  if (Array.isArray(cuerpo.errores)) return { tipo: 'error', textos: cuerpo.errores as string[] }
  if (typeof cuerpo.detail === 'string') return { tipo: 'error', textos: [cuerpo.detail] }
  const textos = [cuerpo.mensaje, cuerpo.explicacion].filter(
    (t): t is string => typeof t === 'string' && t.length > 0,
  )
  return {
    tipo: 'error',
    textos: textos.length > 0 ? textos : [`El servidor respondió con el código ${status}`],
    detalle: typeof cuerpo.error === 'string' ? cuerpo.error : undefined,
  }
}

export type Respuesta<T> = { ok: true; datos: T } | { ok: false; aviso: Aviso }

export async function llamar<T>(
  token: string,
  url: string,
  cuerpo?: unknown,
): Promise<Respuesta<T>> {
  const opciones: RequestInit =
    cuerpo === undefined
      ? { headers: cabeceras(token) }
      : {
          method: 'POST',
          headers: { ...cabeceras(token), 'Content-Type': 'application/json' },
          body: JSON.stringify(cuerpo),
        }
  let r: Response
  try {
    r = await fetch(url, opciones)
  } catch {
    return { ok: false, aviso: avisoDeConexion('ERR_CONEXION') }
  }
  if (CODIGOS_DEL_PROXY.includes(r.status)) return { ok: false, aviso: avisoDeConexion(String(r.status)) }
  let datos: Record<string, unknown> = {}
  try {
    datos = await r.json()
  } catch {
    // respuesta sin JSON: se informa con el código
  }
  if (r.status === 401) expirarSesion()
  if (!r.ok) return { ok: false, aviso: avisoDeError(r.status, datos) }
  return { ok: true, datos: datos as T }
}
