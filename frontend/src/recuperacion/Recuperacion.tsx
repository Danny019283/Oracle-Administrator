import { useCallback, useEffect, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { MostrarAviso, Tabla } from '../admin/Avisos'

type Respaldo = {
  directorio: string
  base: string
  tipo: string
  estado: string
  fecha: string
}

export function Recuperacion({ token }: { token: string }) {
  const [respaldos, setRespaldos] = useState<Respaldo[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)

  const cargar = useCallback(async () => {
    const r = await llamar<{ respaldos: Respaldo[]; avisos: string[] }>(token, '/directorios/respaldos')
    if (!r.ok) return setAviso(r.aviso)
    const { respaldos = [], avisos = [] } = r.datos
    setRespaldos(respaldos)
    setAviso(avisos.length > 0 ? { tipo: 'error', textos: avisos } : null)
  }, [token])

  useEffect(() => {
    void cargar()
  }, [cargar])

  return (
    <div className="panel">
      <h1>Recuperación de respaldos</h1>
      <MostrarAviso aviso={aviso} />
      <Tabla
        titulo="Respaldos"
        columnas={[
          { titulo: 'Respaldo', valor: (r: Respaldo) => r.base },
          { titulo: 'Tipo', valor: (r: Respaldo) => r.tipo },
          { titulo: 'Estado', valor: (r: Respaldo) => r.estado },
          { titulo: 'Directorio', valor: (r: Respaldo) => r.directorio },
          { titulo: 'Fecha', valor: (r: Respaldo) => new Date(r.fecha).toLocaleString('es') },
          {
            titulo: 'Acciones',
            valor: (r: Respaldo) => (
              <button type="button" className="boton" aria-label={`Recuperar ${r.base}`}>
                Recuperar
              </button>
            ),
          },
        ]}
        filas={respaldos}
        clave={(r) => `${r.directorio}/${r.base}`}
        vacio="No hay respaldos para mostrar"
      />
    </div>
  )
}
