import { useCallback, useEffect, useState } from 'react'
import '../admin/admin.css'
import { llamar, type Aviso, type Credenciales } from '../admin/api'
import { BotonConfirmar, MostrarAviso, Tabla } from '../admin/Avisos'

type Usuario = {
  usuario: string
  estado: string
  tablespace: string
  temporal: string
  perfil: string
  creado: string
}

type Permiso = { nombre: string; admin: boolean }

type Detalle = Usuario & {
  roles: Permiso[]
  privilegios: Permiso[]
  cuotas: { tablespace: string; usado_mb: number; ilimitada: boolean }[]
}

type Catalogos = {
  tablespaces: string[]
  temporales: string[]
  roles: string[]
  privilegios: string[]
}

type Mensaje = { mensaje: string }

type Vista = { tipo: 'lista' } | { tipo: 'crear' } | { tipo: 'detalle'; usuario: string }

const CATALOGOS_VACIOS: Catalogos = { tablespaces: [], temporales: [], roles: [], privilegios: [] }

const bloqueado = (estado: string) => estado.includes('LOCKED')

type Props = { credenciales: Credenciales }

export function Seguridad({ credenciales }: Props) {
  const [vista, setVista] = useState<Vista>({ tipo: 'lista' })
  const [aviso, setAviso] = useState<Aviso | null>(null)

  const ir = (siguiente: Vista, mensaje: Aviso | null = null) => {
    setAviso(mensaje)
    setVista(siguiente)
  }

  return (
    <section className="vista">
      {vista.tipo !== 'lista' && (
        <button type="button" className="volver" onClick={() => ir({ tipo: 'lista' })}>
          ← Lista de usuarios
        </button>
      )}
      {vista.tipo === 'lista' && (
        <ListaUsuarios credenciales={credenciales} aviso={aviso} setAviso={setAviso} ir={ir} />
      )}
      {vista.tipo === 'crear' && (
        <CrearUsuario credenciales={credenciales} aviso={aviso} setAviso={setAviso} ir={ir} />
      )}
      {vista.tipo === 'detalle' && (
        <DetalleUsuario
          credenciales={credenciales}
          usuario={vista.usuario}
          aviso={aviso}
          setAviso={setAviso}
          ir={ir}
        />
      )}
    </section>
  )
}

type PropsVista = Props & {
  aviso: Aviso | null
  setAviso: (aviso: Aviso | null) => void
  ir: (vista: Vista, mensaje?: Aviso | null) => void
}

function ListaUsuarios({ credenciales, aviso, setAviso, ir }: PropsVista) {
  const [usuarios, setUsuarios] = useState<Usuario[]>([])

  useEffect(() => {
    void llamar<{ usuarios: Usuario[] }>(credenciales, '/seguridad/usuarios').then((r) => {
      if (r.ok) setUsuarios(r.datos.usuarios)
      else setAviso(r.aviso)
    })
  }, [credenciales, setAviso])

  return (
    <>
      <div className="encabezado-modulo">
        <div>
          <h1>Seguridad de usuarios</h1>
          <p className="apoyo">
            Crea usuarios, bloquéalos o desbloquéalos y administra sus roles y privilegios.
          </p>
        </div>
        <button type="button" className="boton principal" onClick={() => ir({ tipo: 'crear' })}>
          Crear usuario
        </button>
      </div>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <h2>Usuarios</h2>
        <Tabla
          titulo="Usuarios"
          columnas={[
            { titulo: 'Usuario', valor: (u: Usuario) => u.usuario },
            {
              titulo: 'Estado',
              valor: (u: Usuario) => (
                <span className={`estado ${bloqueado(u.estado) ? 'mal' : 'bien'}`}>{u.estado}</span>
              ),
            },
            { titulo: 'Tablespace', valor: (u: Usuario) => u.tablespace },
            { titulo: 'Temporal', valor: (u: Usuario) => u.temporal },
            { titulo: 'Perfil', valor: (u: Usuario) => u.perfil },
            { titulo: 'Creado', valor: (u: Usuario) => u.creado },
            {
              titulo: 'Detalle',
              valor: (u: Usuario) => (
                <button
                  type="button"
                  className="boton"
                  aria-label={`Administrar ${u.usuario}`}
                  onClick={() => ir({ tipo: 'detalle', usuario: u.usuario })}
                >
                  Administrar
                </button>
              ),
            },
          ]}
          filas={usuarios}
          clave={(u) => u.usuario}
          vacio="No hay usuarios creados además de los de Oracle"
        />
      </div>
    </>
  )
}

function useCatalogos(credenciales: Credenciales, setAviso: (aviso: Aviso | null) => void) {
  const [catalogos, setCatalogos] = useState<Catalogos>(CATALOGOS_VACIOS)
  useEffect(() => {
    void llamar<Catalogos>(credenciales, '/seguridad/catalogos').then((r) => {
      if (r.ok) setCatalogos(r.datos)
      else setAviso(r.aviso)
    })
  }, [credenciales, setAviso])
  return catalogos
}

function CrearUsuario({ credenciales, aviso, setAviso, ir }: PropsVista) {
  const catalogos = useCatalogos(credenciales, setAviso)
  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [tablespace, setTablespace] = useState('')
  const [temporal, setTemporal] = useState('')
  const [cuota, setCuota] = useState('UNLIMITED')
  const [conexion, setConexion] = useState(true)

  const crear = async () => {
    const r = await llamar<Mensaje>(credenciales, '/seguridad/usuarios', {
      usuario,
      password,
      tablespace,
      temporal,
      cuota,
      permitir_conexion: conexion,
    })
    if (r.ok) ir({ tipo: 'lista' }, { tipo: 'ok', textos: [r.datos.mensaje] })
    else setAviso(r.aviso)
  }

  return (
    <>
      <h1>Crear usuario</h1>
      <p className="apoyo">El nombre se guarda en mayúsculas. La contraseña no se muestra en ningún momento.</p>

      <MostrarAviso aviso={aviso} />

      <div className="panel">
        <label className="campo">
          Usuario
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} />
        </label>
        <label className="campo">
          Contraseña
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label className="campo">
          Tablespace por defecto
          <select value={tablespace} onChange={(e) => setTablespace(e.target.value)}>
            <option value="">Selecciona un tablespace</option>
            {catalogos.tablespaces.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Tablespace temporal
          <select value={temporal} onChange={(e) => setTemporal(e.target.value)}>
            <option value="">Selecciona un tablespace temporal</option>
            {catalogos.temporales.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          Cuota en el tablespace por defecto
          <input value={cuota} onChange={(e) => setCuota(e.target.value)} />
        </label>
        <p className="ayuda">UNLIMITED o un tamaño como 100M, 500K o 1G.</p>
        <label className="opcion">
          <input type="checkbox" checked={conexion} onChange={() => setConexion((v) => !v)} />
          Permitir que se conecte (otorga CREATE SESSION)
        </label>
      </div>

      <button type="button" className="accion" onClick={() => void crear()}>
        Crear usuario
      </button>
    </>
  )
}

function DetalleUsuario({ credenciales, usuario, aviso, setAviso, ir }: PropsVista & { usuario: string }) {
  const catalogos = useCatalogos(credenciales, setAviso)
  const [detalle, setDetalle] = useState<Detalle | null>(null)
  const [rol, setRol] = useState('')
  const [privilegio, setPrivilegio] = useState('')
  const [password, setPassword] = useState('')

  const base = `/seguridad/usuarios/${encodeURIComponent(usuario)}`

  const cargar = useCallback(
    () =>
      llamar<Detalle>(credenciales, base).then((r) => {
        if (r.ok) setDetalle(r.datos)
        else setAviso(r.aviso)
      }),
    [credenciales, base, setAviso],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  const operar = async (ruta: string, cuerpo: unknown = {}) => {
    const r = await llamar<Mensaje>(credenciales, `${base}/${ruta}`, cuerpo)
    if (!r.ok) {
      setAviso(r.aviso)
      return false
    }
    await cargar()
    setAviso({ tipo: 'ok', textos: [r.datos.mensaje] })
    return true
  }

  const eliminar = async () => {
    const r = await llamar<Mensaje>(credenciales, `${base}/eliminar`, { confirmar: true })
    if (r.ok) ir({ tipo: 'lista' }, { tipo: 'ok', textos: [r.datos.mensaje] })
    else setAviso(r.aviso)
  }

  return (
    <>
      <h1>Usuario {usuario}</h1>
      {detalle && (
        <p className="apoyo">
          Estado: <span className={`estado ${bloqueado(detalle.estado) ? 'mal' : 'bien'}`}>{detalle.estado}</span>
          {' · '}Tablespace {detalle.tablespace} · Temporal {detalle.temporal} · Perfil {detalle.perfil}
        </p>
      )}

      <MostrarAviso aviso={aviso} />

      {detalle && (
        <>
          <div className="panel">
            <h2>Cuenta</h2>
            <div className="botones">
              {bloqueado(detalle.estado) ? (
                <button type="button" className="boton" onClick={() => void operar('desbloquear')}>
                  Desbloquear
                </button>
              ) : (
                <button type="button" className="boton" onClick={() => void operar('bloquear')}>
                  Bloquear
                </button>
              )}
              <BotonConfirmar
                etiqueta="Eliminar usuario"
                pregunta={`¿Eliminar ${usuario} y todos sus objetos (CASCADE)?`}
                onConfirmar={() => void eliminar()}
              />
            </div>
            <div className="fila-formulario" style={{ marginTop: '1.25rem' }}>
              <label className="campo">
                Nueva contraseña
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </label>
              <button
                type="button"
                className="boton principal"
                onClick={async () => {
                  if (await operar('password', { password })) setPassword('')
                }}
              >
                Cambiar contraseña
              </button>
            </div>
          </div>

          <div className="panel">
            <h2>Roles</h2>
            <ul className="chips" aria-label="Roles otorgados">
              {detalle.roles.map((r) => (
                <li key={r.nombre} className="chip">
                  {r.nombre}
                  <button
                    type="button"
                    aria-label={`Revocar ${r.nombre}`}
                    onClick={() => void operar('roles', { nombre: r.nombre, otorgar: false })}
                  >
                    Revocar
                  </button>
                </li>
              ))}
              {detalle.roles.length === 0 && <li className="ayuda">Sin roles</li>}
            </ul>
            <div className="fila-formulario">
              <label className="campo">
                Rol
                <select value={rol} onChange={(e) => setRol(e.target.value)}>
                  <option value="">Selecciona un rol</option>
                  {catalogos.roles.map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="boton principal"
                onClick={() => void operar('roles', { nombre: rol, otorgar: true })}
              >
                Otorgar rol
              </button>
            </div>
          </div>

          <div className="panel">
            <h2>Privilegios de sistema</h2>
            <ul className="chips" aria-label="Privilegios otorgados">
              {detalle.privilegios.map((p) => (
                <li key={p.nombre} className="chip">
                  {p.nombre}
                  <button
                    type="button"
                    aria-label={`Revocar ${p.nombre}`}
                    onClick={() => void operar('privilegios', { nombre: p.nombre, otorgar: false })}
                  >
                    Revocar
                  </button>
                </li>
              ))}
              {detalle.privilegios.length === 0 && <li className="ayuda">Sin privilegios directos</li>}
            </ul>
            <div className="fila-formulario">
              <label className="campo">
                Privilegio
                <select value={privilegio} onChange={(e) => setPrivilegio(e.target.value)}>
                  <option value="">Selecciona un privilegio</option>
                  {catalogos.privilegios.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="boton principal"
                onClick={() => void operar('privilegios', { nombre: privilegio, otorgar: true })}
              >
                Otorgar privilegio
              </button>
            </div>
          </div>

          <div className="panel">
            <h2>Cuotas</h2>
            <Tabla
              titulo="Cuotas"
              columnas={[
                { titulo: 'Tablespace', valor: (c: Detalle['cuotas'][number]) => c.tablespace },
                { titulo: 'Usado (MB)', valor: (c: Detalle['cuotas'][number]) => c.usado_mb },
                {
                  titulo: 'Límite',
                  valor: (c: Detalle['cuotas'][number]) => (c.ilimitada ? 'Ilimitada' : 'Limitada'),
                },
              ]}
              filas={detalle.cuotas}
              clave={(c) => c.tablespace}
              vacio="Sin cuotas asignadas"
            />
          </div>
        </>
      )}
    </>
  )
}
