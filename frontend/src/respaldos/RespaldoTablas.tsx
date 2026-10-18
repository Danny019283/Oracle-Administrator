import { useEffect, useState } from 'react'

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

export function RespaldoTablas({ credenciales }: Props) {
  const [tablas, setTablas] = useState<string[]>([])
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [seleccionadas, setSeleccionadas] = useState<string[]>([])
  const [directorio, setDirectorio] = useState('')
  const [nombre, setNombre] = useState('')
  const [errorTablas, setErrorTablas] = useState<string | null>(null)
  const [errorDirectorios, setErrorDirectorios] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)

  useEffect(() => {
    const headers = cabeceras(credenciales)

    fetch('/respaldos/tablas', { headers })
      .then(async (r) => {
        const cuerpo = await r.json()
        if (r.ok) setTablas(cuerpo.tablas)
        else setErrorTablas(cuerpo.detail)
      })
      .catch(() => {})

    fetch('/respaldos/directorios', { headers })
      .then(async (r) => {
        const cuerpo = await r.json()
        if (r.ok) setDirectorios(cuerpo.directorios)
        else setErrorDirectorios(cuerpo.detail)
      })
      .catch(() => {})
  }, [credenciales])

  const todasMarcadas = tablas.length > 0 && seleccionadas.length === tablas.length

  const alternar = (tabla: string) =>
    setSeleccionadas((actuales) =>
      actuales.includes(tabla) ? actuales.filter((t) => t !== tabla) : [...actuales, tabla],
    )

  const respaldar = async () => {
    setResultado(null)
    try {
      const r = await fetch('/respaldos/tablas', {
        method: 'POST',
        headers: { ...cabeceras(credenciales), 'Content-Type': 'application/json' },
        body: JSON.stringify({ tablas: seleccionadas, directorio, nombre }),
      })
      const cuerpo = await r.json()
      if (r.ok && cuerpo.dmp) setResultado({ tipo: 'ok', dmp: cuerpo.dmp, log: cuerpo.log })
      else if (r.status === 422) setResultado({ tipo: 'error', mensajes: cuerpo.errores })
      else if (!r.ok) {
        setResultado({ tipo: 'error', mensajes: [cuerpo.mensaje], log: cuerpo.log })
      }
    } catch {
      // sin respuesta del servidor: no hay nada que mostrar todavía
    }
  }

  const avisos = [errorTablas, errorDirectorios].filter((a): a is string => a !== null)
  const mensajes = [...avisos, ...(resultado?.tipo === 'error' ? resultado.mensajes : [])]

  return (
    <section>
      <h1>Respaldar tablas</h1>

      {mensajes.length > 0 && (
        <div role="alert">
          {mensajes.map((mensaje) => (
            <p key={mensaje}>{mensaje}</p>
          ))}
          {resultado?.tipo === 'error' && resultado.log && <pre>{resultado.log}</pre>}
        </div>
      )}
      {resultado?.tipo === 'ok' && (
        <p role="status">
          Respaldo creado: {resultado.dmp} (log: {resultado.log})
        </p>
      )}

      <label>
        <input
          type="checkbox"
          checked={todasMarcadas}
          onChange={() => setSeleccionadas(todasMarcadas ? [] : tablas)}
        />
        Seleccionar todas
      </label>
      <ul>
        {tablas.map((tabla) => (
          <li key={tabla}>
            <label>
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

      <label>
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

      <label>
        Nombre del dumpfile
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
      </label>

      <button type="button" onClick={respaldar}>
        Respaldar
      </button>
    </section>
  )
}
