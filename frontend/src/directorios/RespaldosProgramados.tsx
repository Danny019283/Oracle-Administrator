import { useCallback, useEffect, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { MostrarAviso, Tabla } from '../admin/Avisos'

type Programacion = {
  id: number
  nombre: string
  politica: string
  frecuencia: string
  hora: string | null
  dia: number | null
  intervalo_horas: number | null
  directorio: string
  ruta_script: string
  ultima_ejecucion: string | null
  ultimo_resultado: string | null
}

const POLITICAS: Record<string, string> = { FULL: 'Full', INCREMENTAL: 'Incremental', TRANSACCIONAL: 'Transaccional' }
const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']

function describirFrecuencia(p: Programacion) {
  switch (p.frecuencia) {
    case 'DIARIO':
      return `Diario a las ${p.hora}`
    case 'SEMANAL':
      return `Semanal: ${DIAS[p.dia ?? 0]} a las ${p.hora}`
    case 'MENSUAL':
      return `Mensual: día ${p.dia} a las ${p.hora}`
    case 'HORAS':
      return `Cada ${p.intervalo_horas} horas`
    default:
      return p.frecuencia
  }
}

export function RespaldosProgramados({ token }: { token: string }) {
  const [programaciones, setProgramaciones] = useState<Programacion[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)

  const cargar = useCallback(async () => {
    const r = await llamar<{ programaciones: Programacion[] }>(token, '/respaldos/programados')
    if (!r.ok) return setAviso(r.aviso)
    setProgramaciones(r.datos.programaciones ?? [])
    setAviso(null)
  }, [token])

  useEffect(() => {
    void cargar()
  }, [cargar])

  return (
    <div className="panel">
      <h2>Respaldos programados</h2>
      <MostrarAviso aviso={aviso} />
      <Tabla
        titulo="Respaldos programados"
        columnas={[
          { titulo: 'Nombre', valor: (p: Programacion) => p.nombre },
          { titulo: 'Política', valor: (p: Programacion) => POLITICAS[p.politica] ?? p.politica },
          { titulo: 'Frecuencia', valor: describirFrecuencia },
          { titulo: 'Directorio', valor: (p: Programacion) => p.directorio },
          { titulo: 'Script', valor: (p: Programacion) => p.ruta_script },
          {
            titulo: 'Última ejecución',
            valor: (p: Programacion) => (p.ultima_ejecucion ? new Date(p.ultima_ejecucion).toLocaleString('es') : 'Nunca'),
          },
          { titulo: 'Último resultado', valor: (p: Programacion) => p.ultimo_resultado ?? '—' },
        ]}
        filas={programaciones}
        clave={(p) => String(p.id)}
        vacio="No hay respaldos programados"
      />
    </div>
  )
}
