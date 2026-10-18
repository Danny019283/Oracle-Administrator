import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { avisoDeConexion, ErrorConexion } from '../respaldos/api'
import { ErrorLogin, iniciarSesion, recordados, type DatosLogin } from './sesion'

const PUERTO_MAXIMO = 65535

type Campo = 'host' | 'puerto' | 'servicio' | 'usuario' | 'password'
type Errores = Partial<Record<Campo, string>>

const CAMPOS: { nombre: Campo; etiqueta: string; palabra: string; tipo: string; autoComplete?: string }[] = [
  { nombre: 'host', etiqueta: 'Host', palabra: 'host', tipo: 'text' },
  { nombre: 'puerto', etiqueta: 'Puerto', palabra: 'puerto', tipo: 'text' },
  { nombre: 'servicio', etiqueta: 'Servicio', palabra: 'servicio', tipo: 'text' },
  { nombre: 'usuario', etiqueta: 'Usuario', palabra: 'usuario', tipo: 'text', autoComplete: 'username' },
  { nombre: 'password', etiqueta: 'Contraseña', palabra: 'contraseña', tipo: 'password', autoComplete: 'current-password' },
]

const INICIAL: DatosLogin = { host: '', puerto: '', servicio: '', usuario: '', password: '', sysdba: false }

function validar(datos: DatosLogin): Errores {
  const errores: Errores = {}
  for (const { nombre, palabra } of CAMPOS) {
    if (!datos[nombre].trim()) errores[nombre] = `El campo ${palabra} es obligatorio`
  }
  if (!errores.puerto) {
    if (!/^\d+$/.test(datos.puerto)) errores.puerto = 'El puerto debe ser un número'
    else if (Number(datos.puerto) < 1 || Number(datos.puerto) > PUERTO_MAXIMO) {
      errores.puerto = `El puerto debe estar entre 1 y ${PUERTO_MAXIMO}`
    }
  }
  return errores
}

function mensajesDe(error: unknown): string[] {
  if (error instanceof ErrorLogin) return error.errores.length ? error.errores : [error.mensaje]
  if (error instanceof ErrorConexion) return [avisoDeConexion(error)]
  return ['No se pudo iniciar sesión']
}

// Diálogo bloqueante: sin cerrar, sin Escape y con el foco atrapado hasta iniciar sesión.
export function ModalLogin() {
  const [datos, setDatos] = useState<DatosLogin>(() => ({ ...INICIAL, ...recordados() }))
  const [errores, setErrores] = useState<Errores>({})
  const [enviando, setEnviando] = useState(false)
  const [aviso, setAviso] = useState<string[]>([])
  const idTitulo = useId()
  const idBase = useId()
  const formulario = useRef<HTMLFormElement>(null)
  const campos = useRef<Partial<Record<Campo, HTMLInputElement | null>>>({})

  useEffect(() => {
    campos.current.host?.focus()
  }, [])

  const cambiar = (nombre: Campo, valor: string) => setDatos((actuales) => ({ ...actuales, [nombre]: valor }))

  const alPulsarTecla = (evento: KeyboardEvent) => {
    if (evento.key === 'Escape') {
      evento.preventDefault()
      return
    }
    if (evento.key !== 'Tab') return
    const enfocables = formulario.current?.querySelectorAll<HTMLElement>('input:not([disabled]), button:not([disabled])')
    if (!enfocables?.length) return
    const primero = enfocables[0]
    const ultimo = enfocables[enfocables.length - 1]
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault()
      ultimo.focus()
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault()
      primero.focus()
    }
  }

  const alEnviar = (evento: FormEvent) => {
    evento.preventDefault()
    const limpios: DatosLogin = {
      ...datos,
      host: datos.host.trim(),
      puerto: datos.puerto.trim(),
      servicio: datos.servicio.trim(),
      usuario: datos.usuario.trim(),
    }
    const encontrados = validar(limpios)
    setErrores(encontrados)
    const primero = CAMPOS.find(({ nombre }) => encontrados[nombre])
    if (primero) {
      campos.current[primero.nombre]?.focus()
      return
    }
    setAviso([])
    setEnviando(true)
    iniciarSesion(limpios)
      .catch((error) => {
        setAviso(mensajesDe(error))
        cambiar('password', '')
        campos.current.password?.focus()
      })
      .finally(() => setEnviando(false))
  }

  return (
    <div className="modal-fondo">
      <div role="dialog" aria-modal="true" aria-labelledby={idTitulo} className="modal" onKeyDown={alPulsarTecla}>
        <h1 id={idTitulo}>Iniciar sesión</h1>
        <p className="apoyo">Ingresa los datos de conexión y las credenciales de tu usuario de Oracle.</p>

        {aviso.length > 0 && (
          <div role="alert" className="aviso error">
            {aviso.map((mensaje) => (
              <p key={mensaje}>{mensaje}</p>
            ))}
          </div>
        )}

        <form ref={formulario} onSubmit={alEnviar} noValidate>
          {CAMPOS.map(({ nombre, etiqueta, tipo, autoComplete }) => {
            const idError = `${idBase}-${nombre}`
            return (
              <div className="campo-login" key={nombre}>
                <label className="campo">
                  {etiqueta}
                  <input
                    ref={(el) => {
                      campos.current[nombre] = el
                    }}
                    type={tipo}
                    value={datos[nombre]}
                    onChange={(e) => cambiar(nombre, e.target.value)}
                    autoComplete={autoComplete}
                    aria-invalid={errores[nombre] ? true : undefined}
                    aria-describedby={errores[nombre] ? idError : undefined}
                  />
                </label>
                {errores[nombre] && (
                  <p className="error-campo" id={idError}>
                    {errores[nombre]}
                  </p>
                )}
              </div>
            )
          })}

          <label className="opcion">
            <input
              type="checkbox"
              checked={datos.sysdba}
              onChange={(e) => setDatos((actuales) => ({ ...actuales, sysdba: e.target.checked }))}
            />
            Iniciar como SYSDBA
          </label>

          <button type="submit" className="accion" disabled={enviando}>
            {enviando ? 'Iniciando sesión…' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}
