import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Estado = { modo: string; audit_trail: string | null }

type Politica = {
  nombre: string
  acciones: string[]
  objetos: string[]
  habilitada: boolean
  predefinida: boolean
}

type TablaAuditable = { schema: string; tabla: string }

type Registro = {
  fecha: string
  usuario: string | null
  accion: string
  schema: string | null
  objeto: string | null
  codigo_retorno: number
  politicas: string | null
  sql: string | null
}

type Tipo = 'tabla' | 'sesion'

const ACCIONES_TABLA = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']

type Mensaje = { mensaje: string }

export function Auditoria({ token }: { token: string }) {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [politicas, setPoliticas] = useState<Politica[]>([])
  const [tablas, setTablas] = useState<TablaAuditable[]>([])
  const [registros, setRegistros] = useState<Registro[]>([])
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [verPredefinidas, setVerPredefinidas] = useState(false)

  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState<Tipo>('tabla')
  const [objeto, setObjeto] = useState('')
  const [acciones, setAcciones] = useState<string[]>([])
  const [habilitar, setHabilitar] = useState(true)

  const [filtroPolitica, setFiltroPolitica] = useState('')
  const [filtroUsuario, setFiltroUsuario] = useState('')

  const cargarPoliticas = useCallback(async () => {
    const r = await llamar<{ politicas: Politica[] }>(token, '/auditoria/politicas')
    if (r.ok) setPoliticas(r.datos.politicas)
    return r
  }, [token])

  const buscarRegistros = useCallback(
    async (politica = '', usuario = '') => {
      const params = new URLSearchParams({ politica, usuario, limite: '100' })
      const r = await llamar<{ registros: Registro[] }>(token, `/auditoria/registros?${params}`)
      if (r.ok) setRegistros(r.datos.registros)
      return r
    },
    [token],
  )

  useEffect(() => {
    const iniciar = async () => {
      const [e, p, t, g] = await Promise.all([
        llamar<Estado>(token, '/auditoria/estado'),
        cargarPoliticas(),
        llamar<{ tablas: TablaAuditable[] }>(token, '/auditoria/tablas'),
        buscarRegistros(),
      ])
      if (e.ok) setEstado(e.datos)
      if (t.ok) setTablas(t.datos.tablas)
      const fallo = [e, p, t, g].find((x) => !x.ok)
      if (fallo && !fallo.ok) setAviso(fallo.aviso)
    }
    void iniciar()
  }, [token, cargarPoliticas, buscarRegistros])

  // Ejecuta una acción sobre una política y refresca la lista.
  const operar = async (url: string, cuerpo: unknown = {}) => {
    const r = await llamar<Mensaje>(token, url, cuerpo)
    if (!r.ok) {
      setAviso(r.aviso)
      return false
    }
    await cargarPoliticas()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
    return true
  }

  const crear = async () => {
    const [schema_tabla, tabla] = objeto ? objeto.split('.') : ['', '']
    const creada = await operar('/auditoria/politicas', {
      nombre,
      tipo,
      acciones: tipo === 'tabla' ? acciones : ['LOGON', 'LOGOFF'],
      schema_tabla,
      tabla,
      habilitar,
    })
    if (creada) {
      setNombre('')
      setAcciones([])
    }
  }

  const alternarAccion = (accion: string) =>
    setAcciones((actuales) =>
      actuales.includes(accion) ? actuales.filter((a) => a !== accion) : [...actuales, accion],
    )

  const visibles = politicas.filter((p) => verPredefinidas || !p.predefinida)

  return (
    <section className="vista">
      <h1>Auditoría de la BD</h1>
      <p className="apoyo">
        Crea políticas de auditoría unificada, habilítalas o deshabilítalas y revisa quién hizo qué en la base de
        datos.
      </p>

      <MostrarAviso aviso={aviso} />

      {estado && (
        <div className="panel">
          <h2>Estado de la auditoría</h2>
          <dl className="indicadores">
            <div className="indicador">
              <dt>Modo</dt>
              <dd>{estado.modo}</dd>
            </div>
            <div className="indicador">
              <dt>audit_trail</dt>
              <dd>{estado.audit_trail ?? '—'}</dd>
            </div>
          </dl>
        </div>
      )}

      <div className="panel">
        <h2>Políticas de auditoría</h2>
        <label className="opcion">
          <input
            type="checkbox"
            checked={verPredefinidas}
            onChange={() => setVerPredefinidas((v) => !v)}
          />
          Mostrar las políticas predefinidas de Oracle (ORA_)
        </label>
        <Tabla
          titulo="Políticas de auditoría"
          columnas={[
            { titulo: 'Política', valor: (p: Politica) => p.nombre },
            { titulo: 'Acciones', valor: (p: Politica) => p.acciones.join(', ') },
            { titulo: 'Objeto', valor: (p: Politica) => p.objetos.join(', ') || '—' },
            {
              titulo: 'Estado',
              valor: (p: Politica) => (
                <span className={`estado ${p.habilitada ? 'bien' : ''}`}>
                  {p.habilitada ? 'Habilitada' : 'Deshabilitada'}
                </span>
              ),
            },
            {
              titulo: 'Acciones disponibles',
              valor: (p: Politica) => (
                <span className="botones">
                  {p.habilitada ? (
                    <button
                      type="button"
                      className="boton"
                      onClick={() => void operar(`/auditoria/politicas/${encodeURIComponent(p.nombre)}/deshabilitar`)}
                    >
                      Deshabilitar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="boton"
                      onClick={() => void operar(`/auditoria/politicas/${encodeURIComponent(p.nombre)}/habilitar`)}
                    >
                      Habilitar
                    </button>
                  )}
                  {!p.predefinida && !p.habilitada && (
                    <BotonConfirmar
                      etiqueta="Eliminar"
                      pregunta={`¿Eliminar la política ${p.nombre}?`}
                      onConfirmar={() =>
                        void operar(`/auditoria/politicas/${encodeURIComponent(p.nombre)}/eliminar`, { confirmar: true })
                      }
                    />
                  )}
                </span>
              ),
            },
          ]}
          filas={visibles}
          clave={(p) => p.nombre}
          vacio="No hay políticas creadas. Crea una en el formulario de abajo."
        />
      </div>

      <div className="panel">
        <h2>Nueva política</h2>
        <label className="campo">
          Nombre de la política
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="AUD_EMPLEADOS" />
        </label>
        <label className="campo">
          Qué auditar
          <select value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)}>
            <option value="tabla">Acciones sobre una tabla</option>
            <option value="sesion">Inicios y cierres de sesión (LOGON / LOGOFF)</option>
          </select>
        </label>
        {tipo === 'tabla' && (
          <>
            <label className="campo">
              Tabla
              <select value={objeto} onChange={(e) => setObjeto(e.target.value)}>
                <option value="">Selecciona una tabla</option>
                {tablas.map((t) => (
                  <option key={`${t.schema}.${t.tabla}`} value={`${t.schema}.${t.tabla}`}>
                    {t.schema}.{t.tabla}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="campo">
              <legend>Acciones a auditar</legend>
              <ul className="opciones">
                {ACCIONES_TABLA.map((accion) => (
                  <li key={accion}>
                    <label className="opcion">
                      <input
                        type="checkbox"
                        checked={acciones.includes(accion)}
                        onChange={() => alternarAccion(accion)}
                      />
                      {accion}
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          </>
        )}
        <label className="opcion">
          <input type="checkbox" checked={habilitar} onChange={() => setHabilitar((v) => !v)} />
          Habilitar la política al crearla
        </label>
      </div>

      <button type="button" className="accion" onClick={() => void crear()}>
        Crear política
      </button>

      <div className="panel" style={{ marginTop: '1.5rem' }}>
        <h2>Registros de auditoría</h2>
        <div className="fila-formulario">
          <label className="campo">
            Política
            <input value={filtroPolitica} onChange={(e) => setFiltroPolitica(e.target.value)} />
          </label>
          <label className="campo">
            Usuario
            <input value={filtroUsuario} onChange={(e) => setFiltroUsuario(e.target.value)} />
          </label>
          <button
            type="button"
            className="boton principal"
            onClick={async () => {
              const r = await buscarRegistros(filtroPolitica, filtroUsuario)
              setAviso(r.ok ? null : r.aviso)
            }}
          >
            Buscar
          </button>
        </div>
        <p className="ayuda">Se muestran los 100 registros más recientes.</p>
        <Tabla
          titulo="Registros de auditoría"
          columnas={[
            { titulo: 'Fecha', valor: (g: Registro) => g.fecha },
            { titulo: 'Usuario', valor: (g: Registro) => g.usuario ?? '—' },
            { titulo: 'Acción', valor: (g: Registro) => g.accion },
            {
              titulo: 'Objeto',
              valor: (g: Registro) => (g.objeto ? `${g.schema}.${g.objeto}` : '—'),
            },
            {
              titulo: 'Resultado',
              valor: (g: Registro) => (
                <span className={`estado ${g.codigo_retorno === 0 ? 'bien' : 'mal'}`}>
                  {g.codigo_retorno === 0 ? 'Correcto' : `ORA-${String(g.codigo_retorno).padStart(5, '0')}`}
                </span>
              ),
            },
            { titulo: 'Políticas', valor: (g: Registro) => g.politicas ?? '—' },
            { titulo: 'Sentencia', valor: (g: Registro) => (g.sql ? <code className="sentencia">{g.sql}</code> : '—') },
          ]}
          filas={registros}
          clave={(g, i) => `${g.fecha}-${i}`}
          vacio="No hay registros de auditoría con esos filtros"
        />
      </div>
    </section>
  )
}
