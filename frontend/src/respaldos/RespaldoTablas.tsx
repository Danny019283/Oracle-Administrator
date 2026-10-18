import { useEffect, useId, useRef, useState } from 'react'

export type Credenciales = {
  usuario: string
  password: string
  servicio: string
}

type Directorio = { nombre: string; ruta: string }

type Resultado =
  | { tipo: 'ok'; dmp: string; log: string }
  | { tipo: 'error'; mensajes: string[]; log?: string }

type Props = {
  credenciales: Credenciales
}

const cabeceras = ({ usuario, password, servicio }: Credenciales) => ({
  'X-Oracle-User': usuario,
  'X-Oracle-Password': password,
  'X-Oracle-Service': servicio,
})

class ErrorConexion extends Error {
  codigo: string

  constructor(codigo: string) {
    super(codigo)
    this.codigo = codigo
  }
}

const CODIGOS_DEL_PROXY = [502, 503, 504]

const avisoDeConexion = ({ codigo }: ErrorConexion) =>
  `No se pudo conectar con el servidor. Verifica que el backend esté en ejecución (código ${codigo})`

// Distingue un backend caído (sin respuesta o 502/503/504 del proxy) de una respuesta normal.
async function pedir(url: string, opciones?: RequestInit) {
  let r: Response
  try {
    r = await fetch(url, opciones)
  } catch {
    throw new ErrorConexion('ERR_CONEXION')
  }
  if (CODIGOS_DEL_PROXY.includes(r.status)) throw new ErrorConexion(String(r.status))
  return { ok: r.ok, status: r.status, cuerpo: await r.json() }
}

export function RespaldoTablas({ credenciales }: Props) {
  const [tablas, setTablas] = useState<string[]>([])
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [seleccionadas, setSeleccionadas] = useState<string[]>([])
  const [directorio, setDirectorio] = useState('')
  const [nombre, setNombre] = useState('')
  const [errorTablas, setErrorTablas] = useState<string | null>(null)
  const [errorDirectorios, setErrorDirectorios] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [errorConexion, setErrorConexion] = useState<string | null>(null)
  const ayudaNombre = useId()
  const encabezado = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    const headers = cabeceras(credenciales)
    const alFallarLaConexion = (error: unknown) => {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    }

    pedir('/respaldos/tablas', { headers })
      .then(({ ok, cuerpo }) => {
        if (ok) setTablas(cuerpo.tablas)
        else setErrorTablas(cuerpo.detail)
      })
      .catch(alFallarLaConexion)

    pedir('/respaldos/directorios', { headers })
      .then(({ ok, cuerpo }) => {
        if (ok) setDirectorios(cuerpo.directorios)
        else setErrorDirectorios(cuerpo.detail)
      })
      .catch(alFallarLaConexion)
  }, [credenciales])

  const todasMarcadas = tablas.length > 0 && seleccionadas.length === tablas.length

  const alternar = (tabla: string) =>
    setSeleccionadas((actuales) =>
      actuales.includes(tabla) ? actuales.filter((t) => t !== tabla) : [...actuales, tabla],
    )

  const respaldar = async () => {
    setResultado(null)
    setErrorConexion(null)
    try {
      const { ok, status, cuerpo } = await pedir('/respaldos/tablas', {
        method: 'POST',
        headers: { ...cabeceras(credenciales), 'Content-Type': 'application/json' },
        body: JSON.stringify({ tablas: seleccionadas, directorio, nombre }),
      })
      if (ok && cuerpo.dmp) setResultado({ tipo: 'ok', dmp: cuerpo.dmp, log: cuerpo.log })
      else if (status === 422) setResultado({ tipo: 'error', mensajes: cuerpo.errores })
      else if (!ok) {
        const mensajes = [cuerpo.mensaje, cuerpo.explicacion].filter(Boolean)
        setResultado({ tipo: 'error', mensajes, log: cuerpo.log })
      }
    } catch (error) {
      if (error instanceof ErrorConexion) setErrorConexion(avisoDeConexion(error))
    }
  }

  const avisos = [errorConexion, errorTablas, errorDirectorios].filter(
    (a): a is string => a !== null,
  )
  const mensajes = [...avisos, ...(resultado?.tipo === 'error' ? resultado.mensajes : [])]

  // El botón queda al final de la página y los avisos arriba: se llevan a la vista.
  useEffect(() => {
    if (resultado) encabezado.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [resultado])

  return (
    <section className="vista">
      <h1 ref={encabezado}>Respaldar tablas</h1>
      <p className="apoyo">Elige las tablas, el directorio de destino y el nombre del respaldo.</p>

      {mensajes.length > 0 && (
        <div role="alert" className="aviso error">
          {mensajes.map((mensaje) => (
            <p key={mensaje}>{mensaje}</p>
          ))}
          {resultado?.tipo === 'error' && resultado.log && <pre>{resultado.log}</pre>}
        </div>
      )}
      {resultado?.tipo === 'ok' && (
        <p role="status" className="aviso exito">
          Respaldo creado: {resultado.dmp} (log: {resultado.log})
        </p>
      )}

      <div className="panel">
        <h2>Tablas</h2>
        <label className="opcion todas">
          <input
            type="checkbox"
            checked={todasMarcadas}
            onChange={() => setSeleccionadas(todasMarcadas ? [] : tablas)}
          />
          Seleccionar todas
        </label>
        <ul className="opciones">
          {tablas.map((tabla) => (
            <li key={tabla}>
              <label className="opcion">
                <input
                  type="checkbox"
                  checked={seleccionadas.includes(tabla)}
                  onChange={() => alternar(tabla)}
                />
                {tabla}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>Destino</h2>
        <label className="campo">
          Directorio
          <select value={directorio} onChange={(e) => setDirectorio(e.target.value)}>
            <option value="">Selecciona un directorio</option>
            {directorios.map((d) => (
              <option key={d.nombre} value={d.nombre}>
                {d.nombre} ({d.ruta})
              </option>
            ))}
          </select>
        </label>

        <label className="campo">
          Nombre del dumpfile
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            aria-describedby={ayudaNombre}
          />
        </label>
        <p className="ayuda" id={ayudaNombre}>
          Se agrega la fecha y la hora al nombre. Usa letras, números, guion y guion bajo.
        </p>
      </div>

      <button type="button" className="accion" onClick={respaldar}>
        Respaldar
      </button>
    </section>
  )
}
