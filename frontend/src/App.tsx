import { useState, type ReactNode } from 'react'
import './App.css'
import { MenuPrincipal, MenuRespaldos } from './menu/Menu'
import type { Credenciales } from './respaldos/api'
import { RespaldoSchemas } from './respaldos/RespaldoSchemas'
import { RespaldoTablas } from './respaldos/RespaldoTablas'
import { ToggleTema } from './tema/ToggleTema'

// Provisional hasta que exista la pantalla de ingreso a Oracle.
const CREDENCIALES: Credenciales = {
  usuario: import.meta.env.VITE_ORACLE_USER ?? '',
  password: import.meta.env.VITE_ORACLE_PASSWORD ?? '',
  servicio: import.meta.env.VITE_ORACLE_SERVICE ?? '',
}

type Vista = 'principal' | 'respaldos' | 'tablas' | 'schemas'

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

  if (vista === 'tablas' || vista === 'schemas') {
    const Pantalla = vista === 'tablas' ? RespaldoTablas : RespaldoSchemas
    return (
      <Marco>
        <button type="button" className="volver" onClick={() => setVista('respaldos')}>
          <FlechaAtras />
          Volver
        </button>
        <Pantalla credenciales={CREDENCIALES} />
      </Marco>
    )
  }

  if (vista === 'respaldos') {
    return (
      <Marco>
        <MenuRespaldos
          onElegirRespaldo={(tipo) => (tipo === 'tablas' || tipo === 'schemas') && setVista(tipo)}
          onVolver={() => setVista('principal')}
        />
      </Marco>
    )
  }

  return (
    <Marco>
      <MenuPrincipal onAbrirRespaldos={() => setVista('respaldos')} />
    </Marco>
  )
}

export default App
