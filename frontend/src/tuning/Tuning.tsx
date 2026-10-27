import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso, type Credenciales } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Catalogos = { schemas: string[]; tablespaces: string[] }

type Operacion = {
  id: number
  nivel: number
  operacion: string
  opciones: string | null
  propietario: string | null
  objeto: string | null
  costo: number | null
  filas: number | null
  bytes: number | null
  acceso: string | null
  filtro: string | null
}

type Plan = { texto: string[]; operaciones: Operacion[]; observaciones: string[] }

type TablaStats = {
  tabla: string
  filas: number | null
  bloques: number | null
  largo_promedio: number | null
  analizada: string | null
  obsoletas: boolean
}

type Indice = {
  propietario: string
  nombre: string
  unico: boolean
  tipo: string
  estado: string
  tablespace: string | null
  analizado: string | null
  columnas: string
  restriccion: string | null
}

type Columna = { nombre: string; tipo: string }

type Mensaje = { mensaje: string }

type Seccion = 'plan' | 'estadisticas' | 'indices'

const SECCIONES: { seccion: Seccion; titulo: string }[] = [
  { seccion: 'plan', titulo: 'Plan de ejecución' },
  { seccion: 'estadisticas', titulo: 'Estadísticas' },
  { seccion: 'indices', titulo: 'Índices' },
]

const conSchema = (ruta: string, params: Record<string, string>) =>
  `${ruta}?${new URLSearchParams(params).toString()}`

const sinDato = (valor: number | string | null) => (valor === null ? '—' : valor)

type Props = { credenciales: Credenciales }

type PropsSeccion = Props & {
  catalogos: Catalogos
  setAviso: (aviso: Aviso | null) => void
}

export function Tuning({ credenciales }: Props) {
  const [seccion, setSeccion] = useState<Seccion>('plan')
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [catalogos, setCatalogos] = useState<Catalogos>({ schemas: [], tablespaces: [] })

  useEffect(() => {
    void llamar<Catalogos>(credenciales, '/tuning/catalogos').then((r) => {
      if (r.ok) setCatalogos(r.datos)
      else setAviso(r.aviso)
    })
  }, [credenciales])

  return (
    <section className="vista">
      <h1>Tunning de consultas</h1>
      <p className="apoyo">
        Analiza el plan de ejecución de una consulta, mantén al día las estadísticas y administra los índices.
      </p>

      <div className="botones" role="group" aria-label="Secciones" style={{ marginBottom: '1.5rem' }}>
        {SECCIONES.map((s) => (
          <button
            key={s.seccion}
            type="button"
            className={`boton ${seccion === s.seccion ? 'principal' : ''}`}
            aria-pressed={seccion === s.seccion}
            onClick={() => {
              setAviso(null)
              setSeccion(s.seccion)
            }}
          >
            {s.titulo}
          </button>
        ))}
      </div>

      <MostrarAviso aviso={aviso} />

      {seccion === 'plan' && <PlanEjecucion credenciales={credenciales} catalogos={catalogos} setAviso={setAviso} />}
      {seccion === 'estadisticas' && (
        <Estadisticas credenciales={credenciales} catalogos={catalogos} setAviso={setAviso} />
      )}
      {seccion === 'indices' && <Indices credenciales={credenciales} catalogos={catalogos} setAviso={setAviso} />}
    </section>
  )
}

function SelectorSchema({
  schemas,
  valor,
  onCambiar,
  opcional = false,
}: {
  schemas: string[]
  valor: string
  onCambiar: (schema: string) => void
  opcional?: boolean
}) {
  return (
    <label className="campo">
      Schema
      <select value={valor} onChange={(e) => onCambiar(e.target.value)}>
        <option value="">{opcional ? 'El del usuario conectado' : 'Selecciona un schema'}</option>
        {schemas.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
    </label>
  )
}

function PlanEjecucion({ credenciales, catalogos, setAviso }: PropsSeccion) {
  const [schema, setSchema] = useState('')
  const [sql, setSql] = useState('')
  const [plan, setPlan] = useState<Plan | null>(null)

  const analizar = async () => {
    setAviso(null)
    const r = await llamar<Plan>(credenciales, '/tuning/plan', { sql, schema })
    if (r.ok) setPlan(r.datos)
    else {
      setPlan(null)
      setAviso(r.aviso)
    }
  }

  return (
    <>
      <div className="panel">
        <h2>Consulta</h2>
        <SelectorSchema schemas={catalogos.schemas} valor={schema} onCambiar={setSchema} opcional />
        <label className="campo">
          Sentencia SQL
          <textarea
            value={sql}
            spellCheck={false}
            placeholder="SELECT * FROM empleados WHERE departamento = 10"
            onChange={(e) => setSql(e.target.value)}
          />
        </label>
        <p className="ayuda">
          Se usa EXPLAIN PLAN: Oracle calcula el plan sin ejecutar la sentencia, así que no se modifica ningún dato.
        </p>
      </div>

      <button type="button" className="accion" onClick={() => void analizar()}>
        Ver plan de ejecución
      </button>

      {plan && (
        <>
          {plan.observaciones.length > 0 && (
            <div className="panel" style={{ marginTop: '1.5rem' }}>
              <h2>Observaciones</h2>
              <ul className="observaciones">
                {plan.observaciones.map((o) => (
                  <li key={o}>{o}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="panel" style={{ marginTop: '1.5rem' }}>
            <h2>Operaciones</h2>
            <Tabla
              titulo="Operaciones del plan"
              columnas={[
                { titulo: 'ID', valor: (o: Operacion) => o.id },
                {
                  titulo: 'Operación',
                  valor: (o: Operacion) => (
                    <code className="id" style={{ paddingLeft: `${o.nivel}rem` }}>
                      {o.operacion}
                      {o.opciones ? ` ${o.opciones}` : ''}
                    </code>
                  ),
                },
                {
                  titulo: 'Objeto',
                  valor: (o: Operacion) => (o.objeto ? [o.propietario, o.objeto].filter(Boolean).join('.') : '—'),
                },
                { titulo: 'Costo', valor: (o: Operacion) => sinDato(o.costo) },
                { titulo: 'Filas', valor: (o: Operacion) => sinDato(o.filas) },
                { titulo: 'Bytes', valor: (o: Operacion) => sinDato(o.bytes) },
                {
                  titulo: 'Predicados',
                  valor: (o: Operacion) =>
                    [o.acceso && `Acceso: ${o.acceso}`, o.filtro && `Filtro: ${o.filtro}`]
                      .filter(Boolean)
                      .map((p) => (
                        <code key={p as string} className="sentencia">
                          {p}
                        </code>
                      )),
                },
              ]}
              filas={plan.operaciones}
              clave={(o) => String(o.id)}
              vacio="Oracle no devolvió operaciones para esta consulta"
            />
          </div>

          <div className="panel">
            <details>
              <summary>Salida completa de DBMS_XPLAN</summary>
              <pre className="plan" style={{ marginTop: '1rem' }}>
                {plan.texto.join('\n')}
              </pre>
            </details>
          </div>
        </>
      )}
    </>
  )
}

function useTablas(
  credenciales: Credenciales,
  schema: string,
  setAviso: (aviso: Aviso | null) => void,
) {
  const [tablas, setTablas] = useState<TablaStats[]>([])

  const cargar = useCallback(
    () =>
      schema
        ? llamar<{ tablas: TablaStats[] }>(credenciales, conSchema('/tuning/tablas', { schema })).then((r) => {
            if (r.ok) setTablas(r.datos.tablas)
            else setAviso(r.aviso)
          })
        : Promise.resolve(),
    [credenciales, schema, setAviso],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  return { tablas: schema ? tablas : [], cargar }
}

function Estadisticas({ credenciales, catalogos, setAviso }: PropsSeccion) {
  const [schema, setSchema] = useState('')
  const { tablas, cargar } = useTablas(credenciales, schema, setAviso)

  const recolectar = async (tabla = '') => {
    const r = await llamar<Mensaje>(credenciales, '/tuning/estadisticas', { schema, tabla })
    if (!r.ok) {
      setAviso(r.aviso)
      return
    }
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
  }

  return (
    <>
      <div className="panel">
        <div className="fila-formulario">
          <SelectorSchema schemas={catalogos.schemas} valor={schema} onCambiar={setSchema} />
          <button
            type="button"
            className="boton principal"
            disabled={!schema}
            onClick={() => void recolectar()}
          >
            Actualizar todo el schema
          </button>
        </div>
        <p className="ayuda">
          El optimizador usa estas estadísticas para elegir el plan. Si nunca se generaron o están obsoletas, los
          planes pueden ser malos.
        </p>
      </div>

      {schema && (
        <div className="panel">
          <h2>Tablas de {schema}</h2>
          <Tabla
            titulo="Estadísticas de tablas"
            columnas={[
              { titulo: 'Tabla', valor: (t: TablaStats) => t.tabla },
              { titulo: 'Filas', valor: (t: TablaStats) => sinDato(t.filas) },
              { titulo: 'Bloques', valor: (t: TablaStats) => sinDato(t.bloques) },
              { titulo: 'Largo promedio (bytes)', valor: (t: TablaStats) => sinDato(t.largo_promedio) },
              {
                titulo: 'Última actualización',
                valor: (t: TablaStats) => t.analizada ?? <span className="estado mal">Nunca</span>,
              },
              {
                titulo: 'Obsoletas',
                valor: (t: TablaStats) =>
                  t.obsoletas ? <span className="estado mal">Sí</span> : t.analizada ? 'No' : '—',
              },
              {
                titulo: 'Acción',
                valor: (t: TablaStats) => (
                  <button
                    type="button"
                    className="boton"
                    aria-label={`Actualizar estadísticas de ${t.tabla}`}
                    onClick={() => void recolectar(t.tabla)}
                  >
                    Actualizar
                  </button>
                ),
              },
            ]}
            filas={tablas}
            clave={(t) => t.tabla}
            vacio="Este schema no tiene tablas"
          />
        </div>
      )}
    </>
  )
}

function Indices({ credenciales, catalogos, setAviso }: PropsSeccion) {
  const [schema, setSchema] = useState('')
  const [tabla, setTabla] = useState('')
  const { tablas } = useTablas(credenciales, schema, setAviso)
  const [indices, setIndices] = useState<Indice[]>([])
  const [columnas, setColumnas] = useState<Columna[]>([])
  const [nombre, setNombre] = useState('')
  const [elegidas, setElegidas] = useState<string[]>([])
  const [unico, setUnico] = useState(false)
  const [tablespace, setTablespace] = useState('')

  const cargar = useCallback(
    () =>
      schema && tabla
        ? llamar<{ indices: Indice[]; columnas: Columna[] }>(
            credenciales,
            conSchema('/tuning/indices', { schema, tabla }),
          ).then((r) => {
            if (r.ok) {
              setIndices(r.datos.indices)
              setColumnas(r.datos.columnas)
            } else setAviso(r.aviso)
          })
        : Promise.resolve(),
    [credenciales, schema, tabla, setAviso],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  const elegirTabla = (siguiente: string) => {
    setTabla(siguiente)
    setIndices([])
    setColumnas([])
    setElegidas([])
  }

  // El orden de las columnas importa en un índice compuesto: se respeta el orden en que se marcan.
  const alternar = (columna: string) =>
    setElegidas((actual) =>
      actual.includes(columna) ? actual.filter((c) => c !== columna) : [...actual, columna],
    )

  const operar = async (ruta: string, cuerpo: unknown) => {
    const r = await llamar<Mensaje>(credenciales, ruta, cuerpo)
    if (!r.ok) {
      setAviso(r.aviso)
      return false
    }
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
    return true
  }

  const crear = async () => {
    const listo = await operar('/tuning/indices', { schema, tabla, nombre, columnas: elegidas, unico, tablespace })
    if (listo) {
      setNombre('')
      setElegidas([])
      setUnico(false)
    }
  }

  return (
    <>
      <div className="panel">
        <div className="fila-formulario">
          <SelectorSchema
            schemas={catalogos.schemas}
            valor={schema}
            onCambiar={(s) => {
              setSchema(s)
              elegirTabla('')
            }}
          />
          <label className="campo">
            Tabla
            <select
              value={tabla}
              disabled={!schema}
              onChange={(e) => elegirTabla(e.target.value)}
            >
              <option value="">Selecciona una tabla</option>
              {tablas.map((t) => (
                <option key={t.tabla}>{t.tabla}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {schema && tabla && (
        <>
          <div className="panel">
            <h2>
              Índices de {schema}.{tabla}
            </h2>
            <Tabla
              titulo="Índices"
              columnas={[
                { titulo: 'Nombre', valor: (i: Indice) => i.nombre },
                { titulo: 'Columnas', valor: (i: Indice) => i.columnas },
                { titulo: 'Único', valor: (i: Indice) => (i.unico ? 'Sí' : 'No') },
                { titulo: 'Tipo', valor: (i: Indice) => i.tipo },
                {
                  titulo: 'Estado',
                  valor: (i: Indice) => (
                    <span className={`estado ${i.estado === 'VALID' ? 'bien' : 'mal'}`}>{i.estado}</span>
                  ),
                },
                { titulo: 'Tablespace', valor: (i: Indice) => i.tablespace ?? '—' },
                {
                  titulo: 'Acción',
                  valor: (i: Indice) =>
                    i.restriccion ? (
                      <span className="ayuda">Respalda {i.restriccion}</span>
                    ) : (
                      <BotonConfirmar
                        etiqueta={`Eliminar ${i.nombre}`}
                        pregunta={`¿Eliminar el índice ${i.nombre}?`}
                        onConfirmar={() =>
                          void operar('/tuning/indices/eliminar', {
                            schema,
                            tabla,
                            nombre: i.nombre,
                            confirmar: true,
                          })
                        }
                      />
                    ),
                },
              ]}
              filas={indices}
              clave={(i) => `${i.propietario}.${i.nombre}`}
              vacio="Esta tabla no tiene índices"
            />
            <p className="ayuda">
              Los índices que respaldan una llave primaria o única no se eliminan desde aquí.
            </p>
          </div>

          <div className="panel">
            <h2>Crear índice</h2>
            <label className="campo">
              Nombre del índice
              <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </label>
            <fieldset className="campo" style={{ border: 0, padding: 0 }}>
              <legend>Columnas</legend>
              <ul className="opciones">
                {columnas.map((c) => (
                  <li key={c.nombre}>
                    <label className="opcion">
                      <input
                        type="checkbox"
                        checked={elegidas.includes(c.nombre)}
                        onChange={() => alternar(c.nombre)}
                      />
                      {c.nombre} <span className="ayuda">{c.tipo}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
            <p className="ayuda">
              {elegidas.length > 0
                ? `Orden del índice: ${elegidas.join(', ')}`
                : 'Marca las columnas en el orden en que quieres indexarlas.'}
            </p>
            <label className="opcion" style={{ marginTop: '0.75rem' }}>
              <input type="checkbox" checked={unico} onChange={() => setUnico((v) => !v)} />
              Índice único (no permite valores repetidos)
            </label>
            <label className="campo" style={{ marginTop: '0.75rem' }}>
              Tablespace
              <select value={tablespace} onChange={(e) => setTablespace(e.target.value)}>
                <option value="">El del schema por defecto</option>
                {catalogos.tablespaces.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
          </div>

          <button type="button" className="accion" onClick={() => void crear()}>
            Crear índice
          </button>
        </>
      )}
    </>
  )
}
