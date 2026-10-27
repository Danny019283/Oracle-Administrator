import { useState, type ReactNode } from 'react'
import './App.css'
import { MenuPrincipal, MenuRespaldos } from './menu/Menu'
import { RespaldoTablas, type Credenciales } from './respaldos/RespaldoTablas'
import { Performance } from './performance/Performance'
import { Auditoria } from './auditoria/Auditoria'
import { Seguridad } from './seguridad/Seguridad'
import { Tablespaces } from './tablespaces/Tablespaces'
import { Tuning } from './tuning/Tuning'
import { ToggleTema } from './tema/ToggleTema'

// Provisional hasta que exista la pantalla de ingreso a Oracle.
const CREDENCIALES: Credenciales = {
  usuario: import.meta.env.VITE_ORACLE_USER ?? '',
  password: import.meta.env.VITE_ORACLE_PASSWORD ?? '',
  servicio: import.meta.env.VITE_ORACLE_SERVICE ?? '',
}

type VistaModulo = 'tablespaces' | 'tuning' | 'performance' | 'auditoria' | 'seguridad'

type Vista = 'principal' | 'respaldos' | 'tablas' | VistaModulo

const VISTA_DE_MODULO: Record<string, VistaModulo> = {
  'Administración de tablespaces': 'tablespaces',
  'Tunning de consultas': 'tuning',
  'Performance de la base de datos': 'performance',
  'Auditoría de la BD': 'auditoria',
  'Seguridad de usuarios': 'seguridad',
}

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

function Marco({ children }: { children: ReactNode }) {
  return (
    <div className="app">
      <header className="barra">
        <span className="marca">
          <MarcaBaseDeDatos />
          Administrador Oracle
        </span>
        <ToggleTema />
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

function App() {
  const [vista, setVista] = useState<Vista>('principal')

  if (vista === 'tablas') {
    return (
      <Marco>
        <button type="button" className="volver" onClick={() => setVista('respaldos')}>
          <FlechaAtras />
          Volver
        </button>
        <RespaldoTablas credenciales={CREDENCIALES} />
      </Marco>
    )
  }

  if (Object.values(VISTA_DE_MODULO).includes(vista as VistaModulo)) {
    return (
      <Marco>
        <button type="button" className="volver" onClick={() => setVista('principal')}>
          <FlechaAtras />
          Volver
        </button>
        {vista === 'tablespaces' && <Tablespaces credenciales={CREDENCIALES} />}
        {vista === 'tuning' && <Tuning credenciales={CREDENCIALES} />}
        {vista === 'performance' && <Performance credenciales={CREDENCIALES} />}
        {vista === 'auditoria' && <Auditoria credenciales={CREDENCIALES} />}
        {vista === 'seguridad' && <Seguridad credenciales={CREDENCIALES} />}
      </Marco>
    )
  }

  if (vista === 'respaldos') {
    return (
      <Marco>
        <MenuRespaldos
          onElegirRespaldo={(tipo) => tipo === 'tablas' && setVista('tablas')}
          onVolver={() => setVista('principal')}
        />
      </Marco>
    )
  }

  return (
    <Marco>
      <MenuPrincipal
        onAbrirRespaldos={() => setVista('respaldos')}
        onElegirModulo={(modulo) => {
          const destino = VISTA_DE_MODULO[modulo]
          if (destino) setVista(destino)
        }}
      />
    </Marco>
  )
}

export default App
