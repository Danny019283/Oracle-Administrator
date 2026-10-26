import { useId } from 'react'

export type Directorio = { nombre: string; ruta: string }

type Props = {
  directorios: Directorio[]
  directorio: string
  alElegirDirectorio: (directorio: string) => void
  nombre: string
  alCambiarNombre: (nombre: string) => void
  etiquetaNombre: string
  ayudaNombre: string
}

export function FormularioDestino({
  directorios,
  directorio,
  alElegirDirectorio,
  nombre,
  alCambiarNombre,
  etiquetaNombre,
  ayudaNombre,
}: Props) {
  const idAyuda = useId()

  return (
    <div className="panel">
      <h2>Destino</h2>
      <label className="campo">
        Directorio
        <select value={directorio} onChange={(e) => alElegirDirectorio(e.target.value)}>
          <option value="">Selecciona un directorio</option>
          {directorios.map((d) => (
            <option key={d.nombre} value={d.nombre}>
              {d.nombre} ({d.ruta})
            </option>
          ))}
        </select>
      </label>

      <label className="campo">
        {etiquetaNombre}
        <input
          value={nombre}
          onChange={(e) => alCambiarNombre(e.target.value)}
          aria-describedby={idAyuda}
        />
      </label>
      <p className="ayuda" id={idAyuda}>
        {ayudaNombre}
      </p>
    </div>
  )
}
