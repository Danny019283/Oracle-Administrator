---
name: Administrador Oracle
description: Minimalismo tipo Google con Soft UI para administrar Oracle XE, una tarea por pantalla.
colors:
  surface: "#eef1f5"
  text: "#1f2933"
  text-soft: "#4a5662"
  page-ground: "#d5dce5"
  panel: "#e6eaf0"
  control-line: "#6f7c8a"
  primary: "#1967d2"
  on-primary: "#ffffff"
  error: "#b3261e"
  success: "#137333"
  surface-dark: "#2b2f36"
  page-ground-dark: "#1b1e23"
  panel-dark: "#25292f"
  text-dark: "#e8eaed"
  text-soft-dark: "#b8bec6"
  primary-dark: "#8ab4f8"
  on-primary-dark: "#0b1f3a"
typography:
  headline:
    fontFamily: "Roboto, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 400
    lineHeight: "2.25rem"
  title:
    fontFamily: "Roboto, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: "1.5rem"
  body:
    fontFamily: "Roboto, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.5"
  label:
    fontFamily: "Roboto, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: "1.25rem"
  code:
    fontFamily: "Roboto Mono, ui-monospace, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: "1.5"
rounded:
  md: "12px"
  lg: "16px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "12px 20px"
    height: "60px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.pill}"
    padding: "12px 24px"
    height: "52px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "6px 16px"
    height: "40px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "48px"
---

# Design System: Administrador Oracle

## Overview

**Creative North Star: "El panel táctil"**

Una herramienta de administración que se siente tranquila y al alcance de la mano. Cada pantalla ofrece una sola tarea sobre una superficie del mismo tono que el fondo; los elementos que se pueden pulsar «salen» de ella con relieve suave, y los campos donde se escribe se «hunden». El resto es silencio: mucho espacio en blanco, una columna central y una jerarquía directa. La estética la fijó el autor: minimalismo y claridad tipo Google combinado con neumorfismo (Soft UI).

El producto es una herramienta de operación para quien necesita completar un respaldo sin escribir comandos, así que la expresión nunca estorba la tarea ni el mensaje de error. Se rechaza el panel SaaS de tarjetas iguales con degradados.

**Key Characteristics:**
- Una hoja central de 60rem máximo, elevada sobre un fondo de página más hundido: ahí se ve dónde empieza y dónde acaba la parte útil. Una pantalla a la vez, siempre con camino de vuelta.
- Cuatro niveles de profundidad: fondo de página, hoja elevada, paneles por tono y controles con relieve o hundidos; la profundidad la dan dos sombras (una clara y otra oscura) y el cambio de tono.
- Un solo acento azul para la acción principal y el foco; el rojo se reserva a los errores.
- Tema claro y oscuro con los mismos roles; el contraste del texto no depende del relieve.

## Colors

Estrategia **Restringida**: una superficie neutra, un acento azul y dos colores de estado.

### Primary
- **Azul de acción** (#1967d2; oscuro #8ab4f8): botón principal, casillas marcadas, flechas de las filas activas, interruptor de tema y anillo de foco.

### Neutral
- **Fondo de página** (#d5dce5; oscuro #1b1e23): lo que rodea a la hoja; más hundido que ella.
- **Superficie gris azulada** (#eef1f5; oscuro #2b2f36): la hoja y todos los controles con relieve.
- **Panel** (#e6eaf0; oscuro #25292f): agrupa el contenido dentro de la hoja, con filete fino.
- **Tinta** (#1f2933; oscuro #e8eaed): texto principal.
- **Tinta suave** (#4a5662; oscuro #b8bec6): texto de apoyo, etiquetas de campo y filas no disponibles.
- **Línea de control** (#6f7c8a; oscuro #8d96a1): borde de 1,5px de campos, selector y casillas, para que no dependan solo de la sombra.

### Estado
- **Error** (#b3261e; oscuro #f6a39c) sobre su tinte al 10%: avisos de fallo y de datos faltantes.
- **Éxito** (#137333; oscuro #81c995) sobre su tinte al 10%: «Respaldo creado».

### Named Rules
**The One Blue Rule.** El azul es la única acción de color de la pantalla. Si algo más lo necesita, se resuelve con peso o tamaño.
**The Reserved Red Rule.** El rojo solo aparece cuando algo falló. Nunca decora ni destaca una opción.

## Typography

**Cuerpo y títulos:** Roboto (con system-ui de respaldo), autoalojada con @fontsource.
**Código y logs:** Roboto Mono, solo para el contenido del log de Oracle.

**Character:** neutra, legible y sin adornos; los títulos son ligeros (400) y las etiquetas y filas de peso medio (500).

### Hierarchy
- **Headline** (400, 1.75rem, 2.25rem): título de cada pantalla; 1.5rem en móvil.
- **Title** (500, 1rem, 1.5rem): encabezado de cada panel («Tablas», «Destino»).
- **Body** (400, 1rem, 1.5): texto de apoyo con medida máxima de 34rem.
- **Label** (500, 0.875rem): etiquetas de campo, botón «Volver» e interruptor de tema.
- **Code** (400, 0.8125rem, 1.5): log de Oracle en bloque con desplazamiento.

### Named Rules
**The Monospace Is Data Rule.** La fuente monoespaciada solo se usa para contenido real de log, nunca como decoración «técnica».

## Layout

Una hoja central de 60rem máximo (esquinas de 28px, relleno de 2.75rem) sobre el fondo de página, con 1.5rem de margen lateral y 3.5rem de aire inferior; la hoja ocupa al menos el 62% de la altura. La barra superior (marca a la izquierda, tema a la derecha) queda fuera de la hoja, sobre el fondo, a 1.75rem de ella. Las filas y los paneles se separan entre 1.125rem y 1.75rem; dentro de un panel, 1.5rem de relleno. Hasta 40rem la hoja baja a 20px de esquina y 1.25rem de relleno lateral; hasta 30rem los paneles bajan a 1.25rem y el título a 1.5rem. Sin barra lateral ni cuadrícula: la navegación es la propia pantalla y el botón «Volver».

## Elevation & Depth

Sistema de **cuatro niveles** con relieve de dos sombras (Soft UI): cada sombra tiene una versión clara (arriba a la izquierda) y otra oscura (abajo a la derecha). El fondo de página es el nivel más bajo, la hoja se eleva sobre él con la sombra más grande, los paneles se distinguen por tono y un filete de 1px (sin sombra propia) y los controles llevan relieve o se hunden.

### Shadow Vocabulary
- **Hoja** (`18px 18px 42px …, -14px -14px 34px …`): solo la hoja central; es la sombra más grande y lo que delimita la parte útil.
- **Relieve** (`7px 7px 16px var(--sombra-oscura), -7px -7px 16px var(--sombra-clara)`): filas activas.
- **Relieve suave** (`4px 4px 10px …, -4px -4px 10px …`): botones y píldoras.
- **Hundido** (`inset 3px 3px 7px …, inset -3px -3px 7px …`): campos, selector, casillas, pista del interruptor, etiquetas «Próximamente», avisos y bloque del log; también el estado pulsado de botones y filas.

### Named Rules
**The Sheet Rule.** Solo hay una hoja elevada por pantalla, y todo lo que se hace sobre ella vive dentro; nada flota fuera de sus bordes salvo la barra superior.
**The Press Inverts Rule.** Todo elemento con relieve se hunde al pulsarlo: la sombra pasa de exterior a interior.
**The Contrast Outranks Depth Rule.** El relieve nunca sustituye al contraste: el texto cumple 4,5:1, los campos llevan borde de línea de control y el foco es un anillo azul de 2px.

## Shapes

Esquinas generosas y consistentes: 28px en la hoja, 16px en filas y paneles, 12px en campos y bloque de log, píldora completa (999px) en botones, etiquetas e interruptor, y 6px en casillas. Sin bordes decorativos ni formas recortadas.

## Components

### Buttons
- **Shape:** píldora (999px).
- **Primary «Respaldar»:** fondo azul, texto sobre-acento, 52px de alto y ancho completo; al pulsar se hunde con sombra interior.
- **Secondary «Volver» e interruptor de tema:** misma superficie con relieve suave, 40px de alto, icono de flecha o pista a un lado.
- **Focus:** anillo azul de 2px con 3px de separación.

### Rows (filas de módulo)
- **Style:** fila de ancho completo, 60px de alto, relieve completo, nombre en peso medio y flecha azul a la derecha.
- **No disponible:** plana, sin relieve, texto suave y etiqueta «Próximamente» hundida; no se ofrece como acción.

### Inputs / Fields
- **Style:** superficie hundida, borde de 1,5px de línea de control, 12px de radio, 48px de alto.
- **Checkbox:** cuadro de 22px hundido; marcado, fondo azul con marca blanca (oscura en tema oscuro).

### Avisos
- **Error:** tinte rojo con sombra hundida y log opcional en bloque. **Éxito:** tinte verde, peso medio. Ambos se llevan a la vista al aparecer.

### Navigation
Sin menú persistente: el menú principal y el submenú son listas de filas, y «Volver» regresa un nivel. La vista nueva entra con un desplazamiento vertical de 10px en 320ms con salida exponencial, que se anula con `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** mantener una sola pantalla a la vez, con «Volver» arriba a la izquierda, dentro de la hoja.
- **Do** usar relieve solo en lo que se pulsa y hundido solo en lo que se escribe o se lee.
- **Do** dejar texto en español y mensajes que nombren el problema y el siguiente paso.
- **Do** probar cada cambio en tema claro y oscuro.

### Don't:
- **Don't** usar el relieve como único indicio de un control: añade borde o color.
- **Don't** introducir un segundo color de acento ni usar el rojo fuera de los errores.
- **Don't** construir cuadrículas de tarjetas iguales ni un panel SaaS genérico.
- **Don't** poner a la misma profundidad el fondo, la hoja y los controles: sin escalón de nivel no se ve el borde de lo útil.
- **Don't** usar sombras de bloque duro ni degradados.
