import { useState } from 'react'

export type TipoRespaldo = 'tablas' | 'schemas' | 'full'

const MODULOS = [
  'Administración de tablespaces',
  'Tunning de consultas',
  'Performance de la base de datos',
  'Auditoría de la BD',
  'Seguridad de usuarios',
  'Creación de respaldos',
  'Recuperación de respaldos',
  'Administración de archivos de respaldos y directorios',
]

const RESPALDOS: { tipo: TipoRespaldo; titulo: string }[] = [
  { tipo: 'tablas', titulo: 'Tablas' },
  { tipo: 'schemas', titulo: 'Schemas' },
  { tipo: 'full', titulo: 'Full' },
]

type Props = {
  onElegirRespaldo: (tipo: TipoRespaldo) => void
}

export function Menu({ onElegirRespaldo }: Props) {
  const [respaldosAbierto, setRespaldosAbierto] = useState(false)

  return (
    <nav>
      <ul>
        {MODULOS.map((modulo) => (
          <li key={modulo}>
            <button
              type="button"
              onClick={
                modulo === 'Creación de respaldos'
                  ? () => setRespaldosAbierto(true)
                  : undefined
              }
            >
              {modulo}
            </button>
          </li>
        ))}
      </ul>
      {respaldosAbierto && (
        <ul>
          {RESPALDOS.map(({ tipo, titulo }) => (
            <li key={tipo}>
              <button type="button" onClick={() => onElegirRespaldo(tipo)}>
                {titulo}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  )
}
