import { useState, type ReactNode } from 'react'
import type { Aviso } from './api'

export function MostrarAviso({ aviso }: { aviso: Aviso | null }) {
  if (!aviso) return null
  if (aviso.tipo === 'ok') {
    return (
      <p role="status" className="aviso exito">
        {aviso.textos.join(' ')}
      </p>
    )
  }
  return (
    <div role="alert" className="aviso error">
      {aviso.textos.map((texto) => (
        <p key={texto}>{texto}</p>
      ))}
      {aviso.detalle && <pre>{aviso.detalle}</pre>}
    </div>
  )
}

type PropsConfirmar = {
  etiqueta: string
  pregunta: string
  onConfirmar: () => void
}

// Las acciones destructivas piden una segunda confirmación explícita.
export function BotonConfirmar({ etiqueta, pregunta, onConfirmar }: PropsConfirmar) {
  const [preguntando, setPreguntando] = useState(false)
  if (!preguntando) {
    return (
      <button type="button" className="boton peligro" onClick={() => setPreguntando(true)}>
        {etiqueta}
      </button>
    )
  }
  return (
    <span className="confirmar" role="group" aria-label={pregunta}>
      <span>{pregunta}</span>
      <button
        type="button"
        className="boton peligro"
        onClick={() => {
          setPreguntando(false)
          onConfirmar()
        }}
      >
        Sí, confirmar
      </button>
      <button type="button" className="boton" onClick={() => setPreguntando(false)}>
        Cancelar
      </button>
    </span>
  )
}

type Columna<T> = { titulo: string; valor: (fila: T) => ReactNode }

type PropsTabla<T> = {
  titulo: string
  columnas: Columna<T>[]
  filas: T[]
  clave: (fila: T, indice: number) => string
  vacio: string
}

export function Tabla<T>({ titulo, columnas, filas, clave, vacio }: PropsTabla<T>) {
  if (filas.length === 0) return <p className="ayuda">{vacio}</p>
  return (
    <div className="tabla-contenedor">
      <table className="tabla" aria-label={titulo}>
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.titulo} scope="col">
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={clave(fila, indice)}>
              {columnas.map((c) => (
                <td key={c.titulo}>{c.valor(fila)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
