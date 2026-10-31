import { useCallback, useEffect, useRef, useState } from 'react'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'
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
  const [avisoLista, setAvisoLista] = useState<Aviso | null>(null)
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const [log, setLog] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [ejecutando, setEjecutando] = useState<number | null>(null)
  const guarda = useRef(false) // el estado no se actualiza entre dos clics del mismo tick

  const cargar = useCallback(async () => {
    const r = await llamar<{ programaciones: Programacion[] }>(token, '/respaldos/programados')
    if (!r.ok) return setAvisoLista(r.aviso)
    setProgramaciones(r.datos.programaciones ?? [])
    setAvisoLista(null)
  }, [token])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // Envía la acción; `alExito` convierte el cuerpo 200 en avisos (y log). Recarga tras 200, 404 y 500.
  const accion = async (
    url: string,
    method: 'POST' | 'DELETE',
    alExito: (cuerpo: Record<string, any>) => { avisos: Aviso[]; log?: string },
    idEjecutando: number | null = null,
  ) => {
    if (guarda.current) return
    guarda.current = true
    setAvisos([])
    setLog('')
    setOcupado(true)
    setEjecutando(idEjecutando)
    let resultado: Aviso[] = []
    let logOk = ''
    let recargar = false
    try {
      const r = await pedir(url, { method, headers: cabeceras(token) })
      if (r.ok) {
        const exito = alExito(r.cuerpo)
        resultado = exito.avisos
        logOk = exito.log ?? ''
        recargar = true
      } else if (r.status !== 401) {
        resultado = [avisoDeFallo(r.status, r.cuerpo)]
        recargar = r.status === 404 || r.status === 500
      }
    } catch (error) {
      if (error instanceof ErrorConexion) resultado = [{ tipo: 'error', textos: [avisoDeConexion(error)] }]
    }
    setEjecutando(null)
    if (recargar) await cargar()
    setAvisos(resultado)
    setLog(logOk)
    setOcupado(false)
    guarda.current = false
  }

  const ejecutar = (id: number) =>
    accion(
      `/respaldos/programados/${id}/ejecutar`,
      'POST',
      (c) => ({ avisos: [{ tipo: 'ok', textos: [c.mensaje ?? 'Respaldo ejecutado'] }], log: c.log }),
      id,
    )

  const eliminar = (id: number) =>
    accion(`/respaldos/programados/${id}`, 'DELETE', (c) => ({
      avisos: [{ tipo: 'ok', textos: [c.mensaje ?? 'Programación eliminada'] }],
    }))

  const reinstalar = () =>
    accion('/respaldos/programados/reinstalar', 'POST', (c) => {
      const fallidas: { nombre: string; mensaje: string }[] = c.fallidas ?? []
      const lista: Aviso[] = [{ tipo: 'ok', textos: [c.mensaje ?? 'Tareas reinstaladas'] }]
      if (fallidas.length > 0) {
        lista.push({ tipo: 'error', textos: fallidas.map((f) => `${f.nombre}: ${f.mensaje}`) })
      }
      return { avisos: lista }
    })

  return (
    <div className="panel">
      <h2>Respaldos programados</h2>
      <button type="button" className="boton" disabled={ocupado} onClick={() => void reinstalar()}>
        Reinstalar tareas
      </button>
      {avisos.map((a, i) => (
        <MostrarAviso key={i} aviso={a} />
      ))}
      <MostrarAviso aviso={avisoLista} />
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
              <>
                <button
                  type="button"
                  className="boton"
                  aria-label={`Ejecutar ${p.nombre}`}
                  disabled={ocupado}
                  onClick={() => void ejecutar(p.id)}
                >
                  {ejecutando === p.id ? 'Ejecutando…' : 'Ejecutar'}
                </button>
                {ocupado ? (
                  // BotonConfirmar no se deshabilita desde fuera: mientras corre una acción se sustituye por un botón inerte.
                  <button type="button" className="boton peligro" disabled>
                    {`Eliminar ${p.nombre}`}
                  </button>
                ) : (
                  <BotonConfirmar
                    etiqueta={`Eliminar ${p.nombre}`}
                    pregunta={`¿Eliminar la programación ${p.nombre}? Se quitan la tarea programada y los scripts de la programación; los respaldos ya generados NO se borran.`}
                    onConfirmar={() => void eliminar(p.id)}
                  />
                )}
              </>
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
