import { useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso } from '../admin/api'
import { MostrarAviso, Tabla } from '../admin/Avisos'

type Directorio = { nombre: string; ruta: string }

export function Directorios({ token }: { token: string }) {
  const [directorios, setDirectorios] = useState<Directorio[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)

  useEffect(() => {
    void llamar<{ directorios: Directorio[]; ejemplos_ruta: string[] }>(token, '/directorios').then((r) => {
      if (r.ok) setDirectorios(r.datos.directorios)
      else setAviso(r.aviso)
    })
  }, [token])

  return (
    <section className="vista">
      <div className="encabezado-modulo">
        <div>
          <h1>Administración de archivos de respaldos y directorios</h1>
          <p className="apoyo">Consulta los directorios de Oracle donde se guardan los respaldos.</p>
        </div>
        <button type="button" className="boton principal">
          Crear directorio
        </button>
      </div>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <h2>Directorios</h2>
        <Tabla
          titulo="Directorios"
          columnas={[
            { titulo: 'Nombre', valor: (d: Directorio) => d.nombre },
            { titulo: 'Ruta', valor: (d: Directorio) => d.ruta },
          ]}
          filas={directorios}
          clave={(d) => d.nombre}
          vacio="No hay directorios para mostrar"
        />
      </div>
    </section>
  )
}
