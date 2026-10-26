import { useState, useSyncExternalStore, type ReactNode } from 'react'
import './App.css'
import { MenuPrincipal, MenuRespaldos } from './menu/Menu'
import { RespaldoFull } from './respaldos/RespaldoFull'
import { RespaldoSchemas } from './respaldos/RespaldoSchemas'
import { RespaldoTablas } from './respaldos/RespaldoTablas'
import { ModalLogin } from './sesion/ModalLogin'
import { alCambiarSesion, cerrarSesion, motivoDeSalida, sesionActual, type Sesion } from './sesion/sesion'
import { ToggleTema } from './tema/ToggleTema'

type Vista = 'principal' | 'respaldos' | 'tablas' | 'schemas' | 'full'

function MarcaBaseDeDatos() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse cx="12" cy="5.5" rx="7.5" ry="2.75" />
      <path d="M4.5 5.5v6.5c0 1.52 3.36 2.75 7.5 2.75s7.5-1.23 7.5-2.75V5.5" />
      <path d="M4.5 12v6.5c0 1.52 3.36 2.75 7.5 2.75s7.5-1.23 7.5-2.75V12" />
    </svg>
  )
}

const suscribirse = (avisar: () => void) => alCambiarSesion(() => avisar())

const useSesion = () => useSyncExternalStore(suscribirse, sesionActual)

const useMotivoDeSalida = () => useSyncExternalStore(suscribirse, motivoDeSalida)

function Marco({ children, sesion }: { children: ReactNode; sesion: Sesion | null }) {
  return (
    <div className="app" inert={!sesion}>
      <header className="barra">
        <span className="marca">
          <MarcaBaseDeDatos />
          Administrador Oracle
        </span>
        <div className="barra-acciones">
          {sesion && (
            <>
              <span className="usuario">
                {sesion.usuario}
                {sesion.sysdba && <span className="etiqueta-sysdba">SYSDBA</span>}
              </span>
              <button type="button" className="cerrar-sesion" onClick={() => void cerrarSesion()}>
                Cerrar sesión
              </button>
            </>
          )}
          <ToggleTema />
        </div>
      </header>
      <main className="hoja">{children}</main>
    </div>
  )
}

function FlechaAtras() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  )
}

const PANTALLAS = { tablas: RespaldoTablas, schemas: RespaldoSchemas, full: RespaldoFull }

// La pantalla abierta pertenece a la sesión: al cambiar el token se vuelve al menú principal.
function Navegador({ sesion }: { sesion: Sesion | null }) {
  const [vista, setVista] = useState<Vista>('principal')

  if (sesion && (vista === 'tablas' || vista === 'schemas' || vista === 'full')) {
    const Pantalla = PANTALLAS[vista]
    return (
      <>
        <button type="button" className="volver" onClick={() => setVista('respaldos')}>
          <FlechaAtras />
          Volver
        </button>
        <Pantalla token={sesion.token} />
      </>
    )
  }

  if (vista === 'respaldos') {
    return (
      <MenuRespaldos
        onElegirRespaldo={setVista}
        onVolver={() => setVista('principal')}
      />
    )
  }

  return <MenuPrincipal onAbrirRespaldos={() => setVista('respaldos')} />
}

function App() {
  const sesion = useSesion()
  const motivo = useMotivoDeSalida()

  return (
    <>
      <Marco sesion={sesion}>
        <Navegador key={sesion?.token ?? 'sin-sesion'} sesion={sesion} />
      </Marco>
      {!sesion && <ModalLogin aviso={motivo === 'expirada' ? 'Sesión expirada. Inicia sesión de nuevo.' : undefined} />}
    </>
  )
}

export default App
