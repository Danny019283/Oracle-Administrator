import { useCallback, useEffect, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Respaldo = {
  directorio: string
  ruta: string
  base: string
  tipo: string
  estado: string
  archivos: { nombre: string; tamano: number }[]
  tamano: number
  fecha: string
}

const UNIDADES = ['B', 'KB', 'MB', 'GB']

function formatearTamano(bytes: number) {
  let valor = bytes
  let i = 0
  while (valor >= 1024 && i < UNIDADES.length - 1) {
    valor /= 1024
    i++
  }
  return i === 0 ? `${valor} B` : `${valor.toFixed(1)} ${UNIDADES[i]}`
}

export function ArchivosRespaldo({ token }: { token: string }) {
  const [respaldos, setRespaldos] = useState<Respaldo[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [advertencia, setAdvertencia] = useState<Aviso | null>(null)

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

  const eliminar = async (r: Respaldo) => {
    const url = `/directorios/${encodeURIComponent(r.directorio)}/respaldos/${encodeURIComponent(r.base)}`
    const res = await llamar<{ mensaje: string; advertencia: { explicacion: string; log: string } | null }>(
      token,
      url,
      undefined,
      'DELETE',
    )
    await cargar()
    setAdvertencia(null)
    if (!res.ok) return setAviso(res.aviso)
    setAviso({ tipo: 'ok', textos: [res.datos.mensaje] })
    const { advertencia } = res.datos
    if (advertencia) setAdvertencia({ tipo: 'error', textos: [advertencia.explicacion], detalle: advertencia.log })
  }

  return (
    <div className="panel">
      <h2>Respaldos</h2>
      <MostrarAviso aviso={aviso} />
      <MostrarAviso aviso={advertencia} />
      <Tabla
        titulo="Respaldos"
        columnas={[
          { titulo: 'Respaldo', valor: (r: Respaldo) => r.base },
          { titulo: 'Tipo', valor: (r: Respaldo) => r.tipo },
          { titulo: 'Estado', valor: (r: Respaldo) => r.estado },
          { titulo: 'Directorio', valor: (r: Respaldo) => r.directorio },
          { titulo: 'Ruta', valor: (r: Respaldo) => r.ruta },
          { titulo: 'Archivos', valor: (r: Respaldo) => r.archivos.map((a) => a.nombre).join(', ') },
          { titulo: 'Tamaño', valor: (r: Respaldo) => formatearTamano(r.tamano) },
          { titulo: 'Fecha', valor: (r: Respaldo) => new Date(r.fecha).toLocaleString('es') },
          {
            titulo: 'Acciones',
            valor: (r: Respaldo) => (
              <BotonConfirmar
                etiqueta={`Eliminar ${r.base}`}
                pregunta={`¿Eliminar el respaldo ${r.base}? Se borrarán sus archivos y su log.`}
                onConfirmar={() => void eliminar(r)}
              />
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
