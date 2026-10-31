import { useCallback, useEffect, useState } from 'react'
import { BotonConfirmar, MostrarAviso } from '../admin/Avisos'
import type { Aviso } from '../admin/api'

const URL_ESTADO = '/base/estado'

const ACCIONES_VALIDAS: Record<string, string[]> = {
  APAGADA: ['NOMOUNT', 'MOUNT', 'ENCENDER'],
  NOMOUNT: ['MOUNT', 'APAGAR', 'ENCENDER'],
  MOUNT: ['APAGAR', 'ENCENDER'],
  ABIERTA: ['APAGAR'],
}

const PREGUNTAS: Record<string, string> = {
  APAGAR: 'APAGAR corta la app y cierra las sesiones de la base. ¿Continuar?',
  NOMOUNT: '¿Iniciar la instancia en NOMOUNT?',
  MOUNT: '¿Montar la base en MOUNT?',
  ENCENDER: '¿Encender y abrir la base?',
}

type Cuerpo = { estado?: string; mensaje?: string; explicacion?: string; log?: string; detail?: unknown }

// El control no usa sesión (RNF-6): se llama con fetch directo, sin cabecera de autorización.
async function pedir(opciones?: RequestInit): Promise<{ ok: boolean; cuerpo: Cuerpo }> {
  try {
    const r = await (opciones ? fetch(URL_ESTADO, opciones) : fetch(URL_ESTADO))
    const cuerpo: Cuerpo = await r.json().catch(() => ({}))
    return { ok: r.ok, cuerpo: r.ok ? cuerpo : { ...cuerpo, mensaje: textoDeError(r.status, cuerpo) } }
  } catch {
    return { ok: false, cuerpo: { mensaje: 'No se pudo conectar con el servidor' } }
  }
}

const textoDeError = (status: number, cuerpo: Cuerpo) =>
  cuerpo.mensaje ?? (typeof cuerpo.detail === 'string' ? cuerpo.detail : `El servidor respondió con el código ${status}`)

const avisoDeError = ({ mensaje, explicacion, log }: Cuerpo): Aviso => ({
  tipo: 'error',
  textos: [mensaje, explicacion].filter((t): t is string => !!t),
  detalle: log,
})

export function EstadoBase() {
  const [estado, setEstado] = useState<string | null>(null)
  const [cambiando, setCambiando] = useState(false)
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [log, setLog] = useState('')

  const consultar = useCallback(async () => {
    const { ok, cuerpo } = await pedir()
    if (ok) {
      setEstado(typeof cuerpo.estado === 'string' && cuerpo.estado in ACCIONES_VALIDAS ? cuerpo.estado : null)
    } else {
      setEstado(null)
      setAviso(avisoDeError(cuerpo))
    }
  }, [])

  useEffect(() => {
    void consultar()
  }, [consultar])

  async function cambiar(accion: string) {
    setCambiando(true)
    setAviso(null)
    setLog('')
    const { ok, cuerpo } = await pedir({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accion }),
    })
    setCambiando(false)
    if (ok) {
      setAviso({ tipo: 'ok', textos: [cuerpo.mensaje ?? 'Estado cambiado'] })
      setLog(cuerpo.log ?? '')
    } else {
      setAviso(avisoDeError(cuerpo))
    }
    await consultar()
  }

  return (
    <div className="estado-base">
      {estado && (
        <span className="usuario">
          Base: <strong>{estado}</strong>
        </span>
      )}
      {cambiando ? (
        <p role="status" className="ayuda">
          Cambiando estado...
        </p>
      ) : (
        estado &&
        ACCIONES_VALIDAS[estado].map((accion) => (
          <BotonConfirmar key={accion} etiqueta={accion} pregunta={PREGUNTAS[accion]} onConfirmar={() => void cambiar(accion)} />
        ))
      )}
      {(aviso || log) && (
        <div className="estado-base-resultado">
          <MostrarAviso aviso={aviso} />
          {log && <pre>{log}</pre>}
        </div>
      )}
    </div>
  )
}
