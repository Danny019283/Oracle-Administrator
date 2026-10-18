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

const MODULOS_DISPONIBLES = ['Creación de respaldos']

const RESPALDOS: { tipo: TipoRespaldo; titulo: string }[] = [
  { tipo: 'tablas', titulo: 'Tablas' },
  { tipo: 'schemas', titulo: 'Schemas' },
  { tipo: 'full', titulo: 'Full' },
]

const RESPALDOS_DISPONIBLES: TipoRespaldo[] = ['tablas', 'schemas']

function Flecha({ haciaAtras = false }: { haciaAtras?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={haciaAtras ? 'm15 18-6-6 6-6' : 'm9 18 6-6-6-6'} />
    </svg>
  )
}

type FilaProps = {
  titulo: string
  disponible: boolean
  onElegir: () => void
}

function Fila({ titulo, disponible, onElegir }: FilaProps) {
  return (
    <li>
      <button
        type="button"
        className="fila"
        aria-disabled={disponible ? undefined : true}
        onClick={disponible ? onElegir : undefined}
      >
        <span>{titulo}</span>
        {disponible ? (
          <Flecha />
        ) : (
          <span className="etiqueta" aria-hidden="true">
            Próximamente
          </span>
        )}
      </button>
    </li>
  )
}

type PropsPrincipal = {
  onAbrirRespaldos: () => void
}

export function MenuPrincipal({ onAbrirRespaldos }: PropsPrincipal) {
  return (
    <section className="vista">
      <h1>¿Qué quieres administrar?</h1>
      <p className="apoyo">Elige un módulo para empezar.</p>
      <nav aria-label="Módulos">
        <ul className="filas">
          {MODULOS.map((modulo) => (
            <Fila
              key={modulo}
              titulo={modulo}
              disponible={MODULOS_DISPONIBLES.includes(modulo)}
              onElegir={onAbrirRespaldos}
            />
          ))}
        </ul>
      </nav>
    </section>
  )
}

type PropsRespaldos = {
  onElegirRespaldo: (tipo: TipoRespaldo) => void
  onVolver: () => void
}

export function MenuRespaldos({ onElegirRespaldo, onVolver }: PropsRespaldos) {
  return (
    <section className="vista">
      <button type="button" className="volver" onClick={onVolver}>
        <Flecha haciaAtras />
        Volver
      </button>
      <h1>Creación de respaldos</h1>
      <p className="apoyo">Elige qué quieres respaldar.</p>
      <nav aria-label="Tipos de respaldo">
        <ul className="filas">
          {RESPALDOS.map(({ tipo, titulo }) => (
            <Fila
              key={tipo}
              titulo={titulo}
              disponible={RESPALDOS_DISPONIBLES.includes(tipo)}
              onElegir={() => onElegirRespaldo(tipo)}
            />
          ))}
        </ul>
      </nav>
    </section>
  )
}
