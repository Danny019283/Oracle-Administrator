import { ErrorConexion } from '../respaldos/api'

export type DatosLogin = {
  host: string
  puerto: string
  servicio: string
  usuario: string
  password: string
  sysdba: boolean
}

export type Sesion = {
  token: string
  usuario: string
  sysdba: boolean
}

export type Recordados = Pick<DatosLogin, 'host' | 'puerto' | 'servicio' | 'usuario'>

export type EventoSesion =
  | { estado: 'activa'; sesion: Sesion }
  | { estado: 'cerrada' }
  | { estado: 'expirada' }

type Escucha = (evento: EventoSesion) => void

const CLAVE_RECORDADOS = 'oracle.conexion'

// El token vive solo en memoria: recargar la página obliga a iniciar sesión de nuevo.
let actual: Sesion | null = null
const escuchas = new Set<Escucha>()

// Fallo de login con respuesta de la API (credenciales, privilegio, Oracle inalcanzable, datos inválidos).
export class ErrorLogin extends Error {
  status: number
  mensaje: string
  codigo: string | null
  errores: string[]

  constructor(status: number, cuerpo: { mensaje?: string; codigo?: string | null; errores?: string[] }) {
    super(cuerpo.mensaje ?? cuerpo.errores?.join('; ') ?? 'No se pudo iniciar sesión')
    this.status = status
    this.mensaje = this.message
    this.codigo = cuerpo.codigo ?? null
    this.errores = cuerpo.errores ?? []
  }
}

const avisar = (evento: EventoSesion) => escuchas.forEach((escucha) => escucha(evento))

export const sesionActual = () => actual

export const cabeceraAutorizacion = (): Record<string, string> =>
  actual ? { Authorization: `Bearer ${actual.token}` } : {}

export function alCambiarSesion(escucha: Escucha) {
  escuchas.add(escucha)
  return () => {
    escuchas.delete(escucha)
  }
}

export function recordados(): Recordados | null {
  try {
    const guardado = localStorage.getItem(CLAVE_RECORDADOS)
    return guardado ? (JSON.parse(guardado) as Recordados) : null
  } catch {
    return null
  }
}

function recordar({ host, puerto, servicio, usuario }: DatosLogin) {
  try {
    localStorage.setItem(CLAVE_RECORDADOS, JSON.stringify({ host, puerto, servicio, usuario }))
  } catch {
    // Sin almacenamiento disponible el login sigue funcionando; solo no se precargan los datos.
  }
}

// Distingue la respuesta de la API (siempre JSON) de un backend caído (sin respuesta o error del proxy).
async function leerCuerpo(r: Response) {
  try {
    return await r.json()
  } catch {
    throw new ErrorConexion(String(r.status))
  }
}

export async function iniciarSesion(datos: DatosLogin): Promise<Sesion> {
  let r: Response
  try {
    r = await fetch('/sesion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    })
  } catch {
    throw new ErrorConexion('ERR_CONEXION')
  }
  const cuerpo = await leerCuerpo(r)
  if (!r.ok) {
    if (!cuerpo?.mensaje && !cuerpo?.errores) throw new ErrorConexion(String(r.status))
    throw new ErrorLogin(r.status, cuerpo)
  }

  actual = { token: cuerpo.token, usuario: cuerpo.usuario, sysdba: cuerpo.sysdba }
  recordar(datos)
  avisar({ estado: 'activa', sesion: actual })
  return actual
}

export async function cerrarSesion(): Promise<void> {
  if (!actual) return
  const cabecera = cabeceraAutorizacion()
  actual = null
  avisar({ estado: 'cerrada' })
  try {
    await fetch('/sesion', { method: 'DELETE', headers: cabecera })
  } catch {
    // La sesión local ya se descartó; la del backend expira sola por inactividad.
  }
}

// La API respondió 401: el token ya no vale.
export function expirarSesion() {
  if (!actual) return
  actual = null
  avisar({ estado: 'expirada' })
}
