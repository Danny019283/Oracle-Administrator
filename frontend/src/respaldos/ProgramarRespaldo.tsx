export type Politica = 'FULL' | 'INCREMENTAL' | 'TRANSACCIONAL'
export type Frecuencia = 'DIARIO' | 'SEMANAL' | 'MENSUAL' | 'HORAS'

export type Programacion = {
  politica: Politica
  frecuencia: Frecuencia
  hora: string
  diaSemana: number
  diaMes: number
  cadaHoras: number
}

export const PROGRAMACION_INICIAL: Programacion = {
  politica: 'FULL',
  frecuencia: 'DIARIO',
  hora: '23:00',
  diaSemana: 0,
  diaMes: 1,
  cadaHoras: 2,
}

const POLITICAS: [Politica, string][] = [
  ['FULL', 'Full (nivel 0)'],
  ['INCREMENTAL', 'Incremental (nivel 1)'],
  ['TRANSACCIONAL', 'Transaccional (archivelogs)'],
]
const FRECUENCIAS: [Frecuencia, string][] = [
  ['DIARIO', 'Diario'],
  ['SEMANAL', 'Semanal'],
  ['MENSUAL', 'Mensual'],
]
const DIAS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

type Props = {
  valor: Programacion
  onChange: (valor: Programacion) => void
}

export function ProgramarRespaldo({ valor, onChange }: Props) {
  const cambiar = (cambios: Partial<Programacion>) => onChange({ ...valor, ...cambios })
  const transaccional = valor.politica === 'TRANSACCIONAL'
  const frecuencias = transaccional ? [...FRECUENCIAS, ['HORAS', 'Cada N horas'] as [Frecuencia, string]] : FRECUENCIAS

  return (
    <div className="panel">
      <h2>Programación</h2>
      <label className="campo">
        Política
        <select
          value={valor.politica}
          onChange={(e) => {
            const politica = e.target.value as Politica
            // «Cada N horas» solo existe con Transaccional.
            const frecuencia = politica !== 'TRANSACCIONAL' && valor.frecuencia === 'HORAS' ? 'DIARIO' : valor.frecuencia
            cambiar({ politica, frecuencia })
          }}
        >
          {POLITICAS.map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="campo">
        Frecuencia
        <select value={valor.frecuencia} onChange={(e) => cambiar({ frecuencia: e.target.value as Frecuencia })}>
          {frecuencias.map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
      </label>

      {valor.frecuencia !== 'HORAS' && (
        <label className="campo">
          Hora
          <input type="time" value={valor.hora} onChange={(e) => cambiar({ hora: e.target.value })} />
        </label>
      )}

      {valor.frecuencia === 'SEMANAL' && (
        <label className="campo">
          Día de la semana
          <select value={valor.diaSemana} onChange={(e) => cambiar({ diaSemana: Number(e.target.value) })}>
            {DIAS.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
      )}

      {valor.frecuencia === 'MENSUAL' && (
        <label className="campo">
          Día del mes
          <input
            type="number"
            min={1}
            max={28}
            value={valor.diaMes}
            onChange={(e) => cambiar({ diaMes: Number(e.target.value) })}
          />
        </label>
      )}

      {valor.frecuencia === 'HORAS' && (
        <label className="campo">
          Cada cuántas horas
          <input
            type="number"
            min={1}
            max={23}
            value={valor.cadaHoras}
            onChange={(e) => cambiar({ cadaHoras: Number(e.target.value) })}
          />
        </label>
      )}
    </div>
  )
}
