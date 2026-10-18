import { useEffect, useState } from 'react'

export type Credenciales = {
  usuario: string
  password: string
  servicio: string
}

type Directorio = { nombre: string; ruta: string }

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

  useEffect(() => {
    const headers = cabeceras(credenciales)

    fetch('/respaldos/tablas', { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((cuerpo) => cuerpo && setTablas(cuerpo.tablas))
      .catch(() => {})

    fetch('/respaldos/directorios', { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((cuerpo) => cuerpo && setDirectorios(cuerpo.directorios))
      .catch(() => {})
  }, [credenciales])

  const todasMarcadas = tablas.length > 0 && seleccionadas.length === tablas.length

  const alternar = (tabla: string) =>
    setSeleccionadas((actuales) =>
      actuales.includes(tabla) ? actuales.filter((t) => t !== tabla) : [...actuales, tabla],
    )

  const respaldar = () =>
    fetch('/respaldos/tablas', {
      method: 'POST',
      headers: { ...cabeceras(credenciales), 'Content-Type': 'application/json' },
      body: JSON.stringify({ tablas: seleccionadas, directorio, nombre }),
    }).catch(() => {})

  return (
    <section>
      <h1>Respaldar tablas</h1>

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
