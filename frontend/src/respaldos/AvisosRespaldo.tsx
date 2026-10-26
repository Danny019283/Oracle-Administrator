import type { ReactNode } from 'react'

type PropsError = {
  mensajes: string[]
  log?: string
}

export function AvisoError({ mensajes, log }: PropsError) {
  if (mensajes.length === 0) return null
  return (
    <div role="alert" className="aviso error">
      {mensajes.map((mensaje) => (
        <p key={mensaje}>{mensaje}</p>
      ))}
      {log && <pre>{log}</pre>}
    </div>
  )
}

export function AvisoExito({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="aviso exito">
      {children}
    </p>
  )
}

export function BarraRespaldando() {
  return (
    <div aria-live="polite" className="progreso">
      <p>Respaldando...</p>
      <div className="progreso-pista" aria-hidden="true">
        <div className="progreso-bloque" />
      </div>
    </div>
  )
}
