import { useCallback, useEffect, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { MostrarAviso, Tabla } from '../admin/Avisos'
import { avisoDeConexion, cabeceras, ErrorConexion, pedir } from '../respaldos/api'

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

const FALTA = '—'

function describirFrecuencia(p: Programacion) {
  const hora = p.hora || FALTA
  const dia = p.dia ?? FALTA
  switch (p.frecuencia) {
    case 'DIARIO':
      return `Diario a las ${hora}`
    case 'SEMANAL':
      return `Semanal: ${p.dia != null && DIAS[p.dia] ? DIAS[p.dia] : FALTA} a las ${hora}`
    case 'MENSUAL':
      return `Mensual: día ${dia} a las ${hora}`
    case 'HORAS':
      return p.intervalo_horas === 1 ? 'Cada 1 hora' : `Cada ${p.intervalo_horas ?? FALTA} horas`
    default:
      return p.frecuencia
  }
}

// Los errores traen `detail` (404/409/403) o `mensaje` + `explicacion` (+ `log` de RMAN).
function avisoDeFallo(status: number, cuerpo: Record<string, unknown>): Aviso {
  const textos =
    typeof cuerpo.detail === 'string'
      ? [cuerpo.detail]
      : [cuerpo.mensaje, cuerpo.explicacion].filter((t): t is string => typeof t === 'string' && t.length > 0)
  return {
    tipo: 'error',
    textos: textos.length > 0 ? textos : [`El servidor respondió con el código ${status}`],
    detalle: typeof cuerpo.log === 'string' && cuerpo.log ? cuerpo.log : undefined,
  }
}

export function RespaldosProgramados({ token }: { token: string }) {
  const [programaciones, setProgramaciones] = useState<Programacion[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [log, setLog] = useState('')
  const [ejecutando, setEjecutando] = useState<number | null>(null)

  const cargar = useCallback(async () => {
    const r = await llamar<{ programaciones: Programacion[] }>(token, '/respaldos/programados')
    if (!r.ok) return setAviso(r.aviso)
    setProgramaciones(r.datos.programaciones ?? [])
    setAviso(null)
  }, [token])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const ejecutar = async (id: number) => {
    setAviso(null)
    setLog('')
    setEjecutando(id)
    let resultado: Aviso | null = null
    let logOk = ''
    let recargar = false
    try {
      const r = await pedir(`/respaldos/programados/${id}/ejecutar`, { method: 'POST', headers: cabeceras(token) })
      if (r.ok) {
        resultado = { tipo: 'ok', textos: [r.cuerpo.mensaje ?? 'Respaldo ejecutado'] }
        logOk = r.cuerpo.log ?? ''
        recargar = true
      } else if (r.status !== 401) {
        resultado = avisoDeFallo(r.status, r.cuerpo)
        recargar = r.status === 404 || r.status === 500
      }
    } catch (error) {
      if (error instanceof ErrorConexion) resultado = { tipo: 'error', textos: [avisoDeConexion(error)] }
    }
    setEjecutando(null)
    if (recargar) await cargar()
    setAviso(resultado)
    setLog(logOk)
  }

  return (
    <div className="panel">
      <h2>Respaldos programados</h2>
      <MostrarAviso aviso={aviso} />
      {log && <pre>{log}</pre>}
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
          {
            titulo: 'Acciones',
            valor: (p: Programacion) => (
              <button
                type="button"
                className="boton"
                aria-label={`Ejecutar ${p.nombre}`}
                disabled={ejecutando !== null}
                onClick={() => void ejecutar(p.id)}
              >
                {ejecutando === p.id ? 'Ejecutando…' : 'Ejecutar'}
              </button>
            ),
          },
        ]}
        filas={programaciones}
        clave={(p) => String(p.id)}
        vacio="No hay respaldos programados"
      />
    </div>
  )
}
