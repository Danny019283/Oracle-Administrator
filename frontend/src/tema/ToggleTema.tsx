import { useEffect, useState } from 'react'

type Tema = 'light' | 'dark'

const CLAVE = 'tema'

function leerGuardado(): Tema | null {
  try {
    const guardado = localStorage.getItem(CLAVE)
    return guardado === 'light' || guardado === 'dark' ? guardado : null
  } catch {
    return null
  }
}

function temaDelSistema(): Tema {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function guardar(tema: Tema) {
  try {
    localStorage.setItem(CLAVE, tema)
  } catch {
    // el navegador no permite guardar: el tema solo dura esta sesión
  }
}

export function ToggleTema() {
  const [tema, setTema] = useState<Tema>(() => leerGuardado() ?? temaDelSistema())

  useEffect(() => {
    document.documentElement.dataset.theme = tema
  }, [tema])

  const alternar = () => {
    const siguiente: Tema = tema === 'dark' ? 'light' : 'dark'
    setTema(siguiente)
    guardar(siguiente)
  }

  return (
    <button type="button" className="tema" aria-pressed={tema === 'dark'} onClick={alternar}>
      Tema oscuro
      <span className="pista" aria-hidden="true" />
    </button>
  )
}
